import json
import uuid
import boto3
import os
import logging
from botocore.exceptions import ClientError
from jwt import PyJWKClient, decode as jwt_decode, InvalidTokenError, PyJWKError

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Configuration
dynamodb = boto3.resource('dynamodb')
connection_table_name = os.getenv('CONNECTION_TABLE')
user_pool_id = os.getenv('COGNITO_POOL_ID')
region = os.getenv('REGION')
websocket_endpoint_url = os.getenv('WEBSOCKET_ENDPOINT_URL')

# Check for environment variable
if not connection_table_name:
    raise ValueError("Environment variable CONNECTION_TABLE is not set.")
table_connection = dynamodb.Table(connection_table_name)

# JWKS URL for Cognito User Pool
jwks_url = f'https://cognito-idp.{region}.amazonaws.com/{user_pool_id}/.well-known/jwks.json'
jwks_client = PyJWKClient(jwks_url)

def validate_access_token(access_token):
    """ Validate access token and return the scope if valid. """
    try:
        signing_key = jwks_client.get_signing_key_from_jwt(access_token)
        decoded_token = jwt_decode(
            access_token,
            signing_key.key,
            algorithms=["RS256"]
        )
        
        # If the token is valid, you can extract the scope from the payload
        scope = decoded_token.get('scope', None)
        return scope

    except InvalidTokenError as e:
        logging.error(f"Invalid token error: {e}")
    except PyJWKError as e:
        logging.error(f"JWK error: {e}")
    except Exception as e:
        logging.error(f"Unexpected error during token validation: {e}")

    return None

def connect(event, context):
    """ Handler for new client connection to WebSocket. """
    access_token = event.get('queryStringParameters', {}).get('access_token')
    if not access_token:
        return {
            'statusCode': 400,
            'body': json.dumps('Missing access_token in query parameters')
        }
    
    scope = validate_access_token(access_token)
    if not scope:
        return {
            'statusCode': 401,
            'body': json.dumps('Invalid or missing access_token')
        }
    
    connection_id = event['requestContext']['connectionId']
    try:
        table_connection.put_item(
            Item={
                'id': str(uuid.uuid4()),
                'connectionId': connection_id,
                'scope': scope
            }
        )
        logging.info(f"Connection ID {connection_id} and scope {scope} saved in {connection_table_name}.")
    except ClientError as e:
        logging.error(f"Error storing connection details: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps('Error storing connection details')
        }
    
    return {
        'statusCode': 200,
        'body': json.dumps('Connected')
    }

def disconnect(event, context):
    """ Handler for client disconnect from WebSocket. """
    connection_id = event['requestContext']['connectionId']
    logging.info(f"Connection ID {connection_id} disconnected.")
    
    try:
        table_connection.delete_item(
            Key={'connectionId': connection_id}
        )
        logging.info("Connection ID removed successfully.")
    except ClientError as e:
        logging.error(f"Error removing connection details: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps('Error removing connection details')
        }
    
    return {
        'statusCode': 200,
        'body': json.dumps('Disconnected')
    }

def defaultMessage(event, context):
    """ Handler for receiving message from WebSocket client. """
    logging.debug(f"Received event: {event}")
    connection_id = event['requestContext']['connectionId']
    body = json.loads(event.get('body', '{}'))  # Ensure body is loaded as JSON
    
    if 'message' not in body:
        return {
            'statusCode': 400,
            'body': json.dumps('Invalid message format')
        }
    
    logging.debug(f"Received message from {connection_id}: {body}")
    send_to_client(connection_id, f"Echo: {body['message']}")
    
    return {
        'statusCode': 200,
        'body': json.dumps('Message processed')
    }

def send_to_client(connection_id, message, url=None):
    """ Send a message to a specific WebSocket connection. """
    client = boto3.client(
        'apigatewaymanagementapi',
        endpoint_url=url or websocket_endpoint_url
    )
    try:
        client.post_to_connection(
            ConnectionId=connection_id,
            Data=message
        )
        logging.debug(f"Sent message to {connection_id}: {message}")
    except client.exceptions.GoneException:
        logging.error(f"Connection {connection_id} is no longer available.")
    except ClientError as e:
        logging.error(f"Failed to send message to {connection_id}: {e}")
