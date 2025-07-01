import json  # Import JSON module for parsing and generating JSON data
import os  # Import OS module for interacting with the operating system
import boto3  # Import Boto3, the AWS SDK for Python, to interact with AWS services
import logging  # Import logging module to log messages
from botocore.exceptions import BotoCoreError, ClientError  # Import specific exceptions from BotoCore

# Import custom helper modules for API responses, response construction, schema validation, WebSocket communication, and event information extraction
from src.helpers.api_responses import Responses
from src.helpers.construct_response import construct_response
from src.helpers.schema_validation import validate_request_datas_schema
from src.handler_websocket.handler import send_to_client
from src.helpers.event_utils import extract_event_info

"""
/**
 * @asyncapi
 * channels:
 *   templateGet:
 *     description: Channel for retrieving a specific template by ID.
 *     publish:
 *       operationId: templateGet
 *       summary: Get a specific template.
 *       message:
 *         messageId: templateGet
 *         contentType: application/json
 *         payload:
 *           type: object
 *           required:
 *             - action
 *             - datas
 *           properties:
 *             action:
 *               type: string
 *               description: The action to perform.
 *               example: get
 *             datas:
 *               type: object
 *               required:
 *                 - id
 *               properties:
 *                 id:
 *                   type: string
 *                   description: The unique identifier of the template to retrieve.
 *                   example: 123e4567-e89b-12d3-a456-426614174000
 *     subscribe:
 *       operationId: templateGetResponse
 *       summary: Receive response for the retrieved template.
 *       message:
 *         $ref: '#/components/messages/TemplateGetResponse'
 */
"""

# Configure the logger for the module
logger = logging.getLogger(__name__)
logger.setLevel(os.getenv('LOG_LEVEL', 'INFO'))  # Set the log level based on environment variable or default to 'INFO'

def get(event, context):
    """
    Handles the retrieval of a template item from a DynamoDB table based on the provided ID.
    
    This function processes incoming WebSocket events, validates the request data, 
    interacts with DynamoDB to retrieve the item, and sends the response back to the client.
    
    :param event: The event data received from the WebSocket, containing the request details.
    :param context: The context in which the function is executed, providing runtime information.
    :return: A dictionary containing the HTTP status code and a message indicating the result of the operation.
    """
    logger.debug('Event: %s', event)  # Log the incoming event for debugging purposes
    logger.info('Inside get function')  # Log entry into the function

    # Initialize a DynamoDB resource and specify the table to interact with
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(os.getenv('TABLE'))  # Get the table name from environment variables

    # Define HTTP status codes for various outcomes
    STATUS_ERROR = 500
    STATUS_UNPROCESSABLE_ENTITY = 422
    STATUS_NOT_FOUND = 404
    STATUS_FOUND = 200

    # Extract necessary information from the event, such as URL and connection ID
    event_info = extract_event_info(event)
    url = event_info.get('url')
    connectionId = event_info.get('connectionId')

    # Parse the body of the WebSocket event
    body = event.get('body', {})
    if isinstance(body, str):
        body = json.loads(body)  # Convert JSON string to dictionary if necessary

    # Extract action and datas from the request body
    action = body.get('action')
    datas = body.get('datas', {})

    # Check if action parameter is provided (mandatory)
    if not action:
        response_result = Responses.result_response(STATUS_UNPROCESSABLE_ENTITY, False, 'Action parameter is required.')
        send_to_client(connectionId, json.dumps(construct_response(response_result)), url)
        return {
            'statusCode': STATUS_UNPROCESSABLE_ENTITY,
            'body': json.dumps('Action parameter is required.')
        }

    # Extract the ID from datas
    id = datas.get('id')
    if not id:
        # If 'id' is missing, send an error response to the client
        response_result = Responses.result_response(STATUS_UNPROCESSABLE_ENTITY, False, 'ID parameter is required in datas.')
        send_to_client(connectionId, json.dumps(construct_response(response_result)), url)
        return {
            'statusCode': STATUS_UNPROCESSABLE_ENTITY,
            'body': json.dumps('ID parameter is required in datas.')
        }

    params = {'id': id}  # Prepare parameters for DynamoDB query

    # Default error response in case of failure
    response_result = Responses.result_response(STATUS_ERROR, False, 'Error during execution.')

    # Validate the request data against a predefined schema
    validation_schema = validate_request_datas_schema(action, datas)
    if not validation_schema['success']:
        # If validation fails, send an error response to the client
        response_result = Responses.result_response(STATUS_UNPROCESSABLE_ENTITY, False, 'Validation errors.', validation_schema)
        send_to_client(connectionId, json.dumps(construct_response(response_result)), url)
        return {
            'statusCode': STATUS_UNPROCESSABLE_ENTITY,
            'body': json.dumps('Validation errors.')
        }

    try:
        # Attempt to retrieve the item from DynamoDB using the provided ID
        try:
            existing_item = table.get_item(Key=params)
        except ClientError as e:
            # Log and handle DynamoDB client errors
            logger.error(f"DynamoDB ClientError: {e.response['Error']['Message']}")
            response_result = Responses.result_response(STATUS_ERROR, False, 'Error accessing DynamoDB.')
        else:
            item = existing_item.get('Item')  # Extract the item from the response
            if item is None:
                # If item is not found, prepare a not found response
                response_result = Responses.result_response(STATUS_NOT_FOUND, False, f'Item with ID {id} not found.')
            else:
                # If item is found, prepare a success response with the item data
                response_result = Responses.result_response(STATUS_FOUND, True, f'Item with ID {id} found.', item)
    except BotoCoreError as error:
        # Log and handle general BotoCore errors
        logger.error(f"BotoCoreError: {str(error)}")
        response_result = Responses.result_response(STATUS_ERROR, False, 'Error during execution.')

    # Send the final response to the WebSocket client
    send_to_client(connectionId, json.dumps(construct_response(response_result)), url)

    return {
        'statusCode': 200,
        'body': json.dumps('Message sent successfully.')  # Indicate successful message sending
    }