import paramiko
import threading
from typing import Callable, List, Tuple
import os

class SSHRunner:
    def __init__(self, key_path: str, username: str = 'ubuntu'):
        self.key_path = os.path.expanduser(key_path)
        self.username = username
        
        # Try to load the key - handle both RSA and ED25519, and different formats
        try:
            self.key = paramiko.RSAKey.from_private_key_file(self.key_path)
        except Exception:
            try:
                self.key = paramiko.Ed25519Key.from_private_key_file(self.key_path)
            except Exception:
                try:
                    self.key = paramiko.ECDSAKey.from_private_key_file(self.key_path)
                except Exception as e:
                    raise Exception(f"Could not load SSH key from {self.key_path}. Error: {e}")
    
    def run_command(self, ip: str, command: str, 
                    log_callback: Callable[[str], None] = None) -> int:
        """
        Run a command via SSH on a remote host.
        Calls log_callback with each line of output.
        Returns exit code.
        """
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        try:
            client.connect(
                ip, 
                username=self.username, 
                pkey=self.key,
                timeout=30
            )
            
            stdin, stdout, stderr = client.exec_command(command)
            
            # Stream output line by line
            for line in stdout:
                if log_callback:
                    log_callback(f"[{ip}] {line.strip()}")
            
            for line in stderr:
                if log_callback:
                    log_callback(f"[{ip}] ERROR: {line.strip()}")
            
            exit_code = stdout.channel.recv_exit_status()
            return exit_code
            
        finally:
            client.close()
    
    def run_parallel(self, commands: List[Tuple[str, str]], 
                    log_callback: Callable[[str], None] = None):
        """
        Run multiple SSH commands in parallel.
        commands: List of (ip, command) tuples
        """
        threads = []
        for ip, command in commands:
            thread = threading.Thread(
                target=self.run_command,
                args=(ip, command, log_callback)
            )
            thread.start()
            threads.append(thread)
        
        for thread in threads:
            thread.join()