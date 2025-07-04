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
from src.helpers.auth_middleware import authenticate_websocket, get_user_email, get_authenticated_user  # Cognito authentication
from src.helpers.scope_manager import require_resource_permission  # Scope validation

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

@authenticate_websocket()  # Require authentication for this handler
@require_resource_permission('PYTHONTEMPLATEWEBSOCKET', 'DELETE')  # Require DELETE permission for this resource
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

    # Extract necessary information from the event
    try:
        event_info = extract_event_info(event)
        url = event_info.get('url')  # WebSocket URL for client communication
        connectionId = event_info.get('connectionId')  # WebSocket connection ID
        
        if not connectionId:
            logger.error("ConnectionId not found in event")
            return {
                'statusCode': STATUS_ERROR,
                'body': json.dumps({'error': 'ConnectionId not found in event'})
            }
        
        if not url:
            logger.error("WebSocket URL not found in event")
            return {
                'statusCode': STATUS_ERROR,
                'body': json.dumps({'error': 'WebSocket URL not found in event'})
            }
    except Exception as event_err:
        logger.error(f"Error extracting event info: {str(event_err)}")
        return {
            'statusCode': STATUS_ERROR,
            'body': json.dumps('Error processing event')
        }

    try:
        # Parse the request body
        if not event.get('body'):
            response_result = Responses.result_response(STATUS_UNPROCESSABLE_ENTITY, False, 'Request body is missing.')
            send_to_client(connectionId, json.dumps(construct_response(response_result)), url)
            return {
                'statusCode': STATUS_UNPROCESSABLE_ENTITY,
                'body': json.dumps('Request body is missing')
            }
        
        try:
            body = json.loads(event['body'])
        except json.JSONDecodeError as json_err:
            logger.error(f"Error parsing JSON body: {str(json_err)}")
            response_result = Responses.result_response(STATUS_UNPROCESSABLE_ENTITY, False, 'Invalid JSON format in request body.')
            send_to_client(connectionId, json.dumps(construct_response(response_result)), url)
            return {
                'statusCode': STATUS_UNPROCESSABLE_ENTITY,
                'body': json.dumps('Invalid JSON format')
            }
        
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

        logger.info(f"Extracted ID: {id}")
        
        # Get the authenticated user's email from the JWT token
        user_info = get_authenticated_user(event)
        email = get_user_email(event) or "system@example.com"
        
        logger.info(f"Delete operation performed by user: {user_info.get('username')} ({email})")

        params = {'id': id}  # Parameters for DynamoDB operations

        # Validate the request against a predefined schema
        try:
            validation_schema = validate_request_datas_schema(action, datas)
        except Exception as validation_err:
            logger.error(f"Error during schema validation: {str(validation_err)}")
            response_result = Responses.result_response(STATUS_ERROR, False, 'Schema validation error.')
            send_to_client(connectionId, json.dumps(construct_response(response_result)), url)
            return {
                'statusCode': STATUS_ERROR,
                'body': json.dumps('Schema validation error')
            }
        
        if not validation_schema['success']:
            # Respond with validation errors if schema validation fails
            response_result = Responses.result_response(STATUS_UNPROCESSABLE_ENTITY, False, 'Validation errors.', validation_schema)
            send_to_client(connectionId, json.dumps(construct_response(response_result)), url)
            return {
                'statusCode': STATUS_UNPROCESSABLE_ENTITY,
                'body': json.dumps('Validation errors.')
            }

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
        except Exception as db_err:
            logger.error(f"Database error: {str(db_err)}")
            response_result = Responses.result_response(STATUS_ERROR, False, 'Database error during operation.')
    except Exception as err:
        # Log and respond with an error for any unexpected exceptions
        logger.error(f"Unexpected error: {str(err)}", exc_info=True)
        response_result = Responses.result_response(STATUS_ERROR, False, f"Internal server error: {str(err)}")
        send_to_client(connectionId, json.dumps(construct_response(response_result)), url)
        return {
            'statusCode': STATUS_ERROR,
            'body': json.dumps('Internal server error')
        }

    # Send the constructed response back to the client via WebSocket
    try:
        send_to_client(connectionId, json.dumps(construct_response(response_result)), url)
    except Exception as websocket_err:
        logger.error(f"Error sending response to client: {str(websocket_err)}")
        # Don't return error here as the main operation might have succeeded

    return {
        'statusCode': STATUS_DELETED,  # Return a success status code
        'body': json.dumps('Message processed')  # Return a success message
    }