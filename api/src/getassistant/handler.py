import json  # Import JSON module for parsing and generating JSON data
import os  # Import OS module for interacting with the operating system
import boto3  # Import Boto3, the AWS SDK for Python, to interact with AWS services
import logging  # Import logging module to log messages
from botocore.exceptions import ClientError  # Import specific exceptions from BotoCore
from boto3.dynamodb.conditions import Attr
from botocore.config import Config

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


config = Config(
    max_pool_connections=50,
    retries={'max_attempts': 3, 'mode': 'adaptive'},
    connect_timeout=5,
    read_timeout=30
)

# Initialize clients with connection pooling
dynamodb_resource = boto3.resource('dynamodb', config=config)
apigateway_client = boto3.client('apigatewaymanagementapi', config=config)

@authenticate_websocket()  # Require authentication for this handler
@require_resource_permission('CHAT', 'READ')  # Require READ permission for this resource
def getassistant(event, context):
    """
    Handles the retrieval of a template item from a DynamoDB table based on the provided ID.
    
    This function processes incoming WebSocket events, validates the request data, 
    interacts with DynamoDB to retrieve the item, and sends the response back to the client.
    
    :param event: The event data received from the WebSocket, containing the request details.
    :param context: The context in which the function is executed, providing runtime information.
    :return: A dictionary containing the HTTP status code and a message indicating the result of the operation.
    """
    logger.debug('Event: %s', event)  
    logger.info('Inside getassistant function')  

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

        url = event_info.get("url")
        connectionId = event_info.get("connectionId")
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

    logger.info(f"Retrieving item for authenticated user: {email} (ID: {user_id})")

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
            datas = body.get("datas", {})
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
            'statusCode': response_result['status_code'],
            'body': response_result['body']
        }

    try:
        validation_schema = validate_request_datas_schema_pydantic(action, datas, logger)
        if not validation_schema['success']:
            response_result = Responses.result_response(422, False, 'Validation errors.', validation_schema)
            logger.debug('Validation failed: %s', validation_schema)
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
        logger.info("assistant id: %s", id)

        all_items = []
        last_evaluated_key = None
        scan_count = 0
        while True:
            scan_count += 1
            scan_kwargs = {
                "FilterExpression": "assistantId = :assistant_id AND isActive = :is_active",
                "ExpressionAttributeValues": {
                    ":assistant_id": id,
                    ":is_active": True
                },
                "Limit": 1000  # Process in batches of 1000
            }
            if last_evaluated_key:
                scan_kwargs["ExclusiveStartKey"] = last_evaluated_key
            
            response = table.scan(**scan_kwargs)
            current_items = response.get('Items', [])
            all_items.extend(current_items)
            last_evaluated_key = response.get('LastEvaluatedKey')
            
            logger.info(f"Scan batch {scan_count}: Found {len(current_items)} items, Total so far: {len(all_items)}")
            
            if not last_evaluated_key:
                break
                
        logger.info(f"Paginated scan complete: Found {len(all_items)} total items with assistantId {id} in {scan_count} batches")

        if len(all_items) > 0:
            formatted_items = []

            # Find items owned by the current user with robust filtering
            email_clean = email.strip()
            user_items = [item for item in all_items if item.get("createdBy", "").strip() == email_clean]

            logger.info(f"Items after createdBy filter: {len(user_items)}")

            if user_items:
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

                response_result = Responses.result_response(200, True, f'Item with ID {id} found.', formatted_result)
                send_to_client(connectionId, json.dumps(construct_response(response_result)), url)
                return {
                    'statusCode': 200,
                    'body': json.dumps(construct_response(response_result))
                }
            else:
                empty_result = {"item": [], "count": 0}
                response_result = Responses.result_response(200, True, f'No items found for assistant ID {id}.', empty_result)
                logger.info("Items found but none owned by user, returning empty response: %s", response_result)
                send_to_client(connectionId, json.dumps(construct_response(response_result)), url)
                return {
                    'statusCode': 200,
                    'body': json.dumps(construct_response(response_result))
                }
        else:
            response_result = Responses.result_response(404, False, f'Assistant with ID {id} not found.')
            logger.info("response: %s", response_result)
            send_to_client(connectionId, json.dumps(construct_response(response_result)), url)
            return {
                'statusCode': 404,
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

    except Exception as err:
        logger.error(f"Unexpected error: {str(err)}", exc_info=True)
        response_result = Responses.result_response(500, False, f"Internal server error: {str(err)}")
        send_to_client(connectionId, json.dumps(construct_response(response_result)), url)
        return {
            'statusCode': 500,
            'body': json.dumps('Internal server error')
        }