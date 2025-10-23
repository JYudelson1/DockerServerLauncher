from flask import Flask, jsonify, request, Response
from flask_cors import CORS
from dotenv import load_dotenv
import os
import json
import platform
import subprocess
import time

from aws_client import AWSClient
from ssh_runner import SSHRunner
from deployment_manager import DeploymentManager
from storage import Storage

load_dotenv()

app = Flask(__name__)
CORS(app)

# Initialize components
aws_client = AWSClient()
storage = Storage()

@app.route('/api/keys', methods=['GET'])
def get_keys():
    """Get list of available SSH keys"""
    keys = aws_client.get_key_pairs()
    return jsonify({
        'keys': [{'name': k['KeyName'], 'fingerprint': k['KeyFingerprint']} 
                 for k in keys],
        'default': os.getenv('DEFAULT_KEY_NAME')
    })

@app.route('/api/launch', methods=['POST'])
def launch_deployment():
    """Launch a new deployment"""
    data = request.json
    count = data['count']
    key_name = data['key_name']
    name = data.get('name')
    
    # Get SSH key path from env
    key_path = os.getenv("PATH_TO_AWS_PRIVATE_KEY") or f"~/.ssh/{key_name}.pem"
    key_path = os.path.expanduser(key_path)
    
    # Create manager with SSH runner for this key
    ssh_runner = SSHRunner(key_path, 'ubuntu')
    manager = DeploymentManager(aws_client, ssh_runner, storage)
    
    deployment_id = manager.launch_deployment(count, key_name, name)
    
    return jsonify({
        'deployment_id': deployment_id,
        'status': 'launching'
    })

@app.route('/api/deployments', methods=['GET'])
def get_deployments():
    """Get all deployments"""
    deployments = storage.get_all_deployments()
    
    # Transform to list format for frontend
    result = []
    for dep_id, dep in deployments.items():
        result.append({
            'id': dep['id'],
            'name': dep['name'],
            'created_at': dep['created_at'],
            'status': dep['status'],
            'head_ip': dep['head']['ip'] if dep.get('head') else None,
            'worker_count': len(dep.get('workers', []))
        })
    
    # Sort by created_at descending
    result.sort(key=lambda x: x['created_at'], reverse=True)
    
    return jsonify({'deployments': result})

@app.route('/api/deployments/<deployment_id>', methods=['GET'])
def get_deployment(deployment_id):
    """Get detailed deployment info"""
    deployment = storage.get_deployment(deployment_id)
    if not deployment:
        return jsonify({'error': 'Deployment not found'}), 404
    return jsonify(deployment)

@app.route('/api/deployments/<deployment_id>', methods=['DELETE'])
def delete_deployment(deployment_id):
    """Delete a deployment"""
    deployment = storage.get_deployment(deployment_id)
    if not deployment:
        return jsonify({'error': 'Deployment not found'}), 404
    
    key_name = deployment['key_name']
    key_path = os.getenv("PATH_TO_AWS_PRIVATE_KEY") or f"~/.ssh/{key_name}.pem"
    key_path = os.path.expanduser(key_path)
    
    ssh_runner = SSHRunner(key_path)
    manager = DeploymentManager(aws_client, ssh_runner, storage)
    
    terminated = manager.delete_deployment(deployment_id)
    
    return jsonify({
        'success': True,
        'terminated_instances': terminated
    })

@app.route('/api/deployments/<deployment_id>/logs/stream', methods=['GET'])
def stream_logs(deployment_id):
    """Stream deployment logs via SSE"""
    deployment = storage.get_deployment(deployment_id)
    if not deployment:
        return jsonify({'error': 'Deployment not found'}), 404
    
    log_file = os.path.expanduser(deployment['log_file'])
    
    def generate():
        # First, send existing logs
        if os.path.exists(log_file):
            with open(log_file, 'r') as f:
                for line in f:
                    yield f"data: {json.dumps({'type': 'log', 'message': line.strip()})}\n\n"
        
        # Then tail the file for new lines
        last_position = os.path.getsize(log_file) if os.path.exists(log_file) else 0
        
        while True:
            # Check if deployment is complete first
            current_deployment = storage.get_deployment(deployment_id)
            if current_deployment['status'] in ['running', 'failed', 'terminated']:
                # Send any remaining logs
                if os.path.exists(log_file):
                    current_size = os.path.getsize(log_file)
                    if current_size > last_position:
                        with open(log_file, 'r') as f:
                            f.seek(last_position)
                            for line in f:
                                yield f"data: {json.dumps({'type': 'log', 'message': line.strip()})}\n\n"
                
                yield f"data: {json.dumps({'type': 'complete', 'status': current_deployment['status']})}\n\n"
                break
            
            # Stream new log lines
            if os.path.exists(log_file):
                current_size = os.path.getsize(log_file)
                if current_size > last_position:
                    with open(log_file, 'r') as f:
                        f.seek(last_position)
                        for line in f:
                            yield f"data: {json.dumps({'type': 'log', 'message': line.strip()})}\n\n"
                    last_position = current_size
            
            time.sleep(1)
    
    return Response(generate(), mimetype='text/event-stream')

@app.route('/api/connect/<deployment_id>', methods=['POST'])
def connect_to_head(deployment_id):
    """Open terminal and SSH to head node"""
    deployment = storage.get_deployment(deployment_id)
    if not deployment or not deployment.get('head'):
        return jsonify({'error': 'Deployment not found or no head node'}), 404
    
    head_ip = deployment['head']['ip']
    key_name = deployment['key_name']
    key_path = os.getenv("PATH_TO_AWS_PRIVATE_KEY") or f"~/.ssh/{key_name}.pem"
    key_path = os.path.expanduser(key_path)
    username = os.getenv('SSH_USERNAME', 'ubuntu')
    
    # Launch terminal with SSH command
    ssh_cmd = f"ssh -i {key_path} {username}@{head_ip}"
    
    system = platform.system()
    try:
        if system == 'Darwin':  # Mac
            subprocess.Popen([
                'osascript', '-e',
                f'tell app "Terminal" to do script "{ssh_cmd}"'
            ])
        elif system == 'Linux':
            # Try to use $TERMINAL env var first, then common terminals
            terminal = os.getenv('TERMINAL')
            if terminal:
                subprocess.Popen([terminal, '-e', ssh_cmd])
            else:
                for term in ['gnome-terminal', 'konsole', 'xterm', 'terminator']:
                    try:
                        subprocess.Popen([term, '--', 'bash', '-c', ssh_cmd])
                        break
                    except FileNotFoundError:
                        continue
        elif system == 'Windows':
            subprocess.Popen(['start', 'cmd', '/k', ssh_cmd], shell=True)
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/deployments/<deployment_id>/logs/open', methods=['GET'])
def open_log_file(deployment_id):
    """Open log file in default text editor"""
    deployment = storage.get_deployment(deployment_id)
    if not deployment:
        return jsonify({'error': 'Deployment not found'}), 404
    
    log_file = os.path.expanduser(deployment['log_file'])
    
    if not os.path.exists(log_file):
        return jsonify({'error': 'Log file not found'}), 404
    
    system = platform.system()
    try:
        if system == 'Darwin':
            subprocess.Popen(['open', log_file])
        elif system == 'Linux':
            subprocess.Popen(['xdg-open', log_file])
        elif system == 'Windows':
            subprocess.Popen(['start', log_file], shell=True)
        
        return jsonify({'success': True, 'log_file': log_file})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5001)