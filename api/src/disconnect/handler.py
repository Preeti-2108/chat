import json
import logging
import os
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)
logger.setLevel(os.getenv('LOG_LEVEL', 'INFO'))

# Define status codes for various outcomes
STATUS_DISCONNECTED = 200

def disconnect(event, context):
    """
    Handles the disconnection event for a WebSocket client with cleanup.

    This function is triggered when a client disconnects from the WebSocket.
    It cleans up connection information stored in DynamoDB during connection.

    Parameters:
    event (dict): Contains information about the disconnection event, including
                  the connection ID and other relevant metadata.
    context (object): Provides runtime information about the Lambda function execution.

    Returns:
    dict: A response object with a status code and a message body indicating the 
          disconnection was processed successfully.
    """
    
    connection_id = event.get('requestContext', {}).get('connectionId')
    logger.info(f"WebSocket disconnection from: {connection_id}")
    
    try:
        # Clean up connection information from DynamoDB if we're tracking connections
        _cleanup_connection_info(connection_id)
        
        logger.info(f"WebSocket disconnection processed successfully for: {connection_id}")
        
        return {
            "statusCode": STATUS_DISCONNECTED,
            "body": json.dumps({
                "message": "Disconnected successfully"
            })
        }
        
    except Exception as e:
        logger.error(f"Error during disconnection cleanup for {connection_id}: {str(e)}")
        # Still return success since the client is disconnecting anyway
        return {
            "statusCode": STATUS_DISCONNECTED,
            "body": json.dumps({
                "message": "Disconnected"
            })
        }

def _cleanup_connection_info(connection_id: str):
    """
    Clean up connection information from DynamoDB.
    
    Args:
        connection_id: WebSocket connection ID to clean up
    """
    try:
        connections_table_name = os.getenv('CONNECTIONS_TABLE')
        if not connections_table_name:
            logger.info("CONNECTIONS_TABLE environment variable not set - skipping connection cleanup")
            return
            
        if not connection_id:
            logger.warning("Connection ID is empty - skipping connection cleanup")
            return
            
        dynamodb = boto3.resource('dynamodb')
        connections_table = dynamodb.Table(connections_table_name)
        
        # Remove the connection record
        connections_table.delete_item(
            Key={'connectionId': connection_id}
        )
        
        logger.info(f"Connection info cleaned up for: {connection_id}")
        
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceNotFoundException':
            logger.info(f"Connections table {connections_table_name} not found - skipping cleanup")
        else:
            logger.warning(f"Failed to cleanup connection info for {connection_id}: {str(e)}")
    except Exception as e:
        logger.warning(f"Failed to cleanup connection info for {connection_id}: {str(e)}")