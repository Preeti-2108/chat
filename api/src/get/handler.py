import json  # Import JSON module for parsing and generating JSON data
import os  # Import OS module for interacting with the operating system
import boto3  # Import Boto3, the AWS SDK for Python, to interact with AWS services
import logging  # Import logging module to log messages
from decimal import Decimal  # Import Decimal for handling DynamoDB numeric types
from botocore.exceptions import BotoCoreError, ClientError  # Import specific exceptions from BotoCore

# Import custom helper modules for API responses, response construction, schema validation, WebSocket communication, and event information extraction
from src.helpers.api_responses import Responses
from src.helpers.construct_response import construct_response
from src.helpers.schema_validation import validate_request_datas_schema
from src.handler_websocket.handler import send_to_client
from src.helpers.event_utils import extract_event_info
from src.helpers.decimal_converter import convert_decimal_to_json_serializable as decimal_to_json_serializable  # Custom helper to convert Decimal objects
from src.helpers.auth_middleware import authenticate_websocket  # Cognito authentication

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

@authenticate_websocket()  # Require authentication for this handler
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

    # Define HTTP status codes for various outcomes
    STATUS_ERROR = 500
    STATUS_UNPROCESSABLE_ENTITY = 422
    STATUS_NOT_FOUND = 404
    STATUS_FOUND = 200

    # Initialize DynamoDB resource and table
    table_name = os.getenv('TABLE')
    if not table_name:
        logger.error("TABLE environment variable is not set")
        response_result = Responses.result_response(STATUS_ERROR, False, 'Configuration error: TABLE environment variable not set.')
        return {
            'statusCode': STATUS_ERROR,
            'body': json.dumps('Configuration error')
        }
    
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(table_name)

    # Extract necessary information from the event, such as URL and connection ID
    event_info = extract_event_info(event)
    url = event_info.get('url')
    connectionId = event_info.get('connectionId')
    
    # Validate that we have a connection ID for WebSocket communication
    if not connectionId:
        logger.error("Connection ID not found in event")
        return {
            'statusCode': STATUS_ERROR,
            'body': json.dumps('Connection ID not found in event')
        }

    # Parse the body of the WebSocket event
    body = event.get('body', {})
    logger.debug(f"Raw body from event: {body}")
    if isinstance(body, str):
        try:
            body = json.loads(body)  # Convert JSON string to dictionary if necessary
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON body: {e}")
            response_result = Responses.result_response(STATUS_UNPROCESSABLE_ENTITY, False, 'Invalid JSON in request body.')
            send_to_client(connectionId, json.dumps(construct_response(response_result)), url)
            return {
                'statusCode': STATUS_UNPROCESSABLE_ENTITY,
                'body': json.dumps('Invalid JSON in request body.')
            }

    # Extract action and datas from the request body
    action = body.get('action')
    datas = body.get('datas', {})
    logger.info(f"Processing action: {action} with datas: {datas}")

    # Extract the ID from datas
    id = datas.get('id')
    if not id:
        # If 'id' is missing, send an error response to the client
        logger.warning(f"Missing ID parameter in request. Datas: {datas}")
        response_result = Responses.result_response(STATUS_UNPROCESSABLE_ENTITY, False, 'ID parameter is required in datas.')
        send_to_client(connectionId, json.dumps(construct_response(response_result)), url)
        return {
            'statusCode': STATUS_UNPROCESSABLE_ENTITY,
            'body': json.dumps('ID parameter is required in datas.')
        }

    params = {'id': id}  # Prepare parameters for DynamoDB query
    logger.info(f"Attempting to retrieve item with ID: {id}")

    # Default error response in case of failure
    response_result = Responses.result_response(STATUS_ERROR, False, 'Error during execution.')

    # Validate the request data against a predefined schema
    validation_schema = validate_request_datas_schema(action, datas)
    if not validation_schema['success']:
        # If validation fails, send an error response to the client
        logger.warning(f"Validation failed for action: {action}, datas: {datas}. Errors: {validation_schema}")
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
            item = existing_item.get('Item')  # Extract the item from the response
            if item is None:
                # If item is not found, prepare a not found response
                response_result = Responses.result_response(STATUS_NOT_FOUND, False, f'Item with ID {id} not found.')
                status_code = STATUS_NOT_FOUND
            else:
                # Convert Decimal objects to JSON-serializable types before creating response
                serializable_item = decimal_to_json_serializable(item)
                # If item is found, prepare a success response with the item data
                response_result = Responses.result_response(STATUS_FOUND, True, f'Item with ID {id} found.', serializable_item)
                status_code = STATUS_FOUND
        except ClientError as e:
            # Log and handle DynamoDB client errors
            logger.error(f"DynamoDB ClientError: {e.response['Error']['Message']}")
            response_result = Responses.result_response(STATUS_ERROR, False, 'Error accessing DynamoDB.')
            status_code = STATUS_ERROR
    except BotoCoreError as error:
        # Log and handle general BotoCore errors
        logger.error(f"BotoCoreError: {str(error)}")
        response_result = Responses.result_response(STATUS_ERROR, False, 'Error during execution.')
        status_code = STATUS_ERROR
    except Exception as error:
        # Log and handle any other unexpected errors
        logger.error(f"Unexpected error: {str(error)}")
        response_result = Responses.result_response(STATUS_ERROR, False, 'Unexpected error during execution.')
        status_code = STATUS_ERROR

    # Send the final response to the WebSocket client
    try:
        response_data = json.dumps(construct_response(response_result))
        logger.debug(f"Sending response to connection {connectionId}: {response_data}")
        send_to_client(connectionId, response_data, url)
        logger.info(f"Successfully sent response for item ID: {id}")
        return {
            'statusCode': status_code,
            'body': json.dumps('Message sent successfully.')
        }
    except Exception as send_error:
        # Log error if sending message fails
        logger.error(f"Failed to send message to client {connectionId}: {str(send_error)}")
        return {
            'statusCode': STATUS_ERROR,
            'body': json.dumps('Failed to send message to client.')
        }