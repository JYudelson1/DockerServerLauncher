import paramiko
import threading
import select
import time
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
                    log_callback: Callable[[str], None] = None,
                    timeout: int = 600,
                    use_pty: bool = True,
                    background: bool = False) -> int:
        """
        Run a command via SSH on a remote host.
        Calls log_callback with each line of output.
        Returns exit code.
        """
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        # Retry connection up to 10 times (5 minutes total)
        max_retries = 10
        for attempt in range(max_retries):
            try:
                client.connect(
                    ip, 
                    username=self.username, 
                    pkey=self.key,
                    timeout=30
                )
                if log_callback:
                    log_callback(f"[{ip}] Connection successful")
                break  # Connection successful
            except Exception as e:
                if attempt < max_retries - 1:
                    if log_callback:
                        log_callback(f"[{ip}] Connection attempt {attempt + 1} failed, retrying in 30s...")
                    time.sleep(30)
                else:
                    raise  # Final attempt failed
        
        try:
            stdin, stdout, stderr = client.exec_command(command, get_pty=use_pty, timeout=timeout)
            
            if background:
                # For background commands, don't wait - just close and return
                if log_callback:
                    log_callback(f"[{ip}] Started background process")
                time.sleep(1)  # Give it a moment to start
                return 0
            
            # Read output with progress updates
            last_log_time = time.time()
            output_buffer = ""
            error_buffer = ""
            
            while not stdout.channel.exit_status_ready():
                # Check if there's data to read
                if stdout.channel.recv_ready():
                    chunk = stdout.channel.recv(1024).decode('utf-8', errors='replace')
                    output_buffer += chunk
                    
                    # Log complete lines
                    while '\n' in output_buffer:
                        line, output_buffer = output_buffer.split('\n', 1)
                        if log_callback and line.strip():
                            log_callback(f"[{ip}] {line.strip()}")
                        last_log_time = time.time()
                
                if stdout.channel.recv_stderr_ready():
                    chunk = stdout.channel.recv_stderr(1024).decode('utf-8', errors='replace')
                    error_buffer += chunk
                    
                    # Log complete lines
                    while '\n' in error_buffer:
                        line, error_buffer = error_buffer.split('\n', 1)
                        if log_callback and line.strip():
                            log_callback(f"[{ip}] ERROR: {line.strip()}")
                        last_log_time = time.time()
                
                # Send periodic "still running" message
                if time.time() - last_log_time > 30:
                    if log_callback:
                        log_callback(f"[{ip}] Still running... (no output for 30s)")
                    last_log_time = time.time()
                
                time.sleep(0.1)  # Small delay to avoid busy waiting
            
            # Read any remaining output
            remaining_out = stdout.read().decode('utf-8', errors='replace')
            if remaining_out and log_callback:
                for line in remaining_out.split('\n'):
                    if line.strip():
                        log_callback(f"[{ip}] {line.strip()}")
            
            remaining_err = stderr.read().decode('utf-8', errors='replace')
            if remaining_err and log_callback:
                for line in remaining_err.split('\n'):
                    if line.strip():
                        log_callback(f"[{ip}] ERROR: {line.strip()}")
            
            exit_code = stdout.channel.recv_exit_status()
            return exit_code
            
        finally:
            client.close()
    
    def run_parallel(self, commands: List[Tuple[str, str]], 
                log_callback: Callable[[str], None] = None,
                use_pty: bool = True,
                background: bool = False):
        """
        Run multiple SSH commands in parallel.
        commands: List of (ip, command) tuples
        Raises exception if any command fails.
        """
        results = []
        threads = []
        
        def run_and_store(ip, command):
            try:
                exit_code = self.run_command(ip, command, log_callback, use_pty=use_pty, background=background)
                results.append((ip, exit_code))
            except Exception as e:
                results.append((ip, e))
        
        for ip, command in commands:
            thread = threading.Thread(
                target=run_and_store,
                args=(ip, command)
            )
            thread.start()
            threads.append(thread)
        
        for thread in threads:
            thread.join()
        
        # Check for failures (skip for background commands)
        if not background:
            failures = [(ip, result) for ip, result in results if isinstance(result, Exception) or result != 0]
            if failures:
                error_msg = "\n".join([f"{ip}: {result}" for ip, result in failures])
                raise Exception(f"Some worker setups failed:\n{error_msg}")