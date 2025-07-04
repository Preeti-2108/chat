"""
Amazon Cognito JWT Token Authentication Helper

This module provides utilities for validating JWT tokens issued by Amazon Cognito.
It includes functions to verify token signatures, extract user information, and validate token claims.
"""

import json
import jwt
import requests
import logging
import os
from typing import Dict, Optional, Any
from jwt.exceptions import InvalidTokenError, ExpiredSignatureError, InvalidSignatureError
from datetime import datetime, timezone

logger = logging.getLogger(__name__)
logger.setLevel(os.getenv('LOG_LEVEL', 'INFO'))

class CognitoJWTValidator:
    """
    A class to validate JWT tokens issued by Amazon Cognito User Pools.
    """
    
    def __init__(self, user_pool_id: str, region: str, client_id: Optional[str] = None):
        """
        Initialize the Cognito JWT validator.
        
        Args:
            user_pool_id: The Cognito User Pool ID
            region: AWS region where the User Pool is located
            client_id: Optional Cognito App Client ID for additional validation
        """
        self.user_pool_id = user_pool_id
        self.region = region
        self.client_id = client_id
        self.jwks_url = f"https://cognito-idp.{region}.amazonaws.com/{user_pool_id}/.well-known/jwks.json"
        self.issuer = f"https://cognito-idp.{region}.amazonaws.com/{user_pool_id}"
        self._jwks_cache = None
        self._cache_expiry = None
    
    def _get_jwks(self) -> Dict[str, Any]:
        """
        Retrieve the JSON Web Key Set (JWKS) from Cognito.
        Implements basic caching to avoid repeated requests.
        
        Returns:
            Dict containing the JWKS
        """
        current_time = datetime.now(timezone.utc)
        
        # Use cached JWKS if available and not expired (cache for 1 hour)
        if (self._jwks_cache and self._cache_expiry and 
            current_time < self._cache_expiry):
            return self._jwks_cache
        
        try:
            response = requests.get(self.jwks_url, timeout=10)
            response.raise_for_status()
            jwks = response.json()
            
            # Cache the JWKS for 1 hour
            self._jwks_cache = jwks
            self._cache_expiry = current_time.replace(hour=current_time.hour + 1)
            
            return jwks
        except requests.RequestException as e:
            logger.error(f"Failed to fetch JWKS from {self.jwks_url}: {str(e)}")
            raise Exception(f"Failed to fetch JWKS: {str(e)}")
    
    def _get_public_key(self, token_header: Dict[str, Any]) -> str:
        """
        Get the public key for verifying the JWT signature.
        
        Args:
            token_header: The JWT header containing the key ID (kid)
            
        Returns:
            The public key in PEM format
        """
        kid = token_header.get('kid')
        if not kid:
            raise ValueError("Token header missing 'kid' field")
        
        jwks = self._get_jwks()
        
        # Find the key with matching kid
        for key in jwks.get('keys', []):
            if key.get('kid') == kid:
                # Convert JWK to PEM format
                return jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(key))
        
        raise ValueError(f"Unable to find a signing key that matches: '{kid}'")
    
    def validate_token(self, token: str) -> Dict[str, Any]:
        """
        Validate a JWT token and return the decoded payload.
        
        Args:
            token: The JWT token to validate
            
        Returns:
            Dict containing the decoded token payload
            
        Raises:
            Exception: If token validation fails
        """
        try:
            # Decode header without verification to get the key ID
            unverified_header = jwt.get_unverified_header(token)
            
            # Get the public key for verification
            public_key = self._get_public_key(unverified_header)
            
            # Verify and decode the token
            decoded_token = jwt.decode(
                token,
                public_key,
                algorithms=['RS256'],
                issuer=self.issuer,
                options={
                    'verify_signature': True,
                    'verify_exp': True,
                    'verify_iat': True,
                    'verify_iss': True,
                    'verify_aud': False,  # Set to True if you want to verify audience
                }
            )
            
            # Additional validations
            self._validate_token_claims(decoded_token)
            
            # Extract username using the same logic as extract_user_info
            username = decoded_token.get('username') or decoded_token.get('cognito:username', 'unknown')
            logger.info(f"Token validated successfully for user: {username}")
            return decoded_token
            
        except ExpiredSignatureError:
            logger.warning("Token has expired")
            raise Exception("Token has expired")
        except InvalidSignatureError:
            logger.warning("Token signature is invalid")
            raise Exception("Invalid token signature")
        except InvalidTokenError as e:
            logger.warning(f"Invalid token: {str(e)}")
            raise Exception(f"Invalid token: {str(e)}")
        except Exception as e:
            logger.error(f"Token validation failed: {str(e)}")
            raise Exception(f"Token validation failed: {str(e)}")
    
    def _validate_token_claims(self, decoded_token: Dict[str, Any]) -> None:
        """
        Validate additional token claims.
        
        Args:
            decoded_token: The decoded JWT payload
        """
        # Validate token use
        token_use = decoded_token.get('token_use')
        if token_use not in ['access', 'id']:
            raise ValueError(f"Invalid token_use: {token_use}")
        
        # Validate client_id if provided
        if self.client_id:
            client_id = decoded_token.get('client_id') or decoded_token.get('aud')
            if client_id != self.client_id:
                raise ValueError(f"Invalid client_id: {client_id}")
        
        # Validate that the token is not used before it's valid
        current_time = datetime.now(timezone.utc).timestamp()
        iat = decoded_token.get('iat')
        if iat and iat > current_time:
            raise ValueError("Token used before valid time")

