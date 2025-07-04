# Import necessary modules and packages
import os
import json
import boto3
import logging
from datetime import datetime
from src.helpers.api_responses import Responses
from src.helpers.construct_response import construct_response
from src.helpers.schema_validation import validate_request_datas_schema
from src.handler_websocket.handler import send_to_client
from src.helpers.event_utils import extract_event_info  # Custom helper to extract necessary information from the event
from src.helpers.decimal_converter import convert_decimal_to_json_serializable as decimal_to_json_serializable  # Custom helper to convert Decimal objects
from src.helpers.auth_middleware import authenticate_websocket, get_user_email, get_authenticated_user  # Cognito authentication
from src.helpers.scope_manager import require_resource_permission  # Scope validation

"""
/**
 * @asyncapi
 * channels:
 *   templateUpdate:
 *     description: Channel for updating a template by ID.
 *     publish:
 *       operationId: templateUpdate
 *       summary: Update a template by ID.
 *       message:
 *         messageId: templateUpdate
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
 *               example: update
 *             datas:
 *               type: object
 *               required:
 *                 - id
 *               properties:
 *                 id:
 *                   type: string
 *                   description: The unique identifier of the template to update.
 *                   example: 123e4567-e89b-12d3-a456-426614174000
 *                 templateCompany:
 *                   type: string
 *                   description: Template company name.
 *                   example: Company Name
 *                 templateAgent:
 *                   type: string
 *                   description: Template agent name.
 *                   example: Agent Name
 *                 templateRootCause:
 *                   type: string
 *                   description: Template root cause.
 *                   example: Root Cause
 *                 templateAgentValidation:
 *                   type: boolean
 *                   description: Template agent validation.
 *                   example: true
 *                 templateIntentFailed:
 *                   type: boolean
 *                   description: Template intent failed.
 *                   example: false
 *                 isActive:
 *                   type: boolean
 *                   description: Is active or not.
 *                   example: true
 *                 templateActions:
 *                   type: array
 *                   items:
 *                     type: object
 *                     properties:
 *                       templateActionsTimeStamp:
 *                         type: integer
 *                         description: Timestamp of the action.
 *                         example: 1639172876
 *                       templateActionsTag:
 *                         type: string
 *                         description: Tag of the action.
 *                         example: Tag Action
 *                 templateStatus:
 *                   type: string
 *                   description: Template status.
 *                   example: Template Status
 *     subscribe:
 *       operationId: templateUpdateResponse
 *       summary: Receive response for the updated template.
 *       message:
 *         $ref: '#/components/messages/TemplateUpdateResponse'
 */
"""

# Initialize logger for the module
logger = logging.getLogger(__name__)
logger.setLevel(os.getenv('LOG_LEVEL', 'INFO'))  # Set log level based on environment variable

