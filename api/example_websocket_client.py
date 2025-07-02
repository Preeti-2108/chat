"""
Example WebSocket Client with Cognito JWT Authentication

This script demonstrates how to connect to a WebSocket API with Cognito JWT authentication.
It shows how to obtain a JWT token from Cognito and use it to authenticate WebSocket connections.
"""

import asyncio
import websockets
import json
import boto3
import logging
from botocore.exceptions import ClientError

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CognitoWebSocketClient:
    """
    WebSocket client with Cognito authentication support.
    """
    
    def __init__(self, user_pool_id: str, client_id: str, region: str = 'us-east-1'):
        """
        Initialize the WebSocket client with Cognito configuration.
        
        Args:
            user_pool_id: Cognito User Pool ID
            client_id: Cognito App Client ID
            region: AWS region
        """
        self.user_pool_id = user_pool_id
        self.client_id = client_id
        self.region = region
        self.cognito_client = boto3.client('cognito-idp', region_name=region)
        self.access_token = None
        self.websocket = None
    
    def authenticate(self, username: str, password: str) -> str:
        """
        Authenticate with Cognito and obtain an access token.
        
        Args:
            username: Cognito username
            password: User password
            
        Returns:
            JWT access token
        """
        try:
            response = self.cognito_client.initiate_auth(
                ClientId=self.client_id,
                AuthFlow='USER_PASSWORD_AUTH',
                AuthParameters={
                    'USERNAME': username,
                    'PASSWORD': password
                }
            )
            
            self.access_token = response['AuthenticationResult']['AccessToken']
            logger.info(f"Successfully authenticated user: {username}")
            return self.access_token
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']
            logger.error(f"Authentication failed: {error_code} - {error_message}")
            raise Exception(f"Authentication failed: {error_message}")
    
    async def connect(self, websocket_url: str):
        """
        Connect to the WebSocket with JWT authentication.
        
        Args:
            websocket_url: WebSocket endpoint URL
        """
        if not self.access_token:
            raise Exception("No access token available. Please authenticate first.")
        
        # Add the JWT token as a query parameter
        auth_url = f"{websocket_url}?token={self.access_token}"
        
        try:
            self.websocket = await websockets.connect(auth_url)
            logger.info("WebSocket connection established with authentication")
            
            # Listen for messages from the server
            await self._listen_for_messages()
            
        except Exception as e:
            logger.error(f"Failed to connect to WebSocket: {str(e)}")
            raise
    
    async def _listen_for_messages(self):
        """
        Listen for incoming messages from the WebSocket.
        """
        try:
            async for message in self.websocket:
                logger.info(f"Received message: {message}")
                await self._handle_message(json.loads(message))
        except websockets.exceptions.ConnectionClosed:
            logger.info("WebSocket connection closed")
        except Exception as e:
            logger.error(f"Error receiving messages: {str(e)}")
    
    async def _handle_message(self, message: dict):
        """
        Handle incoming WebSocket messages.
        
        Args:
            message: Parsed JSON message from the server
        """
        message_type = message.get('type', 'unknown')
        
        if message_type == 'connection_ack':
            logger.info("Connection acknowledged by server")
            # You can start sending messages here
            await self.send_test_messages()
        elif message_type == 'error':
            logger.error(f"Server error: {message.get('message', 'Unknown error')}")
        else:
            logger.info(f"Received {message_type} message: {message}")
    
    async def send_message(self, action: str, data: dict):
        """
        Send a message to the WebSocket server.
        
        Args:
            action: The action to perform
            data: Message data
        """
        if not self.websocket:
            raise Exception("WebSocket not connected")
        
        message = {
            "action": action,
            "datas": data
        }
        
        await self.websocket.send(json.dumps(message))
        logger.info(f"Sent message: {action}")
    
    async def send_test_messages(self):
        """
        Send some test messages to demonstrate functionality.
        """
        # Example: Create a new item
        await self.send_message("create", {
            "templateCompany": "Test Company",
            "templateAgent": "Test Agent",
            "templateRootCause": "Test Root Cause",
            "templateAgentValidation": True,
            "isActive": True
        })
        
        # Wait a bit before sending the next message
        await asyncio.sleep(1)
        
        # Example: List items
        await self.send_message("list", {})
    
    async def disconnect(self):
        """
        Disconnect from the WebSocket.
        """
        if self.websocket:
            await self.websocket.close()
            logger.info("WebSocket disconnected")

# Example usage
async def main():
    """
    Example of how to use the CognitoWebSocketClient.
    """
    # Configure your Cognito settings
    USER_POOL_ID = "your-user-pool-id"
    CLIENT_ID = "your-client-id"
    REGION = "us-east-1"
    WEBSOCKET_URL = "wss://your-api-id.execute-api.region.amazonaws.com/prod"
    
    # User credentials
    USERNAME = "your-username"
    PASSWORD = "your-password"
    
    client = CognitoWebSocketClient(USER_POOL_ID, CLIENT_ID, REGION)
    
    try:
        # Authenticate with Cognito
        logger.info("Authenticating with Cognito...")
        client.authenticate(USERNAME, PASSWORD)
        
        # Connect to WebSocket with authentication
        logger.info("Connecting to WebSocket...")
        await client.connect(WEBSOCKET_URL)
        
    except Exception as e:
        logger.error(f"Error: {str(e)}")
    finally:
        await client.disconnect()

if __name__ == "__main__":
    # Run the example
    # asyncio.run(main())
    
    # Instructions for usage:
    print("""
    Cognito WebSocket Client Example
    ================================
    
    To use this client:
    
    1. Update the configuration variables in the main() function:
       - USER_POOL_ID: Your Cognito User Pool ID
       - CLIENT_ID: Your Cognito App Client ID
       - REGION: AWS region where your resources are deployed
       - WEBSOCKET_URL: Your WebSocket API endpoint
       - USERNAME and PASSWORD: Valid Cognito user credentials
    
    2. Install required dependencies:
       pip install websockets boto3
    
    3. Configure AWS credentials (AWS CLI, environment variables, or IAM role)
    
    4. Uncomment the asyncio.run(main()) line and run the script
    
    Alternative authentication with query parameters:
    wss://your-api-id.execute-api.region.amazonaws.com/prod?token=your-jwt-token
    
    Alternative authentication with headers (if supported by your WebSocket setup):
    Headers: {"Authorization": "Bearer your-jwt-token"}
    """)
