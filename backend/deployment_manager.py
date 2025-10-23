import random
import time
import os
from datetime import datetime
from typing import Dict, List, Tuple
import threading
from ssh_runner import SSHRunner
from aws_client import AWSClient
from storage import Storage

class DeploymentManager:
    def __init__(self, aws_client: AWSClient, ssh_runner: SSHRunner, storage: Storage):
        self.aws = aws_client
        self.ssh = ssh_runner
        self.storage = storage
    
    def launch_deployment(self, count: int, key_name: str, 
                         name: str = None) -> str:
        """
        Launch a new deployment asynchronously.
        Returns deployment ID immediately.
        """
        deployment_id = f"dep-{int(time.time())}"
        
        deployment = {
            'id': deployment_id,
            'created_at': datetime.utcnow().isoformat() + 'Z',
            'name': name or f"cluster-{count}-nodes",
            'status': 'launching',
            'key_name': key_name,
            'head': None,
            'workers': [],
            'log_file': f"~/.aws-deployment-manager/logs/{deployment_id}.log"
        }
        
        self.storage.save_deployment(deployment)
        
        # Run setup in background
        thread = threading.Thread(
            target=self._setup_deployment,
            args=(deployment_id, count, key_name)
        )
        thread.daemon = True
        thread.start()
        
        return deployment_id
    
    def _setup_deployment(self, deployment_id: str, count: int, key_name: str):
        """Background task to set up deployment"""
        try:
            deployment = self.storage.get_deployment(deployment_id)
            log_callback = self._make_log_callback(deployment_id)
            
            # Step 1: Launch instances
            log_callback("Launching EC2 instances...")
            instance_ids = self.aws.launch_instances(
                template_id=os.getenv('LAUNCH_TEMPLATE_ID'),
                count=count,
                key_name=key_name,
                deployment_id=deployment_id
            )
            deployment['status'] = 'waiting_for_ips'
            self.storage.save_deployment(deployment)
            
            # Step 2: Wait for running state and get IPs
            log_callback(f"Waiting for {count} instances to reach running state...")
            self.aws.wait_for_running(instance_ids)
            
            log_callback("Getting instance IPs...")
            ip_map = self.aws.get_instance_ips(instance_ids)
            
            # NEW: Wait for instances to pass status checks (SSH will be ready)
            log_callback("Waiting for instances to pass status checks...")
            self.aws.wait_for_status_ok(instance_ids)
            
            # Step 3: Pick random head
            instance_items = list(ip_map.items())
            random.shuffle(instance_items)
            head_id, head_ip = instance_items[0]
            workers = instance_items[1:]
            
            deployment['head'] = {
                'instance_id': head_id,
                'ip': head_ip
            }
            deployment['workers'] = [
                {'instance_id': wid, 'ip': wip} 
                for wid, wip in workers
            ]
            deployment['status'] = 'setting_up'
            self.storage.save_deployment(deployment)
            
            log_callback(f"Head node: {head_ip}")
            log_callback(f"Worker nodes: {', '.join(wip for _, wip in workers)}")
            
            # Step 4: Set up workers per-worker (install then start), in parallel across workers
            log_callback("Setting up worker nodes (installing dependencies)...")
            worker_threads = []

            def setup_single_worker(worker_ip: str):
                # Install dependencies (blocking)
                install_cmd = self._get_worker_setup_command_1()
                rc = self.ssh.run_command(worker_ip, install_cmd, log_callback, use_pty=False, background=False)
                if rc != 0:
                    raise Exception(f"[{worker_ip}] Worker dependency installation failed with exit code {rc}")

                # Start worker server (remote background via nohup)
                if log_callback:
                    log_callback(f"[{worker_ip}] Starting worker server...")
                start_cmd = self._get_worker_setup_command_2()
                self.ssh.run_command(worker_ip, start_cmd, log_callback, use_pty=False, background=False)

            for _, worker_ip in workers:
                t = threading.Thread(target=setup_single_worker, args=(worker_ip,))
                t.start()
                worker_threads.append(t)

            # Wait for all workers to finish their per-worker sequence (mirrors `wait`)
            for t in worker_threads:
                t.join()

            # Step 5: Set up head node
            log_callback("Setting up head node...")
            worker_ips = [wip for _, wip in workers]
            comma_separated_urls = ','.join(
                f"http://{ip}:8080" for ip in worker_ips
            )
            # Split head setup into install (blocking) and start (nohup)
            head_install_cmd = self._get_head_setup_install_command()
            rc_head_install = self.ssh.run_command(head_ip, head_install_cmd, log_callback, use_pty=False, background=False)
            if rc_head_install != 0:
                raise Exception(f"[{head_ip}] Head install failed with exit code {rc_head_install}")

            head_start_cmd = self._get_head_setup_start_command(comma_separated_urls)
            self.ssh.run_command(head_ip, head_start_cmd, log_callback, use_pty=False, background=False)
            
            # Done!
            deployment['status'] = 'running'
            self.storage.save_deployment(deployment)
            log_callback("✓ Deployment complete!")
            
        except Exception as e:
            log_callback(f"ERROR: {str(e)}")
            deployment = self.storage.get_deployment(deployment_id)
            deployment['status'] = 'failed'
            self.storage.save_deployment(deployment)
    
    def _make_log_callback(self, deployment_id: str):
        """Create a callback that logs to file"""
        log_file = os.path.expanduser(
            f"~/.aws-deployment-manager/logs/{deployment_id}.log"
        )
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        
        def callback(message: str):
            timestamp = datetime.utcnow().isoformat()
            log_line = f"[{timestamp}] {message}\n"
            
            # Write to file
            with open(log_file, 'a') as f:
                f.write(log_line)
            
        return callback
    
    def _get_worker_setup_command_1(self) -> str:
        """Returns the first worker setup command (install deps)"""
        return (
            "sudo apt update && "
            "sudo apt install -y python3-pip python3-venv python-is-python3 && "
            "sudo apt-get install -y apt-transport-https ca-certificates curl "
            "software-properties-common && "
            "curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo apt-key add - && "
            "DISTRO=$(lsb_release -cs) && "  # Store in a variable first
            "sudo add-apt-repository -y "
            "\"deb [arch=amd64] https://download.docker.com/linux/ubuntu $DISTRO stable\" && "
            "sudo DEBIAN_FRONTEND=noninteractive apt-get update && "
            "sudo DEBIAN_FRONTEND=noninteractive apt-get install -y docker-ce && "
            "sudo usermod -aG docker $USER && "
            "python3 -m venv ~/.venv && "
            "~/.venv/bin/pip install --force-reinstall "
            "git+https://github.com/astOwOlfo/scalable_docker.git@new"
        )
    
    def _get_worker_setup_command_2(self) -> str:
        """Returns the second worker setup command (start server)"""
        return (
            "nohup ~/.venv/bin/python -m scalable_docker.worker_server "
            "> ~/scalable_docker_worker_server.log 2>&1 &"
        )
    
    def _get_head_setup_install_command(self) -> str:
        """Install Python and scalable_docker on head (blocking)"""
        return (
            "sudo apt update && "
            "sudo apt install -y python3-pip python3-venv python-is-python3 && "
            "python3 -m venv ~/.venv && "
            "~/.venv/bin/pip install --force-reinstall "
            "git+https://github.com/astOwOlfo/scalable_docker.git@new"
        )

    def _get_head_setup_start_command(self, worker_urls: str) -> str:
        """Start head server with nohup (detached)"""
        return (
            f"nohup ~/.venv/bin/python -m scalable_docker.head_server "
            f"--worker-urls {worker_urls} "
            "> ~/scalable_docker_head_server.log 2>&1 &"
        )
    
    def delete_deployment(self, deployment_id: str) -> List[str]:
        """Terminate all instances in a deployment"""
        deployment = self.storage.get_deployment(deployment_id)
        if deployment:
            deployment['status'] = 'terminating'  # Intermediate state
            self.storage.save_deployment(deployment)
        
        terminated = self.aws.terminate_deployment(deployment_id)
        
        if terminated and deployment:
            deployment['status'] = 'terminated'
            self.storage.save_deployment(deployment)
        
        return terminated