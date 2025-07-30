"""
Scope Management Module

This module provides utilities for managing and validating JWT scopes for API access control.
It includes decorators and functions to check user permissions based on scopes.
"""

import logging
import os
from typing import List, Dict, Any, Optional, Union, Callable
from functools import wraps
from src.helpers.cognito_auth import extract_scopes_from_token, validate_scopes, has_scope_permission, get_user_permissions

logger = logging.getLogger(__name__)
logger.setLevel(os.getenv('LOG_LEVEL', 'INFO'))

class ScopeValidationError(Exception):
    """Custom exception for scope validation errors."""
    pass

def require_scopes(required_scopes: Union[str, List[str]], require_all: bool = False):
    """
    Decorator to require specific scopes for WebSocket handlers.
    
    Args:
        required_scopes: Single scope string or list of scope strings required
        require_all: If True, user must have ALL required scopes. If False, user must have at least ONE.
        
    Returns:
        Decorated function that validates scopes before execution
    """
    def decorator(handler_func: Callable) -> Callable:
        @wraps(handler_func)
        def wrapper(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
            # Get user info from authenticated event
            auth_info = event.get('auth', {})
            if not auth_info.get('is_authenticated'):
                raise ScopeValidationError("Authentication required for scope validation")
            
            user_info = auth_info.get('user_info', {})
            user_scopes = user_info.get('scopes', [])
            
            # Convert single scope to list
            scopes_to_check = [required_scopes] if isinstance(required_scopes, str) else required_scopes
            
            # Validate scopes
            if not validate_scopes(user_scopes, scopes_to_check, require_all):
                logger.warning(f"User {user_info.get('username')} missing required scopes: {scopes_to_check}")
                raise ScopeValidationError(f"Insufficient permissions. Required scopes: {scopes_to_check}")
            
            logger.info(f"User {user_info.get('username')} has required scopes: {scopes_to_check}")
            
            # Call the original handler
            return handler_func(event, context)
        
        return wrapper
    return decorator

def require_resource_permission(resource: str, action: str):
    """
    Decorator to require specific resource permission for WebSocket handlers.
    
    Args:
        resource: The resource name (e.g., 'TEMPLATE', 'RECIPIENTS')
        action: The action (e.g., 'CREATE', 'READ', 'UPDATE', 'DELETE')
        
    Returns:
        Decorated function that validates resource permissions before execution
    """
    def decorator(handler_func: Callable) -> Callable:
        @wraps(handler_func)
        def wrapper(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
            # Get user info from authenticated event
            auth_info = event.get('auth', {})
            if not auth_info.get('is_authenticated'):
                raise ScopeValidationError("Authentication required for scope validation")
            
            user_info = auth_info.get('user_info', {})
            user_scopes = user_info.get('scopes', [])
            
            # Check resource permission
            if not has_scope_permission(user_scopes, resource, action):
                logger.warning(f"User {user_info.get('username')} denied access to {resource}.{action}")
                raise ScopeValidationError(f"Insufficient permissions for {resource}.{action}")
            
            logger.info(f"User {user_info.get('username')} granted access to {resource}.{action}")
            
            # Call the original handler
            return handler_func(event, context)
        
        return wrapper
    return decorator

def get_user_scopes(event: Dict[str, Any]) -> List[str]:
    """
    Get the authenticated user's scopes from the event.
    
    Args:
        event: The WebSocket event (should be processed by authenticate_websocket decorator)
        
    Returns:
        List of user scopes
    """
    auth_info = event.get('auth', {})
    if auth_info.get('is_authenticated'):
        user_info = auth_info.get('user_info', {})
        return user_info.get('scopes', [])
    return []

def has_any_scope(event: Dict[str, Any], scopes: List[str]) -> bool:
    """
    Check if the authenticated user has any of the specified scopes.
    
    Args:
        event: The WebSocket event (should be processed by authenticate_websocket decorator)
        scopes: List of scopes to check
        
    Returns:
        True if user has at least one of the specified scopes, False otherwise
    """
    user_scopes = get_user_scopes(event)
    return validate_scopes(user_scopes, scopes, require_all=False)

def has_all_scopes(event: Dict[str, Any], scopes: List[str]) -> bool:
    """
    Check if the authenticated user has all of the specified scopes.
    
    Args:
        event: The WebSocket event (should be processed by authenticate_websocket decorator)
        scopes: List of scopes to check
        
    Returns:
        True if user has all of the specified scopes, False otherwise
    """
    user_scopes = get_user_scopes(event)
    return validate_scopes(user_scopes, scopes, require_all=True)

def has_resource_permission(event: Dict[str, Any], resource: str, action: str) -> bool:
    """
    Check if the authenticated user has permission for a specific resource and action.
    
    Args:
        event: The WebSocket event (should be processed by authenticate_websocket decorator)
        resource: The resource name (e.g., 'TEMPLATE', 'RECIPIENTS')
        action: The action (e.g., 'CREATE', 'READ', 'UPDATE', 'DELETE')
        
    Returns:
        True if user has permission, False otherwise
    """
    user_scopes = get_user_scopes(event)
    return has_scope_permission(user_scopes, resource, action)

def get_user_resource_permissions(event: Dict[str, Any]) -> Dict[str, List[str]]:
    """
    Get all resource permissions for the authenticated user.
    
    Args:
        event: The WebSocket event (should be processed by authenticate_websocket decorator)
        
    Returns:
        Dict with resources as keys and list of actions as values
    """
    user_scopes = get_user_scopes(event)
    return get_user_permissions(user_scopes)

def check_scope_manually(event: Dict[str, Any], required_scopes: Union[str, List[str]], require_all: bool = False) -> Dict[str, Any]:
    """
    Manual scope validation for handlers that don't use the decorator.
    
    Args:
        event: The WebSocket event
        required_scopes: Single scope string or list of scope strings required
        require_all: If True, user must have ALL required scopes. If False, user must have at least ONE.
        
    Returns:
        Dict with validation result
    """
    try:
        auth_info = event.get('auth', {})
        if not auth_info.get('is_authenticated'):
            return {
                'success': False,
                'error': 'Authentication required for scope validation'
            }
        
        user_info = auth_info.get('user_info', {})
        user_scopes = user_info.get('scopes', [])
        
        # Convert single scope to list
        scopes_to_check = [required_scopes] if isinstance(required_scopes, str) else required_scopes
        
        # Validate scopes
        if not validate_scopes(user_scopes, scopes_to_check, require_all):
            return {
                'success': False,
                'error': f'Insufficient permissions. Required scopes: {scopes_to_check}',
                'user_scopes': user_scopes,
                'required_scopes': scopes_to_check
            }
        
        return {
            'success': True,
            'user_scopes': user_scopes,
            'required_scopes': scopes_to_check
        }
        
    except Exception as e:
        logger.error(f"Manual scope validation failed: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }

def filter_data_by_scope(event: Dict[str, Any], data: List[Dict[str, Any]], 
                        resource_field: str, action: str = 'READ') -> List[Dict[str, Any]]:
    """
    Filter data based on user's scope permissions.
    
    Args:
        event: The WebSocket event (should be processed by authenticate_websocket decorator)
        data: List of data items to filter
        resource_field: Field in each data item that contains the resource type
        action: The action to check permission for (default: 'READ')
        
    Returns:
        Filtered list of data items that the user has permission to access
    """
    user_scopes = get_user_scopes(event)
    filtered_data = []
    
    for item in data:
        resource = item.get(resource_field)
        if resource and has_scope_permission(user_scopes, resource, action):
            filtered_data.append(item)
    
    return filtered_data

def get_scope_error_response(required_scopes: Union[str, List[str]], user_scopes: List[str] = None) -> Dict[str, Any]:
    """
    Generate a standardized error response for scope validation failures.
    
    Args:
        required_scopes: The scopes that were required
        user_scopes: The scopes that the user actually has (optional)
        
    Returns:
        Dict containing error response
    """
    scopes_list = [required_scopes] if isinstance(required_scopes, str) else required_scopes
    
    error_response = {
        'error': 'Insufficient permissions',
        'error_code': 'SCOPE_VALIDATION_FAILED',
        'required_scopes': scopes_list,
        'message': f'This operation requires the following scopes: {", ".join(scopes_list)}'
    }
    
    if user_scopes is not None:
        error_response['user_scopes'] = user_scopes
    
    return error_response