def extract_user_info(decoded_token: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract user information from a decoded JWT token.
    
    Args:
        decoded_token: The decoded JWT payload
        
    Returns:
        Dict containing user information
    """
    return {
        'user_id': decoded_token.get('sub'),
        'username': decoded_token.get('username') or decoded_token.get('cognito:username'),
        'email': decoded_token.get('email'),
        'email_verified': decoded_token.get('email_verified'),
        'groups': decoded_token.get('cognito:groups', []),
        'token_use': decoded_token.get('token_use'),
        'client_id': decoded_token.get('client_id') or decoded_token.get('aud'),
        'exp': decoded_token.get('exp'),
        'iat': decoded_token.get('iat'),
    }

def validate_cognito_token(token: str) -> Dict[str, Any]:
    """
    Convenience function to validate a Cognito JWT token using environment variables.
    
    Args:
        token: The JWT token to validate
        
    Returns:
        Dict containing the decoded token payload and user info
    """
    user_pool_id = os.getenv('COGNITO_POOL_ID')
    region = os.getenv('REGION', 'us-east-1')
    client_id = os.getenv('COGNITO_CLIENT_ID')  # Optional
    
    if not user_pool_id:
        raise Exception("COGNITO_POOL_ID environment variable is not set")
    
    validator = CognitoJWTValidator(user_pool_id, region, client_id)
    decoded_token = validator.validate_token(token)
    user_info = extract_user_info(decoded_token)
    
    return {
        'decoded_token': decoded_token,
        'user_info': user_info
    }

def extract_token_from_event(event: Dict[str, Any]) -> Optional[str]:
    """
    Extract JWT token from various parts of the WebSocket event.
    Falls back to retrieving the token from DynamoDB if not found in the event.
    
    The function looks for the authorization token in the following order:
    1. Query string parameters: 'authorization', 'Authorization', 'AUTHORIZATION'
    2. Headers: 'Authorization' or 'authorization'
    3. Multi-value headers: 'Authorization' or 'authorization'
    4. DynamoDB connections table (if connection exists)
    
    Args:
        event: The WebSocket event
        
    Returns:
        The JWT token if found, None otherwise
    """
    # Try to get token from query string parameters
    query_params = event.get('queryStringParameters') or {}
    
    # Check for 'authorization' parameter in different cases
    for param_name in ['authorization', 'Authorization', 'AUTHORIZATION']:
        authentication_token = query_params.get(param_name)
        if authentication_token:
            return authentication_token
    
    # Try to get token from headers
    headers = event.get('headers') or {}
    
    # Check Authorization header
    auth_header = headers.get('Authorization') or headers.get('authorization')
    if auth_header:
        # Handle "Bearer <token>" format
        if auth_header.startswith('Bearer '):
            return auth_header[7:]
        return auth_header
    
    # Try to get token from multi-value headers (API Gateway v2)
    multi_headers = event.get('multiValueHeaders') or {}
    auth_headers = multi_headers.get('Authorization') or multi_headers.get('authorization')
    if auth_headers and isinstance(auth_headers, list) and auth_headers:
        auth_header = auth_headers[0]
        if auth_header.startswith('Bearer '):
            return auth_header[7:]
        return auth_header
    
    # If no token found in event, try to retrieve from DynamoDB connections table
    connection_id = event.get('requestContext', {}).get('connectionId')
    if connection_id:
        try:
            import boto3
            from botocore.exceptions import ClientError
            
            connections_table_name = os.getenv('CONNECTIONS_TABLE')
            if connections_table_name:
                dynamodb = boto3.resource('dynamodb')
                connections_table = dynamodb.Table(connections_table_name)
                
                response = connections_table.get_item(
                    Key={'connectionId': connection_id}
                )
                
                item = response.get('Item', {})
                stored_token = item.get('access_token')
                
                if stored_token:
                    logger.info(f"Retrieved stored JWT token for connection {connection_id}")
                    return stored_token
                else:
                    logger.warning(f"No stored token found for connection {connection_id}")
                    
        except Exception as e:
            logger.error(f"Failed to retrieve token from DynamoDB for connection {connection_id}: {str(e)}")
    
    return None
