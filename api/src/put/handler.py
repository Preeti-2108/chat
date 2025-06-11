# Import necessary modules for handling environment variables, JSON data, AWS services, logging, and regular expressions
import os
import json
import boto3
import logging
import re
from datetime import datetime

# Import helper functions for authorization checks, API responses, response construction, and schema validation
from src.helpers.check_authorization import check_authorization
from src.helpers.api_responses import Responses
from src.helpers.construct_response import construct_response
from src.helpers.schema_validation import validate_request_body_schema

"""
/**
 * @openapi
 * /{id}:
 *  put:
 *    summary: Update a template sample by ID.
 *    parameters:
 *      - in: path
 *        name: id
 *        required: true
 *        schema:
 *          type: string
 *        description: Use template sample's ID.
 *      - in: header
 *        name: Authorization
 *        description: Access token required for authentication.
 *        required: true
 *        schema:
 *          type: string
 *    requestBody:
 *      description: Object that contains all the data of the item.
 *      required: true
 *      content:
 *        application/json:
 *          schema:
 *            type: object
 *            required:
 *              - templateSampleCompany
 *              - templateSampleAgent
 *              - templateSampleActionsTag
 *              - templateSampleActionsTimeStamp
 *            properties:
 *              templateSampleCompany:
 *                type: string
 *                description: Template sample company name.
 *                example: Company Name
 *              templateSampleAgent:
 *                type: string
 *                description: Template sample agent name.
 *                example: Agent Name
 *              templateSampleRootCause:
 *                type: string
 *                description: Template sample root cause.
 *                example: Root Cause
 *              templateSampleAgentValidation:
 *                type: boolean
 *                description: Template sample agent validation.
 *                example: True
 *              isActive:
 *                type: boolean
 *                description: Is active or not.
 *                example: True
 *              templateSampleIntentFailed:
 *                type: boolean
 *                description: Template sample intent failed.
 *                example: False
 *              templateSampleActions:
 *                type: array
 *                items:
 *                  type: object
 *                  properties:
 *                    templateSampleActionsTimeStamp:
 *                      type: string
 *                      description: Timestamp of the action.
 *                      example: 1639172876
 *                    templateSampleActionsTag:
 *                      type: string
 *                      description: Tag of the action.
 *                      example: Tag Action
 *              templateSampleStatus:
 *                type: string
 *                description: Template sample status.
 *                example: Template sample Status
 *    responses:
 *      '200':
 *        description: Successfully updated
 *        content:
 *          application/json:
 *            schema:
 *              $ref: '#/components/schemas/TemplatePython'
 *      '422':
 *        description: Validation errors.
 *      '500':
 *        description: Error during the execution.
 */
 """

# Initialize logger for the module
logger = logging.getLogger(__name__)
logger.setLevel(os.getenv('LOG_LEVEL', 'INFO'))  # Set log level based on environment variable

def edit(event, context):
    """
    Handles the update of a template in DynamoDB based on the provided ID.
    
    Parameters:
    - event: Contains request data, including headers, path parameters, and body.
    - context: Provides runtime information about the Lambda function execution.

    Returns:
    - A constructed HTTP response indicating success or failure of the update operation.
    """
    logger.debug('logging event: %s', event)  # Log the incoming event for debugging
    logger.info('Inside delete function')  # Log entry into the function

    # Initialize DynamoDB resource and specify the table to interact with
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(os.getenv('TABLE'))

    # Define HTTP status codes for various response scenarios
    STATUS_ERROR = 500
    STATUS_UNPROCESSABLE_ENTITY = 422
    STATUS_UPDATED = 200
    STATUS_NOT_FOUND = 404

    # Parse the request body and ensure boolean values are correctly formatted
    body = event['body']
    body = re.sub('true', 'true', body, flags=re.IGNORECASE)
    body = re.sub('false', 'false', body, flags=re.IGNORECASE)
    request_body = json.loads(body)  # Convert JSON string to Python dictionary

    # Extract HTTP method and path parameter ID from the event
    http_method = event['requestContext']['http']['method']
    id = event['pathParameters']['id']
    request_body['id'] = id  # Add ID to request body for validation

    # Validate the request body against the expected schema
    validation_schema = validate_request_body_schema(http_method, request_body)
    response_result = Responses.result_response(STATUS_ERROR, False, 'Error during the execution.')

    try:
        # If validation fails, return a 422 response with validation error details
        if not validation_schema['success']:
            response_result = Responses.result_response(STATUS_UNPROCESSABLE_ENTITY, False, 'Validation errors.', validation_schema)
            return construct_response(response_result)

        # Check authorization and retrieve the email of the user making the request
        email = check_authorization(event)
        validation_schema['data']['updatedBy'] = email  # Record who updated the template

        # Remove ID from request body and validation data to prevent overwriting
        if 'id' in request_body:
            del request_body['id']
        if 'id' in validation_schema['data']:
            del validation_schema['data']['id']

        # Generate the update query for DynamoDB using the validated data
        expression = generate_update_query(validation_schema['data'])

        # Check if the item with the given ID exists in DynamoDB
        existing_item = table.get_item(Key={'id': id})

        if 'Item' not in existing_item:
            # If item does not exist, return a 404 response
            response_result = Responses.result_response(STATUS_NOT_FOUND, False, f'Template with ID {id} not found.')
        else:
            # Update the existing item in DynamoDB with new data
            new_item = table.update_item(
                Key={'id': id},
                ExpressionAttributeNames=expression['ExpressionAttributeNames'],
                ExpressionAttributeValues=expression['ExpressionAttributeValues'],
                UpdateExpression=expression['UpdateExpression'],
                ReturnValues='ALL_NEW'
            )

            # Return a 200 response with the updated item attributes
            response_result = Responses.result_response(STATUS_UPDATED, True, f'Template with ID {id} updated successfully.', new_item['Attributes'])

    except Exception as err:
        # Handle any exceptions and return a 500 response with error details
        response_result = Responses.result_response(STATUS_ERROR, False, str(err))

    # Return the constructed response to the client
    return construct_response(response_result)

def generate_update_query(fields):
    """
    Constructs a DynamoDB update expression from the provided fields.
    
    Parameters:
    - fields: Dictionary containing field names and values to update.

    Returns:
    - A dictionary containing the update expression, attribute names, and attribute values for DynamoDB.
    """
    # Get the current date and time in RFC3339 format
    rfc3339_date = datetime.now().isoformat()

    # Initialize the update expression components
    new_item = {
        'UpdateExpression': 'set #updatedAt = :updatedAt,',  # Start with setting the updatedAt field
        'ExpressionAttributeNames': {'#updatedAt': 'updatedAt'},  # Map attribute names to placeholders
        'ExpressionAttributeValues': {':updatedAt': rfc3339_date},  # Map attribute values to placeholders
    }

    # Iterate over fields to build the update expression dynamically
    for key, item in fields.items():
        new_item['UpdateExpression'] += f" #{key} = :{key},"  # Append each field to the update expression
        new_item['ExpressionAttributeNames'][f"#{key}"] = key  # Add field name to attribute names
        new_item['ExpressionAttributeValues'][f":{key}"] = item  # Add field value to attribute values

    # Remove trailing comma from the update expression
    new_item['UpdateExpression'] = new_item['UpdateExpression'][:-1]

    return new_item  # Return the constructed update expression