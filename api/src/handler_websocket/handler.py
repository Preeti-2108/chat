# Import necessary libraries for handling JSON, UUIDs, AWS services, environment variables, and logging
import json
import uuid
import boto3
import os
import logging
from botocore.exceptions import ClientError
from jwt import PyJWKClient, decode as jwt_decode, InvalidTokenError, PyJWKError
from src.helpers.security.url_validator import validate_and_get_url, is_allowed_url

# Configure logging to display debug-level messages
logging.basicConfig(level=logging.DEBUG)

# Define status codes for various outcomes
STATUS_ERROR = 500
STATUS_UNAUTHORIZED = 401
STATUS_SUCCESS = 200
STATUS_UNSUPPORTED = 400

# Initialize AWS DynamoDB resource
dynamodb = boto3.resource('dynamodb')

# Retrieve environment variables for configuration
connection_table_name = os.getenv('TABLE')  # DynamoDB table name for storing connections
user_pool_id = os.getenv('COGNITO_POOL_ID')  # Cognito User Pool ID for JWT validation
region = os.getenv('REGION')  # AWS region for service endpoints
websocket_endpoint_url = os.getenv('WEBSOCKET_ENDPOINT_URL')  # WebSocket endpoint URL

# Ensure the connection table name is set in the environment
if not connection_table_name:
    raise ValueError("Environment variable TABLE is not set.")

# Reference to the DynamoDB table for storing WebSocket connection details
table_connection = dynamodb.Table(connection_table_name)

# Construct the JWKS URL for the Cognito User Pool to fetch public keys for JWT validation
jwks_url = f'https://cognito-idp.{region}.amazonaws.com/{user_pool_id}/.well-known/jwks.json'
jwks_client = PyJWKClient(jwks_url)

def validate_access_token(access_token):
    """ 
    Validate the provided JWT access token using the Cognito User Pool's JWKS.
    
    Args:
        access_token (str): The JWT access token to validate.
    
    Returns:
        str or None: The scope from the token if valid, otherwise None.
    """
    try:
        # Retrieve the signing key from the JWKS using the token
        signing_key = jwks_client.get_signing_key_from_jwt(access_token)
        
        # Decode the token using the signing key and RS256 algorithm
        decoded_token = jwt_decode(
            access_token,
            signing_key.key,
            algorithms=["RS256"]
        )
        
        # Extract the scope from the decoded token payload
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
    """ 
    Handle a new client connection to the WebSocket.
    
    Args:
        event (dict): The event data from the API Gateway.
        context (object): The runtime information of the Lambda function.
    
    Returns:
        dict: The response object with status code and message.
    """
    # Extract the access token from query parameters
    access_token = event.get('queryStringParameters', {}).get('access_token')
    if not access_token:
        return {
            'statusCode': STATUS_UNSUPPORTED,
            'body': json.dumps('Missing access_token in query parameters')
        }
    
    # Validate the access token and retrieve the scope
    scope = validate_access_token(access_token)
    if not scope:
        return {
            'statusCode': STATUS_UNAUTHORIZED,
            'body': json.dumps('Invalid or missing access_token')
        }
    
    # Get the connection ID from the request context
    connection_id = event['requestContext']['connectionId']
    try:
        # Store the connection details in the DynamoDB table
        table_connection.put_item(
            Item={
                'id': str(uuid.uuid4()),  # Generate a unique ID for the connection
                'connectionId': connection_id,
                'scope': scope
            }
        )
        logging.info(f"Connection ID {connection_id} and scope {scope} saved in {connection_table_name}.")
    except ClientError as e:
        logging.error(f"Error storing connection details: {e}")
        return {
            'statusCode': STATUS_ERROR,
            'body': json.dumps('Error storing connection details')
        }
    
    return {
        'statusCode': STATUS_SUCCESS,
        'body': json.dumps('Connected')
    }

def disconnect(event, context):
    """ 
    Handle client disconnection from the WebSocket.
    
    Args:
        event (dict): The event data from the API Gateway.
        context (object): The runtime information of the Lambda function.
    
    Returns:
        dict: The response object with status code and message.
    """
    # Get the connection ID from the request context
    connection_id = event['requestContext']['connectionId']
    logging.info(f"Connection ID {connection_id} disconnected.")
    
    try:
        # Remove the connection details from the DynamoDB table
        table_connection.delete_item(
            Key={'connectionId': connection_id}
        )
        logging.info("Connection ID removed successfully.")
    except ClientError as e:
        logging.error(f"Error removing connection details: {e}")
        return {
            'statusCode': STATUS_ERROR,
            'body': json.dumps('Error removing connection details')
        }
    
    return {
        'statusCode': STATUS_SUCCESS,
        'body': json.dumps('Disconnected')
    }

def defaultMessage(event, context):
    """ 
    Handle receiving a message from a WebSocket client.
    
    Args:
        event (dict): The event data from the API Gateway.
        context (object): The runtime information of the Lambda function.
    
    Returns:
        dict: The response object with status code and message.
    """
    logging.debug(f"Received event: {event}")
    
    # Get the connection ID from the request context
    connection_id = event['requestContext']['connectionId']
    
    # Parse the message body from the event
    body = json.loads(event.get('body', '{}'))  # Ensure body is loaded as JSON
    
    # Check if the message is present in the body
    if 'message' not in body:
        return {
            'statusCode': STATUS_UNSUPPORTED,
            'body': json.dumps('Invalid message format')
        }
    
    logging.debug(f"Received message from {connection_id}: {body}")
    
    # Echo the received message back to the client
    send_to_client(connection_id, f"Echo: {body['message']}")
    
    return {
        'statusCode': STATUS_SUCCESS,
        'body': json.dumps('Message processed')
    }

def send_to_client(connection_id, message, url=None):
    """ 
    Send a message to a specific WebSocket connection.
    
    Args:
        connection_id (str): The ID of the WebSocket connection.
        message (str): The message to send to the client.
        url (str, optional): The WebSocket endpoint URL. Defaults to the configured endpoint.
    """
    # Use provided URL or fall back to configured endpoint
    try:
        validated_url = validate_and_get_url(url, fallback_url=websocket_endpoint_url)
    except ValueError as e:
        logging.error(f"SSRF protection: {str(e)}")
        validated_url = websocket_endpoint_url
        if not validated_url:
            logging.error("No valid WebSocket endpoint URL available")
            raise ValueError("No valid WebSocket endpoint URL available")
    
    # Initialize the API Gateway Management API client
    client = boto3.client(
        'apigatewaymanagementapi',
        endpoint_url=validated_url
    )
    try:
        # Post the message to the specified WebSocket connection
        client.post_to_connection(
            ConnectionId=connection_id,
            Data=message
        )
        logging.debug(f"Sent message to {connection_id}: {message}")
    except client.exceptions.GoneException:
        logging.error(f"Connection {connection_id} is no longer available.")
    except ClientError as e:
        logging.error(f"Failed to send message to {connection_id}: {e}")