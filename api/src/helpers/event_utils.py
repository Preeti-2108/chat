import boto3
import os
from botocore.exceptions import ClientError

# DynamoDB setup
dynamodb = boto3.resource('dynamodb')
table_connection = dynamodb.Table(os.getenv('CONNECTION_TABLE'))

def extract_event_info(event):
    """
    Extract necessary information from the event.
    """
    domain_name = event.get('requestContext', {}).get('domainName')
    stage = event.get('requestContext', {}).get('stage')
    url = f'https://{domain_name}/{stage}' if domain_name and stage else None
    connection_id = event.get('requestContext', {}).get('connectionId')

    # Retrieve the access token associated with the connectionId from DynamoDB
    access_token = None
    if connection_id:
        try:
            response = table_connection.get_item(
                Key={
                    'connectionId': connection_id
                }
            )
            access_token = response.get('Item', {}).get('access_token')
            print(f"Access token for connection ID {connection_id}: {access_token}")
        except ClientError as e:
            print(f"Error retrieving access token: {e}")
    
    return {
        'url': url,
        'connectionId': connection_id,
        'access_token': access_token
    }
