# Import necessary modules and packages
import os
import json
import boto3
import logging
from datetime import datetime
from src.helpers.check_authorization import check_authorization
from src.helpers.api_responses import Responses
from src.helpers.construct_response import construct_response
from src.helpers.schema_validation import validate_request_datas_schema
from src.handler_websocket.handler import send_to_client
from src.helpers.event_utils import extract_event_info  # Custom helper to extract necessary information from the event

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
 *             - id
 *             - templateCompany
 *             - templateAgent
 *             - templateActionsTag
 *             - templateActionsTimeStamp
 *           properties:
 *             id:
 *               type: string
 *               description: Use template's ID.
 *             templateCompany:
 *               type: string
 *               description: Template company name.
 *               example: Company Name
 *             templateAgent:
 *               type: string
 *               description: Template agent name.
 *               example: Agent Name
 *             templateRootCause:
 *               type: string
 *               description: Template root cause.
 *               example: Root Cause
 *             templateAgentValidation:
 *               type: boolean
 *               description: Template agent validation.
 *               example: true
 *             isActive:
 *               type: boolean
 *               description: Is active or not.
 *               example: true
 *             templateIntentFailed:
 *               type: boolean
 *               description: Template intent failed.
 *               example: false
 *             templateActions:
 *               type: array
 *               items:
 *                 type: object
 *                 properties:
 *                   templateActionsTimeStamp:
 *                     type: string
 *                     description: Timestamp of the action.
 *                     example: 1639172876
 *                   templateActionsTag:
 *                     type: string
 *                     description: Tag of the action.
 *                     example: Tag Action
 *             templateStatus:
 *               type: string
 *               description: Template status.
 *               example: Template Status
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

def edit(event, context):
    """
    Handles the WebSocket edit operation for updating a template in DynamoDB.

    This function processes incoming WebSocket events, validates the request data,
    checks authorization, and updates the specified template in the DynamoDB table.
    It sends a response back to the client via WebSocket.

    :param event: The event data from the WebSocket request.
    :param context: The context in which the function is called.
    :return: The response sent to the client via WebSocket.
    """
    logger.debug('Logging event: %s', event)
    logger.info('Inside WebSocket edit function')

    # Initialize DynamoDB resource and table
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(os.getenv('TABLE'))

    # Define status codes for various outcomes
    STATUS_ERROR = 500
    STATUS_UNPROCESSABLE_ENTITY = 422
    STATUS_UPDATED = 200
    STATUS_NOT_FOUND = 404

    # Extract necessary information from the event
    event_info = extract_event_info(event)
    url = event_info.get('url')
    connectionId = event_info.get('connectionId')

    try:
        # Parse the WebSocket message (expecting a JSON payload in the body)
        body = json.loads(event['body'])
        datas = body.get('datas', {})
        action = body.get('action')
        id = body.get('id')  # Assuming the 'id' comes from the body

        # Check if 'id' is provided in the request
        if not id:
            response_result = Responses.result_response(STATUS_UNPROCESSABLE_ENTITY, False, 'ID is required.')
            return send_to_client(connectionId, json.dumps(construct_response(response_result)), url)

        datas['id'] = id  # Ensure ID is part of the data

        # Validate the request and retrieve validation errors
        validation_schema = validate_request_datas_schema(action, datas)
        if not validation_schema['success']:
            response_result = Responses.result_response(STATUS_UNPROCESSABLE_ENTITY, False, 'Validation errors.', validation_schema)
            return send_to_client(connectionId, json.dumps(construct_response(response_result)), url)

        # Check authorization and get the email of the user
        email = check_authorization(event)
        validation_schema['datas']['updatedBy'] = email

        # Clean up the id field to prevent overwriting it
        if 'id' in datas:
            del datas['id']
        if 'id' in validation_schema['datas']:
            del validation_schema['datas']['id']

        # Generate update expression for DynamoDB
        expression = generate_update_query(validation_schema['datas'])

        # Check if the item exists in DynamoDB
        existing_item = table.get_item(Key={'id': id})
        if 'Item' not in existing_item:
            response_result = Responses.result_response(STATUS_NOT_FOUND, False, f'Item with ID {id} not found.')
        else:
            # Update the item in DynamoDB
            updated_item = table.update_item(
                Key={'id': id},
                ExpressionAttributeNames=expression['ExpressionAttributeNames'],
                ExpressionAttributeValues=expression['ExpressionAttributeValues'],
                UpdateExpression=expression['UpdateExpression'],
                ReturnValues='ALL_NEW'
            )

            # Build a successful response with the updated attributes
            response_result = Responses.result_response(STATUS_UPDATED, True, f'Item with ID {id} updated successfully.', updated_item['Attributes'])

    except Exception as err:
        # In case of error, log and build an error response
        logger.error(f"Error during item update: {str(err)}")
        response_result = Responses.result_response(STATUS_ERROR, False, f"Error occurred: {str(err)}")

    # Send the constructed response via WebSocket
    return send_to_client(connectionId, json.dumps(construct_response(response_result)), url)

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