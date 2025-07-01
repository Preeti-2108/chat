import boto3
import os
from botocore.exceptions import ClientError

# Initialize a DynamoDB resource using Boto3
dynamodb = boto3.resource('dynamodb')

# Access the DynamoDB table specified by the environment variable 'TABLE'
table_connection = dynamodb.Table(os.getenv('TABLE'))

def extract_event_info(event):
    """
    Extracts and returns essential information from an AWS API Gateway event.
    
    This function retrieves the domain name, stage, and connection ID from the event's
    request context. It constructs a URL using the domain name and stage if both are available.
    Additionally, it attempts to fetch an access token from a DynamoDB table using the connection ID.
    
    Parameters:
    event (dict): The event dictionary containing request context information.
    
    Returns:
    dict: A dictionary containing the constructed URL, connection ID, and access token.
    """
    # Extract domain name and stage from the event's request context
    domain_name = event.get('requestContext', {}).get('domainName')
    stage = event.get('requestContext', {}).get('stage')
    
    # Construct the URL using domain name and stage if both are present
    url = f'https://{domain_name}/{stage}' if domain_name and stage else None
    
    # Extract connection ID from the event's request context
    connection_id = event.get('requestContext', {}).get('connectionId')

    # Initialize access token as None
    # TODO: Implement proper token storage/retrieval mechanism for WebSocket connections
    access_token = None
    
    # For now, we disable the access token retrieval to avoid schema mismatch errors
    # This should be implemented with a proper connections table if needed
    
    # If a connection ID is present, attempt to retrieve the associated access token from DynamoDB
    # DISABLED: This causes schema errors because the main table uses 'id' not 'connectionId'
    # if connection_id:
    #     try:
    #         response = table_connection.get_item(
    #             Key={
    #                 'connectionId': connection_id
    #             }
    #         )
    #         access_token = response.get('Item', {}).get('access_token')
    #         print(f"Access token for connection ID {connection_id}: {access_token}")
    #     except ClientError as e:
    #         print(f"Error retrieving access token: {e}")
    #         access_token = None
    
    # Return a dictionary containing the URL, connection ID, and access token
    return {
        'url': url,
        'connectionId': connection_id,
        'access_token': access_token
    }