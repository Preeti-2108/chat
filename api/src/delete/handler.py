# Import necessary modules and packages
import json  # For handling JSON data
import os  # For accessing environment variables
import boto3  # AWS SDK for Python to interact with AWS services
import logging  # For logging information and errors
from botocore.exceptions import ClientError  # Exception for AWS client errors
from botocore.config import Config  # For configuring AWS clients
from src.helpers.api_responses import Responses  # Custom response handling
from src.helpers.construct_response import construct_response  # Helper to construct responses
from src.helpers.schema_validation import validate_request_datas_schema_pydantic  # Schema validation utility
from src.handler_websocket.handler import send_to_client  # WebSocket communication utility
from src.helpers.event_utils import extract_event_info  # Utility to extract information from events
from src.helpers.auth_middleware import authenticate_websocket, get_user_email, get_authenticated_user  # Cognito authentication
from src.helpers.scope_manager import require_resource_permission  # Scope validation
from src.helpers.queue_helper import send_message_to_queue

# Configure connection pooling for better performance
config = Config(
    max_pool_connections=50,
    retries={'max_attempts': 3, 'mode': 'adaptive'},
    connect_timeout=5,
    read_timeout=30
)

# Initialize clients with connection pooling
dynamodb_resource = boto3.resource('dynamodb', config=config)
apigateway_client = boto3.client('apigatewaymanagementapi', config=config)


"""
/**
 * @asyncapi
 * channels:
 *   chatDelete:
 *     description: Channel for deleting a specific chat by ID.
 *     publish:
 *       operationId: chatDelete
 *       summary: Delete a specific chat.
 *       message:
 *         messageId: chatDelete
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
 *                   description: The unique identifier of the chat to delete.
 *                   example: 123e4567-e89b-12d3-a456-426614174000
 *     subscribe:
 *       operationId: chatDeleteResponse
 *       summary: Receive response for the deleted chat.
 *       message:
 *         $ref: '#/components/messages/chatDeleteResponse'
 */
"""

# Configure logger for the module
logger = logging.getLogger(__name__)
logger.setLevel(os.getenv('LOG_LEVEL', 'INFO'))  # Set log level based on environment variable

