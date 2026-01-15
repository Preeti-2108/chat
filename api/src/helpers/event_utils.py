import boto3
import os
import logging
from botocore.exceptions import ClientError
from src.helpers.websocket_security import get_secure_websocket_url, SecurityError

logger = logging.getLogger(__name__)
logger.setLevel(os.getenv('LOG_LEVEL', 'INFO'))

# Initialize a DynamoDB resource using Boto3
dynamodb = boto3.resource('dynamodb')

# Access the DynamoDB table specified by the environment variable 'TABLE'
table_connection = dynamodb.Table(os.getenv('TABLE'))

def extract_event_info(event):
    """
    Extracts and returns essential information from an AWS API Gateway event.
    
    This function retrieves the domain name, stage, and connection ID from the event's
    request context. It constructs a URL using the domain name and stage if both are available,
    with SSRF protection by validating the URL against a whitelist.
    Additionally, it attempts to fetch an access token from a DynamoDB table using the connection ID.
    
    Parameters:
    event (dict): The event dictionary containing request context information.
    
    Returns:
    dict: A dictionary containing the validated URL, connection ID, and access token.
    """
    # Extract domain name and stage from the event's request context
    domain_name = event.get('requestContext', {}).get('domainName')
    stage = event.get('requestContext', {}).get('stage')
    
    # SECURITY FIX: Use secure URL construction with validation to prevent SSRF attacks
    url = None
    if domain_name and stage:
        try:
            # Use the secure function that validates against whitelist
            url = get_secure_websocket_url(domain_name, stage)
            if url:
                logger.info(f"Validated WebSocket URL: {url}")
            else:
                logger.error(f"WebSocket URL validation failed for domain: {domain_name}, stage: {stage}")
        except SecurityError as e:
            logger.error(f"SECURITY WARNING: WebSocket URL validation failed: {e}")
            # In case of security error, we don't provide the URL
            url = None
    
    # Extract connection ID from the event's request context
    connection_id = event.get('requestContext', {}).get('connectionId')

    # Initialize access token as None
    access_token = None
    
    # Try to extract token from the event first
    from src.helpers.cognito_auth import extract_token_from_event
    access_token = extract_token_from_event(event)
    
    # Alternative: If you have a separate CONNECTIONS_TABLE and the token wasn't found in event
    if not access_token and connection_id:
        connections_table_name = os.getenv('CONNECTIONS_TABLE')
        if connections_table_name:
            try:
                connections_table = boto3.resource('dynamodb').Table(connections_table_name)
                response = connections_table.get_item(
                    Key={
                        'connectionId': connection_id
                    }
                )
                stored_token = response.get('Item', {}).get('access_token')
                if stored_token:
                    access_token = stored_token
                    logger.info(f"Retrieved access token from connections table for connection ID {connection_id}")
            except ClientError as e:
                logger.error(f"Error retrieving access token from connections table: {e}")
                pass
    
    # Return a dictionary containing the URL, connection ID, and access token
    return {
        'url': url,
        'connectionId': connection_id,
        'access_token': access_token
    }