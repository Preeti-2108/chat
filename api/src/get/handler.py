import json  # Provides methods to work with JSON data
import os  # Provides a way of using operating system dependent functionality
import boto3  # AWS SDK for Python to interact with AWS services
import logging  # Provides a way to configure and use loggers
from botocore.exceptions import BotoCoreError, ClientError  # Exceptions for AWS SDK
from src.helpers.api_responses import Responses  # Custom helper for API responses
from src.helpers.construct_response import construct_response  # Custom helper to construct responses
from src.helpers.schema_validation import validate_request_datas_schema  # Custom helper to validate request data schema
from src.handler_websocket.handler import send_to_client  # Custom helper to send data to a client via WebSocket
from src.helpers.event_utils import extract_event_info  # Custom helper to extract necessary information from the event

"""
/**
 * @asyncapi
 * channels:
 *   templateRetrieval:
 *     description: Channel for retrieving a single template by ID.
 *     publish:
 *       operationId: templateRetrieval
 *       summary: Return a single template.
 *       message:
 *         messageId: templateRetrieval
 *         contentType: application/json
 *         payload:
 *           type: object
 *           required:
 *             - id
 *           properties:
 *             id:
 *               type: string
 *               description: Use template's ID.
 *               example: 184CF8DA-B821-4FF4-BD6C-CDAFA166E2E0
 *     subscribe:
 *       operationId: templateRetrievalResponse
 *       summary: Receive response for the retrieved template.
 *       message:
 *         $ref: '#/components/messages/TemplateRetrievalResponse'
 */
"""

# Configure logger
logger = logging.getLogger(__name__)
logger.setLevel(os.getenv('LOG_LEVEL', 'INFO'))  # Set Log Level

def get(event, context):
    """
    Main function to handle the retrieval of an item.
    """
    logger.debug('Event: %s', event)  # Log the incoming event
    logger.info('Inside get function')  # Log entry into the function

    # Initialize DynamoDB resource and table
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(os.getenv('TABLE'))

    # Define status codes
    STATUS_ERROR = 500
    STATUS_UNPROCESSABLE_ENTITY = 422
    STATUS_NOT_FOUND = 404
    STATUS_FOUND = 200

    # Extract necessary information from the event
    event_info = extract_event_info(event)
    url = event_info.get('url')
    connectionId = event_info.get('connectionId')

    # Retrieve the ID from the body of the WebSocket event
    body = event.get('body', {})
    if isinstance(body, str):
        body = json.loads(body)  # If the body is a JSON string, convert it to a dictionary

    id = body.get('id')
    if not id:
        response_result = Responses.result_response(STATUS_UNPROCESSABLE_ENTITY, False, 'ID parameter is required.')
        send_to_client(connectionId, json.dumps(construct_response(response_result)), url)
        return {
            'statusCode': STATUS_UNPROCESSABLE_ENTITY,
            'body': json.dumps('ID parameter is required.')
        }

    params = {'id': id}

    # Default error response
    response_result = Responses.result_response(STATUS_ERROR, False, 'Error during execution.')

    # Retrieve the action from the body
    action = body.get('action')

    # Validate the request data
    validation_schema = validate_request_datas_schema(action, params)
    if not validation_schema['success']:
        response_result = Responses.result_response(STATUS_UNPROCESSABLE_ENTITY, False, 'Validation errors.', validation_schema)
        send_to_client(connectionId, json.dumps(construct_response(response_result)), url)
        return {
            'statusCode': STATUS_UNPROCESSABLE_ENTITY,
            'body': json.dumps('Validation errors.')
        }

    try:
        # Check if the item exists in DynamoDB
        try:
            existing_item = table.get_item(Key=params)
        except ClientError as e:
            logger.error(f"DynamoDB ClientError: {e.response['Error']['Message']}")
            response_result = Responses.result_response(STATUS_ERROR, False, 'Error accessing DynamoDB.')
        else:
            item = existing_item.get('Item')
            if item is None:
                response_result = Responses.result_response(STATUS_NOT_FOUND, False, f'Item with ID {id} not found.')
            else:
                response_result = Responses.result_response(STATUS_FOUND, True, f'Item with ID {id} found.', item)
    except BotoCoreError as error:
        logger.error(f"BotoCoreError: {str(error)}")
        response_result = Responses.result_response(STATUS_ERROR, False, 'Error during execution.')

    # Send the final response to the WebSocket client
    send_to_client(connectionId, json.dumps(construct_response(response_result)), url)

    return {
        'statusCode': 200,
        'body': json.dumps('Message sent successfully.')
    }