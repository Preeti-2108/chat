import json  # Import JSON module for parsing and generating JSON data
import os  # Import OS module for interacting with the operating system
import boto3  # Import Boto3, the AWS SDK for Python, to interact with AWS services
import logging  # Import logging module to log messages
from botocore.exceptions import ClientError  # Import specific exceptions from BotoCore
from botocore.config import Config  # Import Config to customize Boto3 client configurations

# Import custom helper modules for API responses, response construction, schema validation, WebSocket communication, and event information extraction
from src.helpers.api_responses import Responses
from src.helpers.construct_response import construct_response
from src.helpers.schema_validation import validate_request_datas_schema
from src.handler_websocket.handler import send_to_client
from src.helpers.event_utils import extract_event_info
from src.helpers.decimal_converter import convert_decimal_to_json_serializable as decimal_to_json_serializable  # Custom helper to convert Decimal objects
from src.helpers.auth_middleware import authenticate_websocket, get_user_email, get_authenticated_user  # Cognito authentication
from src.helpers.scope_manager import require_resource_permission  # Scope validation

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
 *   get:
 *     description: Channel for retrieving a specific template by ID.
 *     publish:
 *       operationId: get
 *       summary: Get a specific template.
 *       message:
 *         messageId: get
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
 *       operationId: getResponse
 *       summary: Receive response for the retrieved template.
 *       message:
 *         $ref: '#/components/messages/chatGetResponse'
 */
"""

# Configure the logger for the module
logger = logging.getLogger(__name__)
logger.setLevel(os.getenv('LOG_LEVEL', 'INFO'))  # Set the log level based on environment variable or default to 'INFO'

@authenticate_websocket()  # Require authentication for this handler
# @require_resource_permission('PYTHONTEMPLATECDKWEBSOCKET', 'READ')  # Require READ permission for this resource
def get(event, context):
    """
    Handles the retrieval of a template item from a DynamoDB table based on the provided ID.
    
    This function processes incoming WebSocket events, validates the request data, 
    interacts with DynamoDB to retrieve the item, and sends the response back to the client.
    
    :param event: The event data received from the WebSocket, containing the request details.
    :param context: The context in which the function is executed, providing runtime information.
    :return: A dictionary containing the HTTP status code and a message indicating the result of the operation.
    """
    logger.debug('Event: %s', event)  
    logger.info('Inside get function')  

    table_name = os.getenv('TABLE')
    if not table_name:
        logger.error("TABLE environment variable is not set")
        response_result = Responses.result_response(500, False, 'Configuration error: TABLE environment variable not set.')
        return {
            'statusCode': 500,
            'body': json.dumps('Configuration error')
        }
    
    # Use the pooled DynamoDB resource
    table = dynamodb_resource.Table(table_name)
    logger.info("DynamoDB Table initialized: %s", table_name)

    try:
        # Extracting event information
        event_info = extract_event_info(event)
        logger.info("Event Info: %s", event_info)

        url = event_info.get("url")
        connectionId = event_info.get("connectionId")

        logger.info("URL: %s", url)
        logger.info("Connection ID: %s", connectionId)
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
        logger.info("conversation id: %s", id)

            response = table.get_item(Key={"conversationId": id})
            
        if "Item" in response and response["Item"] is not None:
            if response["Item"]["createdBy"] == email:
                # Format the conversation like LIST handler
                item = response["Item"]
                conversation = {
                    "conversationId": item.get("conversationId"),
                    "assistantId": item.get("assistantId"),
                    "title": item.get("title"),
                    "createdAt": item.get("createdAt"),
                    "createdBy": item.get("createdBy"),
                    "updatedAt": item.get("updatedAt"),
                    "updatedBy": item.get("updatedBy"),
                    "chatHistory": item.get("chatHistory"),
                    "isActive": item.get("isActive"),
                    "status": item.get("status")
                }
                
                # Create the same format as LIST handler
                formatted_result = {"item": [conversation], "count": 1}
                serializable_result = decimal_to_json_serializable(formatted_result)
                
                logger.info("response: %s", serializable_result)
                response_result = Responses.result_response(200, True, f'Item with ID {id} found.', serializable_result)
                send_to_client(connectionId, json.dumps(construct_response(response_result)), url)
                return {
                    'statusCode': 200,
                    'body': json.dumps(construct_response(response_result))
                }
            else:
                response_result = Responses.result_response(403, False, f'Item with ID {id} found but not owned by {email}.')
                logger.info("response: %s", response_result)
                send_to_client(connectionId, json.dumps(construct_response(response_result)), url)
                return {
                    'statusCode': 403,
                    'body': json.dumps(construct_response(response_result))
                }
        else:
            response_result = Responses.result_response(404, False, f'Item with ID {id} not found.')
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
    
    # Log performance summary at the end