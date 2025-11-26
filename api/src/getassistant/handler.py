import json  # Import JSON module for parsing and generating JSON data
import os  # Import OS module for interacting with the operating system
import boto3  # Import Boto3, the AWS SDK for Python, to interact with AWS services
import logging  # Import logging module to log messages
from botocore.exceptions import ClientError  # Import specific exceptions from BotoCore
from boto3.dynamodb.conditions import Attr

# Import custom helper modules for API responses, response construction, schema validation, WebSocket communication, and event information extraction
from src.helpers.api_responses import Responses
from src.helpers.construct_response import construct_response
from src.helpers.schema_validation import validate_request_datas_schema_pydantic
from src.handler_websocket.handler import send_to_client
from src.helpers.event_utils import extract_event_info
from src.helpers.decimal_converter import convert_decimal_to_json_serializable as decimal_to_json_serializable  # Custom helper to convert Decimal objects
from src.helpers.auth_middleware import authenticate_websocket, get_user_email, get_authenticated_user  # Cognito authentication
from src.helpers.scope_manager import require_resource_permission  # Scope validation

"""
/**
 * @asyncapi
 * channels:
 *   chatGetAssistant:
 *     description: Channel for retrieving a specific chat by assistant ID.
 *     publish:
 *       operationId: chatGetAssistant
 *       summary: Get a specific chat by assistant ID.
 *       message:
 *         messageId: chatGetAssistant
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
 *               example: getassistant
 *             datas:
 *               type: object
 *               required:
 *                 - id
 *               properties:
 *                 id:
 *                   type: string
 *                   description: The unique identifier of the chat to retrieve.
 *                   example: 184cf8da-b821-4ff4-bd6c-cdafa166e2e0
 *     subscribe:
 *       operationId: chatGetAssistantResponse
 *       summary: Receive response for the retrieved chat.
 *       message:
 *         $ref: '#/components/messages/chatGetAssistantResponse'
 */
"""

# Configure the logger for the module
logger = logging.getLogger(__name__)
logger.setLevel(os.getenv('LOG_LEVEL', 'INFO'))  # Set the log level based on environment variable or default to 'INFO'

