"""
WebSocket Authentication Middleware

This module provides authentication middleware for WebSocket connections using Cognito JWT tokens.
It includes decorators and utilities to secure WebSocket handlers.
"""

import json
import logging
import os
from functools import wraps
from typing import Dict, Any, Callable, Optional
from src.helpers.cognito_auth import validate_cognito_token, extract_token_from_event
from src.helpers.api_responses import Responses
from src.helpers.construct_response import construct_response
from src.handler_websocket.handler import send_to_client
from src.helpers.event_utils import extract_event_info

logger = logging.getLogger(__name__)
logger.setLevel(os.getenv('LOG_LEVEL', 'INFO'))

class AuthenticationError(Exception):
    """Custom exception for authentication errors."""
    pass

def authenticate_websocket(required_groups: Optional[list] = None):
    """
    Decorator to authenticate WebSocket requests using Cognito JWT tokens.
    
    Args:
        required_groups: Optional list of Cognito groups required for access
        
    Returns:
        Decorated function that validates authentication before execution
    """
    def decorator(handler_func: Callable) -> Callable:
        @wraps(handler_func)
        def wrapper(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
            # Extract connection info for error responses
            event_info = extract_event_info(event)
            connection_id = event_info.get('connectionId')
            url = event_info.get('url')
            
            try:
                # Extract and validate the JWT token
                token = extract_token_from_event(event)
                if not token:
                    logger.warning("No authentication token provided")
                    return _send_auth_error(
                        connection_id, 
                        url, 
                        "Authentication required. Please provide a valid JWT token.",
                        401
                    )
                
                # Validate the token
                auth_result = validate_cognito_token(token)
                user_info = auth_result['user_info']
                decoded_token = auth_result['decoded_token']
                
                logger.info(f"User authenticated: {user_info.get('username')} (ID: {user_info.get('user_id')})")
                
                # Check group membership if required
                if required_groups:
                    user_groups = user_info.get('groups', [])
                    if not any(group in user_groups for group in required_groups):
                        logger.warning(f"User {user_info.get('username')} does not have required group membership")
                        return _send_auth_error(
                            connection_id,
                            url,
                            "Insufficient permissions. Required group membership not found.",
                            403
                        )
                
                # Add authentication info to the event for the handler to use
                event['auth'] = {
                    'user_info': user_info,
                    'decoded_token': decoded_token,
                    'is_authenticated': True
                }
                
                # Call the original handler
                return handler_func(event, context)
                
            except Exception as e:
                logger.error(f"Authentication failed: {str(e)}")
                return _send_auth_error(
                    connection_id,
                    url,
                    f"Authentication failed: {str(e)}",
                    401
                )
        
        return wrapper
    return decorator

def _send_auth_error(connection_id: Optional[str], url: Optional[str], message: str, status_code: int) -> Dict[str, Any]:
    """
    Send an authentication error response via WebSocket.
    
    Args:
        connection_id: WebSocket connection ID
        url: WebSocket URL
        message: Error message
        status_code: HTTP status code
        
    Returns:
        Error response dictionary
    """
    if connection_id and url:
        response_result = Responses.result_response(status_code, False, message)
        try:
            send_to_client(connection_id, json.dumps(construct_response(response_result)), url)
        except Exception as e:
            logger.error(f"Failed to send auth error to client: {str(e)}")
    
    return {
        'statusCode': status_code,
        'body': json.dumps({'error': message})
    }

def get_authenticated_user(event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Get the authenticated user information from the event.
    
    Args:
        event: The WebSocket event (should be processed by authenticate_websocket decorator)
        
    Returns:
        User information if authenticated, None otherwise
    """
    auth_info = event.get('auth', {})
    if auth_info.get('is_authenticated'):
        return auth_info.get('user_info')
    return None

def get_user_email(event: Dict[str, Any]) -> Optional[str]:
    """
    Get the authenticated user's email from the event.
    
    Args:
        event: The WebSocket event (should be processed by authenticate_websocket decorator)
        
    Returns:
        User email if authenticated, None otherwise
    """
    user_info = get_authenticated_user(event)
    if user_info:
        return user_info.get('email')
    return None

def get_user_id(event: Dict[str, Any]) -> Optional[str]:
    """
    Get the authenticated user's ID from the event.
    
    Args:
        event: The WebSocket event (should be processed by authenticate_websocket decorator)
        
    Returns:
        User ID if authenticated, None otherwise
    """
    user_info = get_authenticated_user(event)
    if user_info:
        return user_info.get('user_id')
    return None

def get_username(event: Dict[str, Any]) -> Optional[str]:
    """
    Get the authenticated user's username from the event.
    
    Args:
        event: The WebSocket event (should be processed by authenticate_websocket decorator)
        
    Returns:
        Username if authenticated, None otherwise
    """
    user_info = get_authenticated_user(event)
    if user_info:
        return user_info.get('username')
    return None

def has_group(event: Dict[str, Any], group_name: str) -> bool:
    """
    Check if the authenticated user belongs to a specific group.
    
    Args:
        event: The WebSocket event (should be processed by authenticate_websocket decorator)
        group_name: The name of the group to check
        
    Returns:
        True if user belongs to the group, False otherwise
    """
    user_info = get_authenticated_user(event)
    if user_info:
        user_groups = user_info.get('groups', [])
        return group_name in user_groups
    return False

def require_authentication(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Manual authentication check for handlers that don't use the decorator.
    
    Args:
        event: The WebSocket event
        
    Returns:
        Authentication result with user info or error response
    """
    try:
        token = extract_token_from_event(event)
        if not token:
            raise AuthenticationError("No authentication token provided")
        
        auth_result = validate_cognito_token(token)
        return {
            'success': True,
            'user_info': auth_result['user_info'],
            'decoded_token': auth_result['decoded_token']
        }
    except Exception as e:
        logger.error(f"Manual authentication check failed: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }
