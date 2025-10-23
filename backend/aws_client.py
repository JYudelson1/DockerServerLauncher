import boto3
from typing import List, Dict
import os

class AWSClient:
    def __init__(self):
        region = os.getenv('AWS_REGION', 'us-east-1')
        self.ec2 = boto3.client('ec2', region_name=region)
        print(f"Using region: {region}")  # Debug
    
    def get_key_pairs(self) -> List[Dict]:
        """Fetch all SSH key pairs from AWS"""
        response = self.ec2.describe_key_pairs()
        print(f"Found {len(response['KeyPairs'])} key pairs")  # Debug line
        return response['KeyPairs']
    
    def launch_instances(self, template_id: str, count: int, 
                        key_name: str, deployment_id: str) -> List[str]:
        """
        Launch instances from template.
        Tags all instances with DeploymentId.
        Returns list of instance IDs.
        """
        # Get subnets from default VPC (AWS will pick one with capacity)
        vpcs = self.ec2.describe_vpcs(Filters=[{'Name': 'isDefault', 'Values': ['true']}])
        if vpcs['Vpcs']:
            vpc_id = vpcs['Vpcs'][0]['VpcId']
            subnets = self.ec2.describe_subnets(Filters=[{'Name': 'vpc-id', 'Values': [vpc_id]}])
            subnet_ids = [s['SubnetId'] for s in subnets['Subnets']]
        else:
            subnet_ids = []
        
        launch_params = {
            'LaunchTemplate': {
                'LaunchTemplateId': template_id,
                'Version': '13'
            },
            'KeyName': key_name,
            'MinCount': count,
            'MaxCount': count,
            'TagSpecifications': [{
                'ResourceType': 'instance',
                'Tags': [
                    {'Key': 'DeploymentId', 'Value': deployment_id},
                    {'Key': 'Name', 'Value': f'deployment-{deployment_id}'}
                ]
            }]
        }
        
        # If we found subnets, let AWS pick one by providing all options
        if subnet_ids:
            # Just pick the first available subnet - AWS will use it if it has capacity
            launch_params['SubnetId'] = subnet_ids[0]
        
        response = self.ec2.run_instances(**launch_params)
        return [inst['InstanceId'] for inst in response['Instances']]
    
    def wait_for_running(self, instance_ids: List[str]) -> None:
        """Wait for all instances to reach running state"""
        waiter = self.ec2.get_waiter('instance_running')
        waiter.wait(InstanceIds=instance_ids)
    
    def get_instance_ips(self, instance_ids: List[str]) -> Dict[str, str]:
        """
        Get public IPs for instances.
        Returns dict of {instance_id: public_ip}
        """
        response = self.ec2.describe_instances(InstanceIds=instance_ids)
        result = {}
        for reservation in response['Reservations']:
            for instance in reservation['Instances']:
                result[instance['InstanceId']] = instance['PublicIpAddress']
        return result
    
    def terminate_deployment(self, deployment_id: str) -> List[str]:
        """
        Find all instances with DeploymentId tag and terminate them.
        Returns list of terminated instance IDs.
        """
        response = self.ec2.describe_instances(
            Filters=[{
                'Name': 'tag:DeploymentId',
                'Values': [deployment_id]
            }, {
                'Name': 'instance-state-name',
                'Values': ['pending', 'running', 'stopping', 'stopped']
            }]
        )
        
        instance_ids = []
        for reservation in response['Reservations']:
            for instance in reservation['Instances']:
                instance_ids.append(instance['InstanceId'])
        
        if instance_ids:
            # Actually terminate
            terminate_response = self.ec2.terminate_instances(InstanceIds=instance_ids)
            
            # Verify the termination request was accepted
            successfully_terminated = [
                inst['InstanceId'] 
                for inst in terminate_response['TerminatingInstances']
                if inst['CurrentState']['Name'] in ['shutting-down', 'terminated']
            ]
            
            return successfully_terminated
        
        return []
    
    def wait_for_status_ok(self, instance_ids: List[str]) -> None:
        """Wait for all instances to pass status checks (2/2 checks)"""
        waiter = self.ec2.get_waiter('instance_status_ok')
        waiter.wait(InstanceIds=instance_ids)