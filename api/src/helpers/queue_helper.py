import os
import json
import boto3
import logging

# Set up logging
logger = logging.getLogger(__name__)
if not logger.handlers:
    logger.setLevel(logging.INFO)

# Create a new instance of the SQS service
sqs = boto3.client('sqs')

def send_message_to_queue(message_body):
    """
    Sends a message to the specified SQS queue.
    This function constructs the parameters needed for the SQS send_message API call,
    including the queue URL and the message body, and sends the message to the queue.
    
    Args:
        message_body (dict): The message body to send, which will be stringified.
        
    Returns:
        dict: Response from SQS send_message API call
        
    Raises:
        Exception: Will raise an error if the queue URL is not provided or if the SQS API call fails.
    """
    # Check if the AWS region is set in the environment variables
    queue_url = f"https://sqs.{os.environ['REGION']}.amazonaws.com/{os.environ['AWS_ACCOUNT_ID']}/AUDIT_QUEUE"
    
    # Check if the queue URL is available
    if not queue_url:
        # Raise an error if the queue URL is not available
        raise Exception('Queue URL could not be retrieved.')
    
    # Validate message_body is not None
    if message_body is None:
        raise Exception('Message body must not be None.')
    
    # Define parameters for the send_message API call
    params = {
        'QueueUrl': queue_url,  # Use the specified queue URL
        'MessageBody': json.dumps(message_body, default=str),  # Convert the message body to a JSON string
    }
    
    try:
        # Call the SQS send_message API and wait for the result
        response = sqs.send_message(**params)
        return response
    except Exception as error:
        # Log the error message if the API call fails
        logger.error(f"Failed to send message to queue: {str(error)}")
        # Re-raise the error to be handled by the caller
        raise error