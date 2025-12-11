import json
import logging
import os
from src.helpers.auth_middleware import authenticate_websocket
from src.helpers.api_responses import Responses

logger = logging.getLogger(__name__)
logger.setLevel(os.getenv('LOG_LEVEL', 'INFO'))

# Define status codes
STATUS_ERROR = 500
STATUS_SUCCESS = 200
@authenticate_websocket()  # Require authentication for this handler
def send_message(event, context):
    """
    Handles the sending of a message triggered by an authenticated WebSocket event.
    
    This function is typically invoked in response to an authenticated WebSocket event.
    It processes the event and returns a response indicating the status of the message 
    sending operation.
    
    Parameters:
    event (dict): A dictionary containing event data, including authentication info.
    context (object): An object providing runtime information about the function execution.
    
    Returns:
    dict: A dictionary containing the HTTP status code and a message body.
    """
    
    try:
        # Get authenticated user info from the event (added by middleware)
        user_info = event.get('auth', {}).get('user_info', {})
        username = user_info.get('username', 'unknown')
        
        logger.info("Message send request from authenticated user")
        
        # Here you would implement your message sending logic
        # For example: send to other WebSocket connections, queue processing, etc.
        
        return {
            "statusCode": STATUS_SUCCESS,
            "body": json.dumps({
                "message": "Message sent successfully",
                "sender": username
            })
        }
        
    except Exception as e:
        logger.error(f"Error sending message: {str(e)}")
        return {
            "statusCode": STATUS_ERROR,
            "body": json.dumps({
                "error": "Failed to send message",
                "message": str(e)
            })
        }