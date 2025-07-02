# Import necessary modules and packages
import json  # For handling JSON data
import os  # For accessing environment variables
import boto3  # AWS SDK for Python to interact with AWS services
import logging  # For logging information and errors
from botocore.exceptions import ClientError  # Exception for AWS client errors
from src.helpers.api_responses import Responses  # Custom response handling
from src.helpers.construct_response import construct_response  # Helper to construct responses
from src.helpers.schema_validation import validate_request_datas_schema  # Schema validation utility
from src.handler_websocket.handler import send_to_client  # WebSocket communication utility
from src.helpers.event_utils import extract_event_info  # Utility to extract information from events

"""
/**
 * @asyncapi
 * channels:
 *   templateDelete:
 *     description: Channel for deleting a specific template by ID.
 *     publish:
 *       operationId: templateDelete
 *       summary: Delete a specific template.
 *       message:
 *         messageId: templateDelete
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
 *               example: delete
 *             datas:
 *               type: object
 *               required:
 *                 - id
 *               properties:
 *                 id:
 *                   type: string
 *                   description: The unique identifier of the template to delete.
 *                   example: 123e4567-e89b-12d3-a456-426614174000
 *     subscribe:
 *       operationId: templateDeleteResponse
 *       summary: Receive response for the deleted template.
 *       message:
 *         $ref: '#/components/messages/TemplateDeleteResponse'
 */
"""

# Configure logger for the module
logger = logging.getLogger(__name__)
logger.setLevel(os.getenv('LOG_LEVEL', 'INFO'))  # Set log level based on environment variable

def delete(event, context):
    """
    Handles the deletion of a template based on the provided event data.
    
    Args:
        event (dict): The event data containing information about the request.
        context (object): The context in which the function is executed.

    Returns:
        dict: A response object with status code and message.
    """
    logger.debug('Event: %s', event)  # Log the incoming event for debugging
    logger.info('Inside delete function')  # Log entry into the delete function

    # Define HTTP status codes for various outcomes
    STATUS_ERROR = 500
    STATUS_UNPROCESSABLE_ENTITY = 422
    STATUS_NOT_FOUND = 404
    STATUS_DELETED = 200

    # Initialize DynamoDB resource and table using environment variable for table name
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(os.getenv('TABLE'))

    # Extract necessary information from the event
    event_info = extract_event_info(event)
    url = event_info.get('url')  # WebSocket URL for client communication
    connectionId = event_info.get('connectionId')  # WebSocket connection ID

    # Parse the request body
    body = json.loads(event.get('body', '{}'))
    action = body.get('action')
    datas = body.get('datas', {})

    # Extract ID from datas
    id = datas.get('id')
    if not id:
        # Respond with an error if ID is not provided
        response_result = Responses.result_response(STATUS_UNPROCESSABLE_ENTITY, False, 'ID parameter is required in datas.')
        send_to_client(connectionId, json.dumps(construct_response(response_result)), url)
        return {
            'statusCode': STATUS_UNPROCESSABLE_ENTITY,
            'body': json.dumps('ID parameter is required in datas.')
        }

    params = {'id': id}  # Parameters for DynamoDB operations

    # Default error response setup
    response_result = Responses.result_response(STATUS_ERROR, False, 'Error during execution.')

    # Validate the request against a predefined schema
    validation_schema = validate_request_datas_schema(action, datas)
    if not validation_schema['success']:
        # Respond with validation errors if schema validation fails
        response_result = Responses.result_response(STATUS_UNPROCESSABLE_ENTITY, False, 'Validation errors.', validation_schema)
        send_to_client(connectionId, json.dumps(construct_response(response_result)), url)
        return {
            'statusCode': STATUS_UNPROCESSABLE_ENTITY,
            'body': json.dumps('Validation errors.')
        }

    try:
        # Attempt to retrieve and delete the item from DynamoDB
        try:
            existing_item = table.get_item(Key=params)  # Check if the item exists
            if 'Item' not in existing_item:
                # Respond with not found if the item does not exist
                response_result = Responses.result_response(STATUS_NOT_FOUND, False, f'Template with ID {id} not found.')
            else:
                # Delete the item if it exists
                table.delete_item(Key=params)
                response_result = Responses.result_response(STATUS_DELETED, True, f'Template with ID {id} successfully deleted.')
        except ClientError as e:
            # Log and respond with an error if there is a DynamoDB client error
            logger.error(f"DynamoDB ClientError: {e.response['Error']['Message']}")
            response_result = Responses.result_response(STATUS_ERROR, False, 'Error accessing DynamoDB.')
    except Exception as err:
        # Log and respond with an error for any unexpected exceptions
        logger.error(f"Unexpected error: {str(err)}")
        response_result = Responses.result_response(STATUS_ERROR, False, str(err))

    # Send the constructed response back to the client via WebSocket
    send_to_client(connectionId, json.dumps(construct_response(response_result)), url)

    return {
        'statusCode': STATUS_DELETED,  # Return a success status code
        'body': json.dumps('Message processed')  # Return a success message
    }