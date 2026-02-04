"""
VPC Configuration Helper

This module retrieves VPC configuration (security groups and subnets) from AWS Secrets Manager.
It mirrors the configuration used in serverless templates.
"""

import json
import boto3
from typing import Dict, List
import logging

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


def get_vpc_config_from_secrets_manager() -> Dict[str, any]:
    """
    Retrieve VPC configuration from AWS Secrets Manager.

    Expected secret format in Secrets Manager:
    - Secret name: serverless/vpc/sg
      Content: {"securityGroup": "sg-xxxxx"}

    - Secret name: serverless/vpc/subnets
      Content: {"sub1": "subnet-xxxxx", "sub2": "subnet-xxxxx", "sub3": "subnet-xxxxx"}

    Returns:
        Dict with 'security_groups' (list) and 'subnets' (list)
    """
    try:
        secrets_client = boto3.client('secretsmanager')

        # Get security group from Secrets Manager
        sg_response = secrets_client.get_secret_value(SecretId='serverless/vpc/sg')
        sg_data = json.loads(sg_response['SecretString'])
        security_group = sg_data.get('securityGroup')

        if not security_group:
            raise ValueError("Security group not found in secret 'serverless/vpc/sg'")

        # Get subnets from Secrets Manager
        subnets_response = secrets_client.get_secret_value(SecretId='serverless/vpc/subnets')
        subnets_data = json.loads(subnets_response['SecretString'])

        subnets = [
            subnets_data.get('sub1'),
            subnets_data.get('sub2'),
            subnets_data.get('sub3')
        ]

        # Filter out None values
        subnets = [subnet for subnet in subnets if subnet]

        if not subnets:
            raise ValueError("No subnets found in secret 'serverless/vpc/subnets'")

        # Get VPC ID from first subnet
        ec2_client = boto3.client('ec2')
        subnet_info = ec2_client.describe_subnets(SubnetIds=[subnets[0]])
        vpc_id = subnet_info['Subnets'][0]['VpcId']

        logger.info(f"Retrieved VPC config - VPC: {vpc_id}, Security Group: {security_group}, Subnets: {len(subnets)}")

        return {
            'security_groups': [security_group],
            'subnets': subnets,
            'vpc_id': vpc_id
        }

    except Exception as e:
        logger.error(f"Failed to retrieve VPC configuration from Secrets Manager: {str(e)}")
        logger.warning("Proceeding without VPC configuration - Lambdas will run without VPC")
        return {
            'security_groups': [],
            'subnets': [],
            'vpc_id': None
        }


def has_vpc_config() -> bool:
    """
    Check if VPC configuration is available in Secrets Manager.

    Returns:
        True if VPC config exists, False otherwise
    """
    try:
        secrets_client = boto3.client('secretsmanager')
        secrets_client.get_secret_value(SecretId='serverless/vpc/sg')
        secrets_client.get_secret_value(SecretId='serverless/vpc/subnets')
        return True
    except Exception:
        return False