@authenticate_websocket()  # Require authentication for this handler
@require_resource_permission('PYTHONTEMPLATECDKWEBSOCKET', 'UPDATE')  # Require UPDATE permission for this resource
def edit(event, context):
    """
    Handles the WebSocket edit operation for updating a template in DynamoDB.

    This function processes incoming WebSocket events, validates the request data and updates the specified template in the DynamoDB table.
    It sends a response back to the client via WebSocket.

    :param event: The event data from the WebSocket request.
    :param context: The context in which the function is called.
    :return: The response sent to the client via WebSocket.
    """
    logger.debug('Logging event: %s', event)
    logger.info('Inside WebSocket edit function')

    # Define status codes for various outcomes
    STATUS_ERROR = 500
    STATUS_UNPROCESSABLE_ENTITY = 422
    STATUS_UPDATED = 200
    STATUS_NOT_FOUND = 404

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

    # Extract necessary information from the event
    try:
        event_info = extract_event_info(event)
        url = event_info.get('url')
        connectionId = event_info.get('connectionId')
        
        logger.debug(f"Event info extracted - URL: {url}, ConnectionId: {connectionId}")
        
        # Validate that we have the necessary connection information
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
        # Parse the WebSocket message (expecting a JSON payload in the body)
        logger.debug(f"Raw event body: {event.get('body', 'No body found')}")
        
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
        
        logger.debug(f"Parsed body: {body}")
        
        action = body.get('action')
        datas = body.get('datas', {})
        
        logger.info(f"Action: {action}, Datas: {datas}")

        # Extract ID from datas or path parameters
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
        
        logger.info(f"Extracted ID: {id}")

        # Validate the request and retrieve validation errors
        logger.debug(f"Validating schema for action: {action}")
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
        
        logger.debug(f"Validation result: {validation_schema}")
        
        if not validation_schema['success']:
            logger.warning(f"Validation failed: {validation_schema}")
            response_result = Responses.result_response(STATUS_UNPROCESSABLE_ENTITY, False, 'Validation errors.', validation_schema)
            send_to_client(connectionId, json.dumps(construct_response(response_result)), url)
            return {
                'statusCode': STATUS_UNPROCESSABLE_ENTITY,
                'body': json.dumps('Validation failed')
            }

        # TODO: Replace with actual user email from authentication context
        # Get the authenticated user's email from the JWT token
        user_info = get_authenticated_user(event)
        email = get_user_email(event) or "system@example.com"
        
        logger.info(f"Operation performed by user: {user_info.get('username')} ({email})")
        
        validation_schema['datas']['updatedBy'] = email
        
        logger.debug(f"Validated data before update: {validation_schema['datas']}")

        # Clean up the id field to prevent overwriting it
        if 'id' in datas:
            del datas['id']
        if 'id' in validation_schema['datas']:
            del validation_schema['datas']['id']

        # Generate update expression for DynamoDB
        expression = generate_update_query(validation_schema['datas'])

        # Check if the item exists in DynamoDB
        try:
            existing_item = table.get_item(Key={'id': id})
            if 'Item' not in existing_item:
                logger.warning(f"Item with ID {id} not found in database")
                response_result = Responses.result_response(STATUS_NOT_FOUND, False, f'Item with ID {id} not found.')
                send_to_client(connectionId, json.dumps(construct_response(response_result)), url)
                return {
                    'statusCode': STATUS_NOT_FOUND,
                    'body': json.dumps('Item not found')
                }
        except Exception as db_err:
            logger.error(f"Error checking item existence: {str(db_err)}")
            response_result = Responses.result_response(STATUS_ERROR, False, 'Database error during item lookup.')
            send_to_client(connectionId, json.dumps(construct_response(response_result)), url)
            return {
                'statusCode': STATUS_ERROR,
                'body': json.dumps('Database error')
            }
        # Update the item in DynamoDB
        try:
            updated_item = table.update_item(
                Key={'id': id},
                ExpressionAttributeNames=expression['ExpressionAttributeNames'],
                ExpressionAttributeValues=expression['ExpressionAttributeValues'],
                UpdateExpression=expression['UpdateExpression'],
                ReturnValues='ALL_NEW'
            )

            # Convert Decimal types to JSON-serializable types
            serializable_attributes = decimal_to_json_serializable(updated_item['Attributes'])

            # Build a successful response with the updated attributes
            response_result = Responses.result_response(STATUS_UPDATED, True, f'Item with ID {id} updated successfully.', serializable_attributes)
            
        except Exception as update_err:
            logger.error(f"Error updating item in database: {str(update_err)}")
            response_result = Responses.result_response(STATUS_ERROR, False, 'Database error during item update.')
            send_to_client(connectionId, json.dumps(construct_response(response_result)), url)
            return {
                'statusCode': STATUS_ERROR,
                'body': json.dumps('Database error')
            }

    except json.JSONDecodeError as json_err:
        # Handle JSON parsing errors specifically
        logger.error(f"JSON decode error: {str(json_err)}")
        response_result = Responses.result_response(STATUS_UNPROCESSABLE_ENTITY, False, f"Invalid JSON format: {str(json_err)}")
        send_to_client(connectionId, json.dumps(construct_response(response_result)), url)
        return {
            'statusCode': STATUS_UNPROCESSABLE_ENTITY,
            'body': json.dumps('Invalid JSON format')
        }
    except KeyError as key_err:
        # Handle missing key errors
        logger.error(f"Missing required key: {str(key_err)}")
        response_result = Responses.result_response(STATUS_UNPROCESSABLE_ENTITY, False, f"Missing required field: {str(key_err)}")
        send_to_client(connectionId, json.dumps(construct_response(response_result)), url)
        return {
            'statusCode': STATUS_UNPROCESSABLE_ENTITY,
            'body': json.dumps('Missing required field')
        }
    except Exception as err:
        # In case of error, log and build an error response
        logger.error(f"Unexpected error during item update: {str(err)}", exc_info=True)
        response_result = Responses.result_response(STATUS_ERROR, False, f"Internal server error: {str(err)}")
        send_to_client(connectionId, json.dumps(construct_response(response_result)), url)
        return {
            'statusCode': STATUS_ERROR,
            'body': json.dumps('Internal server error')
        }

    # Send the response to the client
    try:
        send_to_client(connectionId, json.dumps(construct_response(response_result)), url)
    except Exception as websocket_err:
        logger.error(f"Error sending response to client: {str(websocket_err)}")
        # Don't return error here as the main operation might have succeeded

    return {
        'statusCode': STATUS_UPDATED,
        'body': json.dumps('Message processed')
    }

def generate_update_query(fields):
    """
    Generates a DynamoDB update expression for the given fields.

    This function constructs an update expression, along with attribute names and values,
    to be used in a DynamoDB update operation. It ensures that the 'updatedAt' field is
    always set to the current timestamp.

    :param fields: A dictionary of fields to be updated in the DynamoDB item.
    :return: A dictionary containing the update expression, attribute names, and values.
    """
    # Set updated date to current timestamp in RFC 3339 format
    rfc3339_date = datetime.now().isoformat()
    update_expression = {
        'UpdateExpression': 'SET #updatedAt = :updatedAt,',
        'ExpressionAttributeNames': {'#updatedAt': 'updatedAt'},
        'ExpressionAttributeValues': {':updatedAt': rfc3339_date},
    }

    # Construct the update expression for each field
    for key, value in fields.items():
        update_expression['UpdateExpression'] += f" #{key} = :{key},"
        update_expression['ExpressionAttributeNames'][f"#{key}"] = key
        update_expression['ExpressionAttributeValues'][f":{key}"] = value

    # Remove trailing comma from the UpdateExpression
    update_expression['UpdateExpression'] = update_expression['UpdateExpression'][:-1]

    return update_expression