@authenticate_websocket()  # Require authentication for this handler
@require_resource_permission('CHAT', 'DELETE')  # Require DELETE permission for this resource
def delete(event, context):
    """
    Handles the deletion of a template based on the provided event data.
    
    Args:
        event (dict): The event data containing information about the request.
        context (object): The context in which the function is executed.

    Returns:
        dict: A response object with status code and message.
    """
    # Event logged at debug level  
    logger.info('Inside delete function') 
        
    table_name = os.getenv('TABLE')
    if not table_name:
        logger.error("TABLE environment variable is not set")
        response_result = Responses.result_response(500, False, 'Configuration error: TABLE environment variable not set.')
        return {
            'statusCode': 500,
            'body': json.dumps('Configuration error')
        }
    
    table = dynamodb_resource.Table(table_name)
    logger.info("DynamoDB Table initialized: %s", table_name)

    try:
        event_info = extract_event_info(event)
        # Event info extracted

        url = event_info.get("url")
        connectionId = event_info.get("connectionId")

        # URL extracted
        # Connection ID extracted
        if not connectionId:
            logger.error("No connection ID found in event. Connection ID is required")
            return {
                'statusCode': 400,
                'body': json.dumps('Missing !!! Connection ID is required')
            }
    except Exception as event_err:
        logger.error(f"Error extracting event info: {str(event_err)}")
        return {
            'statusCode': 400,
            'body': json.dumps('Error processing event')
        }

    # Get authenticated user info from the JWT token (added by auth middleware)
    user_info = event.get('auth', {}).get('user_info', {})
    if not user_info or user_info is None:
        logger.error("No user info found in event.")
        response_result = Responses.result_response(401, False, message="Unauthorized: No user info found")
        send_to_client(connectionId, json.dumps(construct_response(response_result)), url)
        return {
            'statusCode': 401,
            'body': json.dumps('Unauthorized: No user info found')
        }
    else:
        email = user_info.get('email', 'unknown@example.com')
        username = user_info.get('username', 'unknown')
        user_id = user_info.get('user_id', 'unknown')

    logger.info("Retrieving item for authenticated user");

    try:
        body = json.loads(event.get("body", "{}"))
        if body is None:
            logger.error("Request body is None")
            response_result = Responses.result_response(400, False, message="Request body cannot be empty")
            send_to_client(connectionId, json.dumps(construct_response(response_result)), url)
            return {
                'statusCode': 400,
                'body': json.dumps("Request body cannot be empty")
            }
        else:
            action = body.get("action")
            logger.info("Action: %s", action)
            datas = body.get("datas", {})
            logger.info("Datas: %s", datas)
            if not action:
                logger.error("No action found in request body.")
                response_result = Responses.result_response(400, False, message="Missing action")
                send_to_client(connectionId, json.dumps(construct_response(response_result)), url)
                return {
                    'statusCode': 400,
                    'body': json.dumps("Missing action")
                }
            if not datas and datas is None:
                logger.error("No datas found in request body.")
                response_result = Responses.result_response(400, False, message="Missing datas")
                send_to_client(connectionId, json.dumps(construct_response(response_result)), url)
                return {
                    'statusCode': 400,
                    'body': json.dumps("Missing datas")
                }
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing JSON body: {str(e)}")
        response_result = Responses.result_response(400, False, message="Invalid JSON payload")
        send_to_client(connectionId, json.dumps(construct_response(response_result)), url)
        return {
            'statusCode': 400,
            'body': json.dumps("Invalid JSON payload")
        }

    try:
        validation_schema = validate_request_datas_schema_pydantic(action, datas, logger)
        if not validation_schema['success']:
            response_result = Responses.result_response(422, False, 'Validation errors.', validation_schema)
            logger.debug('Validation failed')
            send_to_client(connectionId, json.dumps(construct_response(response_result)), url)
            return {
                'statusCode': 422,
                'body': json.dumps('Validation failed')
            }
    except Exception as validation_err:
        logger.error(f"Error during schema validation: {str(validation_err)}")
        response_result = Responses.result_response(500, False, 'Schema validation error.')
        send_to_client(connectionId, json.dumps(construct_response(response_result)), url)
        return {
            'statusCode': 500,
            'body': json.dumps('Schema validation error')
        }

    try:
        id = validation_schema['datas'].get('id')
        logger.info("Processing delete request")
        
        existing_item = table.get_item(Key={"conversationId": id})
        if 'Item' not in existing_item or existing_item['Item'] is None:
            logger.error("Chat conversation not found")
            response_result = Responses.result_response(404, False, f'Chat conversation with ID {id} not found.')
            logger.info("response: %s", response_result)
            send_to_client(connectionId, json.dumps(construct_response(response_result)), url)
            return {
                'statusCode': 404,
                'body': json.dumps(f'Chat conversation with ID {id} not found.')
            }
        else:
            # Soft delete: set isActive to False
            table.update_item(
                Key={"conversationId": id},
                UpdateExpression="SET isActive = :inactive",
                ExpressionAttributeValues={":inactive": False}
            )
            response_result = Responses.result_response(200, True, f'Chat conversation with ID {id} successfully marked as inactive.')
            logger.info("Item successfully marked as inactive")
            send_to_client(connectionId, json.dumps(construct_response(response_result)), url)
            return {
                'statusCode': 200,
                'body': json.dumps(construct_response(response_result))
            }

    except ClientError as e:
        logger.error(f"DynamoDB ClientError: {e.response['Error']['Message']}")
        response_result = Responses.result_response(500, False, 'Error accessing DynamoDB.')
        send_to_client(connectionId, json.dumps(construct_response(response_result)), url)
        return {
            'statusCode': 500,
            'body': json.dumps('Error accessing DynamoDB')
        }
    except Exception as db_err:
        logger.error(f"Database error: {str(db_err)}")
        response_result = Responses.result_response(500, False, 'Database error during operation.')
        send_to_client(connectionId, json.dumps(construct_response(response_result)), url)
        return {
            'statusCode': 500,
            'body': json.dumps('Database error during operation')
        }
    except Exception as err:
        logger.error(f"Unexpected error: {str(err)}", exc_info=True)
        response_result = Responses.result_response(500, False, f"Internal server error: {str(err)}")
        send_to_client(connectionId, json.dumps(construct_response(response_result)), url)
        return {
            'statusCode': 500,
            'body': json.dumps('Internal server error')
        }
