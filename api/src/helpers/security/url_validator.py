"""
URL validation utility to prevent SSRF (Server-Side Request Forgery) attacks.

This module provides functions to validate WebSocket endpoint URLs against
a whitelist of allowed hosts to prevent attackers from redirecting requests
to malicious servers.
"""
import os
import logging
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

ALLOWED_HOSTS_ENV = os.getenv('ALLOWED_WEBSOCKET_HOSTS', '')
ALLOWED_HOSTS = [host.strip() for host in ALLOWED_HOSTS_ENV.split(',') if host.strip()]

WEBSOCKET_ENDPOINT_URL = os.getenv('WEBSOCKET_ENDPOINT_URL')
if WEBSOCKET_ENDPOINT_URL:
    parsed = urlparse(WEBSOCKET_ENDPOINT_URL)
    if parsed.hostname:
        host_with_protocol = f"{parsed.scheme}://{parsed.hostname}"
        if host_with_protocol not in ALLOWED_HOSTS:
            ALLOWED_HOSTS.append(host_with_protocol)
        if parsed.hostname not in ALLOWED_HOSTS:
            ALLOWED_HOSTS.append(parsed.hostname)

# Default allowed host - Azure API Management endpoint
# This can be overridden via DEFAULT_ALLOWED_WEBSOCKET_HOST environment variable
DEFAULT_ALLOWED_HOST = os.getenv('DEFAULT_ALLOWED_WEBSOCKET_HOST', 'apiportal1689852356.azure-api.net')
if DEFAULT_ALLOWED_HOST and DEFAULT_ALLOWED_HOST not in ALLOWED_HOSTS:
    # Add both with and without protocol for flexibility
    if not DEFAULT_ALLOWED_HOST.startswith(('ws://', 'wss://')):
        # Add without protocol
        ALLOWED_HOSTS.append(DEFAULT_ALLOWED_HOST)
        # Also add with wss:// protocol
        ALLOWED_HOSTS.append(f'wss://{DEFAULT_ALLOWED_HOST}')
    else:
        ALLOWED_HOSTS.append(DEFAULT_ALLOWED_HOST)

def is_allowed_url(url: str) -> bool:
    """
    Check if a URL is in the whitelist of allowed hosts.
    
    This function validates that the URL's host matches one of the allowed hosts
    to prevent SSRF attacks where an attacker could redirect requests to
    malicious servers.
    
    Args:
        url (str): The URL to validate
        
    Returns:
        bool: True if the URL is allowed, False otherwise
    """
    if not url:
        logger.warning("Empty URL provided for validation")
        return False
    
    try:
        # Parse the URL to extract the host
        parsed = urlparse(url)
        hostname = parsed.hostname
        
        if not hostname:
            logger.warning(f"Invalid URL format: {url} - no hostname found")
            return False
        
        # Check if the hostname matches any allowed host
        # We check both the full URL (with protocol) and just the hostname
        url_with_protocol = f"{parsed.scheme}://{hostname}" if parsed.scheme else hostname
        
        # Check against whitelist
        for allowed in ALLOWED_HOSTS:
            if not allowed:
                continue
                
            # Remove protocol from allowed host for comparison if present
            allowed_clean = allowed.replace('wss://', '').replace('ws://', '').strip()
            
            # Check if hostname matches (exact match only - no subdomain matching for security)
            if hostname == allowed_clean:
                logger.debug(f"URL {url} is allowed (exact match with {allowed})")
                return True
        
        logger.warning(f"URL {url} is not in the allowed hosts whitelist.")
        return False
        
    except Exception as e:
        logger.error(f"Error validating URL {url}: {str(e)}")
        return False


def validate_and_get_url(url: str, fallback_url: str = None) -> str:
    """
    Validate a URL and return it if allowed, otherwise return the fallback URL.
    
    This is a convenience function that validates a URL and falls back to
    a safe default if the provided URL is not allowed.
    
    Args:
        url (str): The URL to validate
        fallback_url (str, optional): The fallback URL to use if validation fails
        
    Returns:
        str: The validated URL if allowed, otherwise the fallback URL
    """
    if url and is_allowed_url(url):
        return url
    
    if fallback_url:
        logger.info(f"Using fallback URL: {fallback_url}")
        return fallback_url
    
    # If no fallback and URL is not allowed, raise an error
    raise ValueError(f"Unauthorized WebSocket URL: {url}. URL must be in the allowed hosts whitelist.")