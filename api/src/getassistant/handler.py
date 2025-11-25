

import os
import json
import boto3
import logging
from botocore.exceptions import ClientError
from src.helpers.api_responses import Responses
from src.helpers.construct_response import construct_response
from src.helpers.schema_validation import validate_request_datas_schema_pydantic
from src.handler_websocket.handler import send_to_client
from src.helpers.event_utils import extract_event_info
from src.helpers.decimal_converter import convert_decimal_to_json_serializable as decimal_to_json_serializable
from src.helpers.auth_middleware import authenticate_websocket, get_authenticated_user, get_user_email

logger = logging.getLogger(__name__)
logger.setLevel(os.getenv('LOG_LEVEL', 'INFO'))

@authenticate_websocket()
def getassistant(event, context):
    """
    Retrieves chat items from DynamoDB by assistantId, filtered by authenticated user.
    Sends response via WebSocket.
    """
    logger.debug('Event: %s', event)
    logger.info('Inside getassistant function')

    STATUS_ERROR = 500
    STATUS_UNPROCESSABLE_ENTITY = 422
    STATUS_NOT_FOUND = 404
    STATUS_FOUND = 200

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

    try:
        event_info = extract_event_info(event)
        url = event_info.get('url')
        connectionId = event_info.get('connectionId')
        if not connectionId:
            logger.error("Connection ID not found in event")
            return {
                'statusCode': STATUS_ERROR,
                'body': json.dumps('Connection ID not found in event')
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
        raw_body = event.get('body')
        if raw_body is None:
            body = {}
        elif isinstance(raw_body, str):
            try:
                body = json.loads(raw_body)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON body: {e}")
                response_result = Responses.result_response(STATUS_UNPROCESSABLE_ENTITY, False, 'Invalid JSON format in request body.')
                send_to_client(connectionId, json.dumps(construct_response(response_result)), url)
                return {
                    'statusCode': STATUS_UNPROCESSABLE_ENTITY,
                    'body': json.dumps('Invalid JSON format in request body.')
                }
        elif isinstance(raw_body, dict):
            body = raw_body
        else:
            response_result = Responses.result_response(STATUS_UNPROCESSABLE_ENTITY, False, 'Invalid body format.')
            send_to_client(connectionId, json.dumps(construct_response(response_result)), url)
            return {
                'statusCode': STATUS_UNPROCESSABLE_ENTITY,
                'body': json.dumps('Invalid body format.')
            }

        action = body.get('action')
        datas = body.get('datas')
        if datas is None:
            datas = {}
        assistant_id = datas.get('id') if isinstance(datas, dict) else None
        if not assistant_id:
            response_result = Responses.result_response(STATUS_UNPROCESSABLE_ENTITY, False, 'assistantId (id) parameter is required in datas.')
            send_to_client(connectionId, json.dumps(construct_response(response_result)), url)
            return {
                'statusCode': STATUS_UNPROCESSABLE_ENTITY,
                'body': json.dumps('assistantId (id) parameter is required in datas.')
            }

        user_info = get_authenticated_user(event)
        email = get_user_email(event) or "system@example.com"
        logger.info(f"GetAssistant operation performed by user: {user_info.get('username', '')} ({email})")

        # Validate request data
        try:
            validation_schema = validate_request_datas_schema_pydantic(action, datas, logger)
        except Exception as validation_err:
            logger.error(f"Error during schema validation: {str(validation_err)}")
            response_result = Responses.result_response(STATUS_ERROR, False, 'Schema validation error.')
            send_to_client(connectionId, json.dumps(construct_response(response_result)), url)
            return {
                'statusCode': STATUS_ERROR,
                'body': json.dumps('Schema validation error')
            }
        if not validation_schema['success']:
            response_result = Responses.result_response(STATUS_UNPROCESSABLE_ENTITY, False, 'Validation errors.', validation_schema)
            send_to_client(connectionId, json.dumps(construct_response(response_result)), url)
            return {
                'statusCode': STATUS_UNPROCESSABLE_ENTITY,
                'body': json.dumps('Validation errors.')
            }

        # Query DynamoDB for items with assistantId
        try:
            scan_kwargs = {
                'FilterExpression': 'assistantId = :assistant_id',
                'ExpressionAttributeValues': {':assistant_id': assistant_id}
            }
            response = table.scan(**scan_kwargs)
            items = response.get('Items', [])
            # Filter items by createdBy == email
            user_items = [item for item in items if item.get('createdBy', '').strip() == email.strip()]
            logger.info(f"Found {len(user_items)} items for assistantId {assistant_id} and user {email}")
            if user_items:
                serializable_items = decimal_to_json_serializable(user_items)
                result = {'items': serializable_items, 'count': len(user_items)}
                response_result = Responses.result_response(STATUS_FOUND, True, f'Items for assistantId {assistant_id} found.', result)
                status_code = STATUS_FOUND
            else:
                result = {'items': [], 'count': 0}
                response_result = Responses.result_response(STATUS_FOUND, True, f'No items found for assistantId {assistant_id}.', result)
                status_code = STATUS_FOUND
        except ClientError as e:
            logger.error(f"DynamoDB ClientError: {e.response['Error']['Message']}")
            response_result = Responses.result_response(STATUS_ERROR, False, 'Error accessing DynamoDB.')
            status_code = STATUS_ERROR
        except Exception as db_err:
            logger.error(f"Database error: {str(db_err)}")
            response_result = Responses.result_response(STATUS_ERROR, False, 'Database error during operation.')
            status_code = STATUS_ERROR
    except Exception as err:
        logger.error(f"Unexpected error: {str(err)}", exc_info=True)
        response_result = Responses.result_response(STATUS_ERROR, False, f"Internal server error: {str(err)}")
        send_to_client(connectionId, json.dumps(construct_response(response_result)), url)
        return {
            'statusCode': STATUS_ERROR,
            'body': json.dumps('Internal server error')
        }

    # Send the response to the client via WebSocket
    try:
        send_to_client(connectionId, json.dumps(construct_response(response_result)), url)
    except Exception as websocket_err:
        logger.error(f"Error sending response to client: {str(websocket_err)}")
        # Don't return error here as the main operation might have succeeded

    return {
        'statusCode': status_code,
        'body': json.dumps('Message sent successfully.')
    }
