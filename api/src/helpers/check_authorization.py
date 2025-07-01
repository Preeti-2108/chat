import os
import jwt
import boto3
from botocore.exceptions import BotoCoreError, ClientError

class BadRequest(Exception):
    """
    Custom exception class for handling bad request errors.
    
    This exception is raised when there are issues with authorization,
    token validation, or missing required parameters.
    """
    def __init__(self, message, status_code=400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code

def check_authorization(event):
    """
    Validates the authorization token from an incoming event and retrieves the user ID.
    
    This function checks for the presence of an authorization token in the event data.
    For WebSocket events, it looks for the token in the message body.
    For HTTP events, it looks in the headers.
    
    Parameters:
    event (dict): The event data containing the authorization token.

    Returns:
    str: The user ID extracted from the token or AWS Cognito.

    Raises:
    BadRequest: If the authorization token is missing, invalid, or lacks necessary information.
    """
    
    authorization_header = None
    
    # Check if this is a WebSocket event (has body) or HTTP event (has headers)
    if 'body' in event and event.get('body'):
        try:
            import json
            body = json.loads(event.get('body', '{}'))
            # Look for authorization token in the message body
            authorization_header = body.get('authorization') or body.get('token')
        except (json.JSONDecodeError, TypeError):
            pass
    
    # Fallback to headers for HTTP requests
    if not authorization_header and 'headers' in event:
        authorization_header = event['headers'].get('authorization') or event['headers'].get('Authorization')

    # Raise an error if the authorization token is missing
    if not authorization_header:
        raise BadRequest("Authorization token is missing.", status_code=401)

    # Extract the token from the authorization header; assumes 'Bearer <token>' format
    token = authorization_header.split(" ")[1] if " " in authorization_header else authorization_header

    # Attempt to decode the token without verifying the signature
    try:
        payload = jwt.decode(token, options={"verify_signature": False})
    except jwt.InvalidTokenError:
        # Raise an error if the token is invalid
        raise BadRequest("Invalid token.", status_code=401)

    # Extract the user email from the token payload
    userId = payload.get('email')
    if not userId:
        # If email is not present, attempt to retrieve the client_id
        clientId = payload.get('client_id')
        if not clientId:
            # Raise an error if both email and client_id are missing
            raise BadRequest("Both email and client_id are missing from the token.", status_code=400)
        else:
            # Retrieve the Cognito User Pool ID from environment variables
            UserPoolId = os.environ['COGNITO_POOL_ID']
            # Initialize a Cognito Identity Provider client
            client = boto3.client('cognito-idp')
            # Describe the user pool client to get the client name
            currentClient = client.describe_user_pool_client(
                UserPoolId=UserPoolId,
                ClientId=clientId
            )
            # Use the client name as the user ID
            userId = currentClient['UserPoolClient']['ClientName']
    
    # Return the determined user ID
    return userId