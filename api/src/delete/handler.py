import json
import os
import boto3
import logging
from botocore.exceptions import ClientError
from src.helpers.api_responses import Responses
from src.helpers.construct_response import construct_response
from src.helpers.schema_validation import validate_request_datas_schema
from src.handler_websocket.handler import send_to_client
from src.helpers.event_utils import extract_event_info 

"""
/**
 * @asyncapi
 * channels:
 *   templateDeletion:
 *     description: Channel for deleting a template by ID.
 *     publish:
 *       operationId: templateDeletion
 *       summary: Delete a template by ID.
 *       message:
 *         messageId: templateDeletion
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
 *       operationId: templateDeletionResponse
 *       summary: Receive response for the deletion request.
 *       message:
 *         $ref: '#/components/messages/TemplateDeletionResponse'
 */
"""

# Configure logger for the module
logger = logging.getLogger(__name__)
logger.setLevel(os.getenv('LOG_LEVEL', 'INFO'))  # Set log level based on environment variable

# Set up logging
logger = logging.getLogger(__name__)
logger.setLevel(os.getenv('LOG_LEVEL', 'INFO'))

def delete(event, context):
    logger.debug('Event: %s', event)
    logger.info('Inside delete function')

    # Define status codes
    STATUS_ERROR = 500
    STATUS_UNPROCESSABLE_ENTITY = 422
    STATUS_NOT_FOUND = 404
    STATUS_DELETED = 200

    # Initialize DynamoDB resource and table
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(os.getenv('TABLE'))

    # Extract necessary information from the event
    event_info = extract_event_info(event)
    url = event_info.get('url')
    connectionId = event_info.get('connectionId')

    # Retrieve the ID in the request body
    body = json.loads(event.get('body', '{}'))
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

    # Get the action from the event
    action = body.get('action')

    # Validate the request
    validation_schema = validate_request_datas_schema(action, params)
    if not validation_schema['success']:
        response_result = Responses.result_response(STATUS_UNPROCESSABLE_ENTITY, False, 'Validation errors.', validation_schema)
        send_to_client(connectionId, json.dumps(construct_response(response_result)), url)
        return {
            'statusCode': STATUS_UNPROCESSABLE_ENTITY,
            'body': json.dumps('Validation errors.')
        }

    try:
        # Check if the item exists and delete it
        try:
            existing_item = table.get_item(Key=params)
            if 'Item' not in existing_item:
                response_result = Responses.result_response(STATUS_NOT_FOUND, False, f'Template with ID {id} not found.')
            else:
                table.delete_item(Key=params)
                response_result = Responses.result_response(STATUS_DELETED, True, f'Template with ID {id} successfully deleted.')
        except ClientError as e:
            logger.error(f"DynamoDB ClientError: {e.response['Error']['Message']}")
            response_result = Responses.result_response(STATUS_ERROR, False, 'Error accessing DynamoDB.')
    except Exception as err:
        logger.error(f"Unexpected error: {str(err)}")
        response_result = Responses.result_response(STATUS_ERROR, False, str(err))

    # Send the response to the client
    send_to_client(connectionId, json.dumps(construct_response(response_result)), url)

    return {
        'statusCode': 200,
        'body': json.dumps('Message processed')
    }