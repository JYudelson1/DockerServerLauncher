import json
import os
from typing import Dict, List, Optional

class Storage:
    def __init__(self, data_dir: str = "~/.aws-deployment-manager"):
        self.data_dir = os.path.expanduser(data_dir)
        self.deployments_file = os.path.join(self.data_dir, "deployments.json")
        self._ensure_dirs()
    
    def _ensure_dirs(self):
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(os.path.join(self.data_dir, "logs"), exist_ok=True)
        if not os.path.exists(self.deployments_file):
            with open(self.deployments_file, 'w') as f:
                json.dump({}, f)
    
    def get_all_deployments(self) -> Dict:
        with open(self.deployments_file, 'r') as f:
            return json.load(f)
    
    def get_deployment(self, deployment_id: str) -> Optional[Dict]:
        deployments = self.get_all_deployments()
        return deployments.get(deployment_id)
    
    def save_deployment(self, deployment: Dict):
        deployments = self.get_all_deployments()
        deployments[deployment['id']] = deployment
        with open(self.deployments_file, 'w') as f:
            json.dump(deployments, f, indent=2)
    
    def delete_deployment(self, deployment_id: str):
        deployments = self.get_all_deployments()
        if deployment_id in deployments:
            del deployments[deployment_id]
            with open(self.deployments_file, 'w') as f:
                json.dump(deployments, f, indent=2)