@authenticate_websocket()  # Require authentication for this handler
# @require_resource_permission('PYTHONTEMPLATECDKWEBSOCKET', 'READ')  # Require READ permission for this resource
def getassistant(event, context):
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
            'body': json.dumps(construct_response(response_result))
        }

    # Extract connectionId and url early for error handling
    connectionId, url = None, None
    try:
        connectionId, url = extract_event_info(event)
    except Exception:
        pass

    try:
        # Extract action and datas from event
        action = event.get('action')
        datas = event.get('datas')
        logger.info(f"Action: {action}, Datas: {datas}")
        if datas is None:
            datas = {}

        # Extract the ID from datas
        id = datas.get('id') if isinstance(datas, dict) else None
        if not id:
            logger.warning(f"Missing ID parameter in request. Datas: {datas}")
            response_result = Responses.result_response(STATUS_UNPROCESSABLE_ENTITY, False, 'ID parameter is required in datas.')
            if connectionId and url:
                send_to_client(connectionId, json.dumps(construct_response(response_result)), url)
            return {
                'statusCode': STATUS_UNPROCESSABLE_ENTITY,
                'body': json.dumps('ID parameter is required in datas.')
            }

        logger.info(f"Extracted ID: {id}")
        user_info = get_authenticated_user(event)
        email = get_user_email(event) or "system@example.com"
        logger.info(f"Get operation performed by user: {user_info.get('username')} ({email})")

        # Validate the request data against a predefined schema
        try:
            validation_schema = validate_request_datas_schema_pydantic(action, datas, logger)
        except Exception as validation_err:
            logger.error(f"Error during schema validation: {str(validation_err)}")
            response_result = Responses.result_response(STATUS_ERROR, False, 'Schema validation error.')
            if connectionId and url:
                send_to_client(connectionId, json.dumps(construct_response(response_result)), url)
            return {
                'statusCode': STATUS_ERROR,
                'body': json.dumps('Schema validation error')
            }

        if not validation_schema['success']:
            logger.warning(f"Validation failed for action: {action}, datas: {datas}. Errors: {validation_schema}")
            response_result = Responses.result_response(STATUS_UNPROCESSABLE_ENTITY, False, 'Validation errors.', validation_schema)
            if connectionId and url:
                send_to_client(connectionId, json.dumps(construct_response(response_result)), url)
            return {
                'statusCode': STATUS_UNPROCESSABLE_ENTITY,
                'body': json.dumps('Validation errors.')
            }

        # Initialize DynamoDB resource and table
        dynamodb = boto3.resource('dynamodb')
        table = dynamodb.Table(table_name)

        # Paginated scan for items with assistantId
        all_items = []
        last_evaluated_key = None
        while True:
            scan_kwargs = {
                'FilterExpression': Attr('assistantId').eq(id)
            }
            if last_evaluated_key:
                scan_kwargs['ExclusiveStartKey'] = last_evaluated_key
            response = table.scan(**scan_kwargs)
            all_items.extend(response.get('Items', []))
            last_evaluated_key = response.get('LastEvaluatedKey')
            if not last_evaluated_key:
                break
        logger.info(f"Paginated scan response: Found {len(all_items)} items with assistantId {id}")

        # If no items at all
        if not all_items:
            response_result = Responses.result_response(STATUS_NOT_FOUND, False, f'Assistant with ID {id} not found.')
            logger.info("response: %s", response_result)
            if connectionId and url:
                send_to_client(connectionId, json.dumps(construct_response(response_result)), url)
            return {
                'statusCode': STATUS_NOT_FOUND,
                'body': json.dumps(construct_response(response_result))
            }

        # Filter items owned by the current user
        email_clean = email.strip()
        user_items = [item for item in all_items if item.get("createdBy", "").strip() == email_clean]
        logger.info(f"Items after createdBy filter: {len(user_items)}")

        if user_items:
            formatted_items = []
            for item in user_items:
                conversation = {
                    "conversationId": item.get("conversationId"),
                    "title": item.get("title", ""),
                    "createdAt": item.get("createdAt", ""),
                    "updatedAt": item.get("updatedAt", ""),
                    "assistantId": item.get("assistantId", ""),
                    "status": item.get("status", "active")
                }
                formatted_items.append(conversation)
            formatted_items.sort(key=lambda x: x["createdAt"], reverse=True)
            serializable_items = decimal_to_json_serializable(formatted_items)
            formatted_result = {"item": serializable_items, "count": len(user_items)}
            response_result = Responses.result_response(STATUS_FOUND, True, f'Item with ID {id} found.', formatted_result)
            if connectionId and url:
                send_to_client(connectionId, json.dumps(construct_response(response_result)), url)
            return {
                'statusCode': STATUS_FOUND,
                'body': json.dumps(construct_response(response_result))
            }
        else:
            empty_result = {"item": [], "count": 0}
            response_result = Responses.result_response(STATUS_FOUND, True, f'No items found for assistant ID {id}.', empty_result)
            logger.info("Items found but none owned by user, returning empty response: %s", response_result)
            if connectionId and url:
                send_to_client(connectionId, json.dumps(construct_response(response_result)), url)
            return {
                'statusCode': STATUS_FOUND,
                'body': json.dumps(construct_response(response_result))
            }
    except Exception as err:
        logger.error(f"Unexpected error: {str(err)}", exc_info=True)
        response_result = Responses.result_response(STATUS_ERROR, False, f"Internal server error: {str(err)}")
        if connectionId and url:
            send_to_client(connectionId, json.dumps(construct_response(response_result)), url)
        return {
            'statusCode': STATUS_ERROR,
            'body': json.dumps('Internal server error')
        }

    # ...existing code ends here...