# Import necessary modules and packages
import os
import boto3
import logging
from botocore.exceptions import BotoCoreError, ClientError
from src.helpers.api_responses import Responses
from src.helpers.construct_response import construct_response
from src.helpers.schema_validation import validate_request_body_schema
from src.handler_websocket.handler import send_to_client
from src.helpers.event_utils import extract_event_info

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

# Initialize logger for the module
logger = logging.getLogger(__name__)
logger.setLevel(os.getenv('LOG_LEVEL', 'INFO'))  # Set log level from environment variable or default to 'INFO'

def get(event, context):
    """
    Handles GET requests to retrieve a single template by ID from DynamoDB.

    Parameters:
    - event: dict, contains request data including path parameters and context
    - context: object, provides runtime information to the handler

    Returns:
    - A constructed HTTP response with the template data or an error message
    """
    logger.debug('logging event: %s', event)  # Log the incoming event for debugging
    logger.info('Inside get function')  # Log entry into the function

    # Initialize DynamoDB resource and specify the table
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(os.getenv('TABLE'))  # Get table name from environment variable

    # Define HTTP status codes for various outcomes
    STATUS_ERROR = 500
    STATUS_UNPROCESSABLE_ENTITY = 422
    STATUS_NOT_FOUND = 404
    STATUS_FOUND = 200

    # Extract the template ID from the path parameters
    id = event['pathParameters']['id']
    params = {
        'id': id
    }

    # Default error response setup
    response_result = Responses.result_response(STATUS_ERROR, False, 'Error during the execution.')

    # Extract HTTP method from the event
    http_method = event['requestContext']['http']['method']

    # Validate the request body schema based on the HTTP method and parameters
    validation_schema = validate_request_body_schema(http_method, params)

    try:
        # Check for validation errors and respond with a 422 status if any
        if not validation_schema['success']:
            response_result = Responses.result_response(STATUS_UNPROCESSABLE_ENTITY, False, 'Validation errors.', validation_schema)
            return construct_response(response_result)

        # Attempt to retrieve the item from DynamoDB using the provided ID
        try:
            existing_item = table.get_item(Key=params)
        except ClientError as e:
            # Log the error message if a client error occurs
            print(e.response['Error']['Message'])
        else:
            # Check if the item exists in the response
            item = existing_item.get('Item')
            if item is None:
                # Respond with a 404 status if the item is not found
                response_result = Responses.result_response(STATUS_NOT_FOUND, False, f'Template with ID {id} not found.')
            else:
                # Respond with a 200 status and the item data if found
                response_result = Responses.result_response(STATUS_FOUND, True, f'Template with ID {id} found.', item)

    except (BotoCoreError, ClientError) as error:
        # Handle any exceptions during the process and respond with a 500 status
        response_result = Responses.result_response(STATUS_ERROR, False, str(error))

    # Construct and return the final HTTP response
    return construct_response(response_result)