"""
WebSocket URL Validation Helper

This module provides security functions to validate WebSocket URLs against a whitelist
of allowed hosts to prevent Server-Side Request Forgery (SSRF) attacks.
"""

import os
import logging
from urllib.parse import urlparse
from typing import List, Optional

logger = logging.getLogger(__name__)

def is_subdomain(host: str, allowed: str) -> bool:
    """
    Check if host is the same as allowed domain or a legitimate subdomain.
    
    This prevents domain hijacking attacks like:
    - allowed.com.evil.com ❌ 
    - evil-allowed.com ❌
    
    But allows legitimate subdomains:
    - allowed.com ✅
    - api.allowed.com ✅
    - sub.api.allowed.com ✅
    
    Args:
        host (str): The hostname to check
        allowed (str): The allowed domain
        
    Returns:
        bool: True if host is same as allowed or legitimate subdomain
    """
    return host == allowed or host.endswith("." + allowed)

def get_allowed_websocket_hosts() -> List[str]:
    """
    Retrieve the list of allowed WebSocket hosts from environment variables.
    
    Returns:
        List[str]: List of allowed exact domain names (no wildcards)
    """
    # Get allowed hosts from environment variable
    allowed_hosts_env = os.getenv('ALLOWED_WEBSOCKET_HOSTS', '')
    
    if not allowed_hosts_env:
        # Fallback to empty list - no default hosts for security
        logger.error("ALLOWED_WEBSOCKET_HOSTS not set. No WebSocket URLs will be allowed.")
        logger.error("Please configure ALLOWED_WEBSOCKET_HOSTS with exact domains like:")
        logger.error("ALLOWED_WEBSOCKET_HOSTS=execute-api.ap-south-1.amazonaws.com,api.deepgram.com")
        return []
    
    # Split by comma and strip whitespace
    allowed_hosts = [host.strip() for host in allowed_hosts_env.split(',') if host.strip()]
    
    # Validate that no wildcards or patterns are used
    for host in allowed_hosts:
        if '*' in host or '.' in host.split('.')[0] or host.startswith('.'):
            logger.error(f"Invalid host pattern '{host}'. Only exact domains allowed, no wildcards.")
    
    # Filter out any invalid patterns
    valid_hosts = [host for host in allowed_hosts if '*' not in host and not host.startswith('.')]
    
    logger.info(f"Loaded {len(valid_hosts)} allowed WebSocket hosts from environment")
    return valid_hosts

def is_allowed_websocket_url(url: str) -> bool:
    """
    Validate if a WebSocket URL is allowed based on exact domain matching.
    
    This follows AWS/Stripe/OpenAI security standards:
    - Only exact domain matches allowed
    - No wildcards or pattern matching
    - No substring matching
    
    Args:
        url (str): The WebSocket URL to validate
        
    Returns:
        bool: True if the URL hostname exactly matches an allowed domain, False otherwise
    """
    if not url:
        logger.error("Empty URL provided for validation")
        return False
    
    try:
        parsed_url = urlparse(url)
        
        # Ensure the URL uses HTTPS (wss:// URLs are converted to https:// by urlparse)
        if parsed_url.scheme not in ('https', 'wss'):
            logger.error(f"Invalid URL scheme: {parsed_url.scheme}. Only HTTPS/WSS URLs are allowed")
            return False
        
        hostname = parsed_url.hostname
        if not hostname:
            logger.error(f"No hostname found in URL: {url}")
            return False
        
        allowed_hosts = get_allowed_websocket_hosts()
        
        # SECURITY: Subdomain-safe matching - prevents domain hijacking attacks
        for allowed_domain in allowed_hosts:
            if is_subdomain(hostname, allowed_domain):
                logger.info(f"URL {url} allowed - hostname '{hostname}' matches allowed domain '{allowed_domain}'")
                return True
        
        logger.error(f"URL {url} REJECTED. Hostname '{hostname}' not allowed by any domain in whitelist: {allowed_hosts}")
        logger.error("Only exact domains and legitimate subdomains allowed. Configure ALLOWED_WEBSOCKET_HOSTS with base domains.")
        return False
        
    except Exception as e:
        logger.error(f"Error parsing URL {url}: {str(e)}")
        return False

def validate_websocket_url(url: Optional[str]) -> Optional[str]:
    """
    Validate and return a WebSocket URL if it's allowed, or None if not.
    
    Args:
        url (Optional[str]): The WebSocket URL to validate
        
    Returns:
        Optional[str]: The validated URL if allowed, None otherwise
        
    Raises:
        SecurityError: If the URL is not allowed (SSRF protection)
    """
    if not url:
        return None
    
    if is_allowed_websocket_url(url):
        return url
    else:
        error_msg = f"WebSocket URL '{url}' is not allowed. This may be a security risk (SSRF attack attempt)."
        logger.error(error_msg)
        raise SecurityError(error_msg)

class SecurityError(Exception):
    """Custom exception for security-related errors"""
    pass

def get_secure_websocket_url(event_domain: str, event_stage: str) -> Optional[str]:
    """
    Construct and validate a WebSocket URL from event components.
    
    This is the recommended secure way to construct WebSocket URLs
    instead of trusting client-provided URLs.
    
    Args:
        event_domain (str): Domain from the request context
        event_stage (str): Stage from the request context
        
    Returns:
        Optional[str]: Validated WebSocket URL or None if invalid
    """
    if not event_domain or not event_stage:
        logger.error("Missing domain or stage information for WebSocket URL construction")
        return None
    
    # Construct URL using server-side components only
    constructed_url = f'https://{event_domain}/{event_stage}'
    
    try:
        return validate_websocket_url(constructed_url)
    except SecurityError as e:
        logger.error(f"Constructed URL failed validation: {e}")
        return None