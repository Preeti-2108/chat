import json
import logging
import os
import boto3
import time
from botocore.exceptions import ClientError
from src.helpers.cognito_auth import extract_token_from_event, validate_cognito_token
from src.helpers.api_responses import Responses

logger = logging.getLogger(__name__)
logger.setLevel(os.getenv('LOG_LEVEL', 'INFO'))

# Define status codes for various outcomes
STATUS_ERROR = 500
STATUS_CONNECTED = 200
STATUS_UNAUTHORIZED = 401

def connect(event, context, token=None):
    """
    Handles the WebSocket connection event with Cognito JWT authentication.

    This function is triggered when a client attempts to establish a WebSocket connection.
    It validates the JWT token provided by the client and stores connection information
    in DynamoDB for authenticated users.

    Parameters:
    event (dict): Contains information about the WebSocket connection request, including
                  query string parameters, headers, and connection context.
    context (object): Provides runtime information about the function execution.
    token (str): Optional JWT token parameter. If not provided, token will be extracted from event.

    Returns:
    dict: A dictionary representing an HTTP response with a status code and message body.
          Returns 200 for successful authenticated connections, 401 for authentication failures.
    """
    
    connection_id = event.get('requestContext', {}).get('connectionId')
    logger.info(f"WebSocket connection attempt from: {connection_id}")
    
    try:
        # Extract JWT token from the connection request or use provided token parameter
        if token is None:
            token = extract_token_from_event(event)
        
        if not token:
            warning_message = f"Connection {connection_id} attempted without authentication token"
            logger.warning(warning_message)
            return {
                "statusCode": STATUS_UNAUTHORIZED,
                "body": json.dumps({
                    "error": "Authentication required",
                    "message": "Please provide a valid JWT token in query parameters or headers",
                    "warning": warning_message
                })
            }
        
        # Validate the Cognito JWT token
        try:
            auth_result = validate_cognito_token(token)
            user_info = auth_result['user_info']
            
            logger.info(f"User authenticated: {user_info.get('username')} (ID: {user_info.get('user_id')})")
            
            # Store connection information in DynamoDB (optional)
            # This allows you to track active connections and send targeted messages
            _store_connection_info(connection_id, user_info, token, context)
            
            logger.info(f"WebSocket connection established successfully for user: {user_info.get('username')}")
            
            return {
                "statusCode": STATUS_CONNECTED,
                "body": json.dumps({
                    "message": "Connected successfully",
                    "user": {
                        "username": user_info.get('username'),
                        "email": user_info.get('email'),
                        "user_id": user_info.get('user_id')
                    }
                })
            }
            
        except Exception as auth_error:
            logger.error(f"Authentication failed for connection {connection_id}: {str(auth_error)}")
            return {
                "statusCode": STATUS_UNAUTHORIZED,
                "body": json.dumps({
                    "error": "Authentication failed",
                    "message": str(auth_error)
                })
            }
            
    except Exception as e:
        logger.error(f"Unexpected error during connection for {connection_id}: {str(e)}")
        return {
            "statusCode": STATUS_ERROR,
            "body": json.dumps({
                "error": "Internal server error",
                "message": "Failed to establish connection"
            })
        }

def _store_connection_info(connection_id: str, user_info: dict, token: str, context):
    """
    Store connection information in DynamoDB for tracking active connections.
    
    Args:
        connection_id: WebSocket connection ID
        user_info: Authenticated user information
        token: JWT token (store only if needed for later validation)
        context: Lambda context
    """
    try:
        # Optional: Store connection info in a separate DynamoDB table for connection tracking
        # This is useful if you need to send messages to specific users or track active sessions
        
        connections_table_name = os.getenv('CONNECTIONS_TABLE')
        if not connections_table_name:
            logger.info("CONNECTIONS_TABLE environment variable not set - skipping connection storage")
            return
            
        dynamodb = boto3.resource('dynamodb')
        connections_table = dynamodb.Table(connections_table_name)
        
        current_time = int(time.time())
        
        # Store connection with user info
        connections_table.put_item(
            Item={
                'connectionId': connection_id,
                'userId': user_info.get('user_id'),
                'username': user_info.get('username'),
                'email': user_info.get('email'),
                'groups': user_info.get('groups', []),
                'connectedAt': current_time,
                'ttl': current_time + (24 * 60 * 60)  # 24 hours TTL
            }
        )
        
        logger.info(f"Connection info stored for user: {user_info.get('username')}")
        
    except Exception as e:
        # Log the error but don't fail the connection
        logger.warning(f"Failed to store connection info: {str(e)}")
        pass