# Import necessary modules for AWS DynamoDB interaction, logging, and error handling
import os
import boto3
import logging

from botocore.exceptions import ClientError
from src.helpers.api_responses import Responses
from src.helpers.construct_response import construct_response
from src.helpers.schema_validation import validate_request_body_schema

"""
/**
 * @openapi
 * /{id}:
 *  delete:
 *    summary: Delete a template by ID.
 *    description: This API endpoint deletes a template identified by its ID.
 *    parameters:
 *      - in: path
 *        name: id
 *        required: true
 *        schema:
 *          type: string
 *        description: The unique identifier of the template to be deleted.
 *        example: 184CF8DA-B821-4FF4-BD6C-CDAFA166E2E0
 *      - in: header
 *        name: Authorization
 *        description: Access token required for authentication.
 *        required: true
 *        schema:
 *          type: string
 *    responses:
 *      '200':
 *        description: Template successfully deleted.
 *        content:
 *          application/json:
 *            schema:
 *              $ref: '#/components/schemas/TemplatePython'
 *      '404':
 *        description: Template not found.
 */
 """

# Configure logger for the module
logger = logging.getLogger(__name__)
logger.setLevel(os.getenv('LOG_LEVEL', 'INFO'))  # Set log level based on environment variable

def delete(event, context):
    """
    Handles the deletion of a template from DynamoDB based on the provided ID.

    Parameters:
    - event: dict, contains request data including path parameters and HTTP method.
    - context: object, provides runtime information to the handler.

    Returns:
    - A structured HTTP response indicating the result of the delete operation.
    """
    logger.debug('logging event: %s', event)  # Log the incoming event for debugging
    logger.info('Inside delete function')  # Log entry into the delete function

    # Define HTTP status codes for various outcomes
    STATUS_ERROR = 500
    STATUS_UNPROCESSABLE_ENTITY = 422
    STATUS_NOT_FOUND = 404
    STATUS_DELETED = 200

    # Initialize DynamoDB resource and specify the table
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(os.getenv('TABLE'))  # Get table name from environment variable

    # Extract the template ID from the path parameters
    id = event['pathParameters']['id']
    params = {
        'id': id  # Key for DynamoDB operations
    }

    # Default error response setup
    response_result = Responses.result_response(STATUS_ERROR, False, 'Error during the execution.')

    # Retrieve the HTTP method from the event context
    http_method = event['requestContext']['http']['method']

    # Validate the request body schema based on the HTTP method and parameters
    validation_schema = validate_request_body_schema(http_method, params)

    try:
        # Check for validation errors and respond with a 422 status if any
        if not validation_schema['success']:
            response_result = Responses.result_response(STATUS_UNPROCESSABLE_ENTITY, False, 'Validation errors.', validation_schema)
            return construct_response(response_result)

        # Attempt to retrieve the item from DynamoDB using the provided ID
        try:
            existing_item = table.get_item(Key=params)
        except ClientError as e:
            # Log the error message if a ClientError occurs
            print(e.response['Error']['Message'])
        else:
            # Check if the item exists in the response
            if 'Item' not in existing_item:
                # Respond with a 404 status if the item is not found
                response_result = Responses.result_response(STATUS_NOT_FOUND, False, f'Template with ID {id} not found.')
            else:
                # Delete the item from DynamoDB if it exists
                table.delete_item(Key=params)
                # Respond with a 200 status indicating successful deletion
                response_result = Responses.result_response(STATUS_DELETED, True, f'Template with ID {id} successfully deleted.')
    except Exception as err:
        # Handle any unexpected exceptions and respond with a 500 status
        response_result = Responses.result_response(STATUS_ERROR, False, str(err))

    # Construct and return the final HTTP response
    return construct_response(response_result)