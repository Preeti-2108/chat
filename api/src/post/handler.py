# Import necessary modules for handling environment variables, regular expressions, JSON data, UUID generation, AWS services, logging, and date-time operations.
import os
import re
import json
import uuid
import boto3
import logging
from datetime import datetime

# Import helper functions for authorization checks, API response construction, and schema validation.
from src.helpers.check_authorization import check_authorization
from src.helpers.api_responses import Responses
from src.helpers.construct_response import construct_response
from src.helpers.schema_validation import validate_request_body_schema

"""
/**
 * @asyncapi
 * channels:
 *   newTemplateSample:
 *     description: Channel for posting and initiating new template sample.
 *     publish:
 *       operationId: newTemplateSample
 *       summary: Post and initiate a new template sample.
 *       message:
 *         messageId: newTemplateSample
 *         contentType: application/json
 *         payload:
 *           type: object
 *           required:
 *             - templateSampleCompany
 *             - templateSampleAgent
 *             - templateSampleActionsTag
 *             - templateSampleActionsTimeStamp
 *           properties:
 *             templateSampleCompany:
 *               type: string
 *               description: Template sample company name.
 *               example: Company Name
 *             templateSampleAgent:
 *               type: string
 *               description: Template sample agent name.
 *               example: Agent Name
 *             templateSampleRootCause:
 *               type: string
 *               description: Template sample root cause.
 *               example: Root Cause
 *             templateSampleAgentValidation:
 *               type: boolean
 *               description: Template sample agent validation.
 *               example: true
 *             templateSampleIntentFailed:
 *               type: boolean
 *               description: Template sample intent failed.
 *               example: false
 *             isActive:
 *               type: boolean
 *               description: Is active or not.
 *               example: true
 *             templateSampleActions:
 *               type: array
 *               items:
 *                 type: object
 *                 properties:
 *                   templateSampleActionsTimeStamp:
 *                     type: string
 *                     description: Timestamp of the action.
 *                     example: 1639172876
 *                   templateSampleActionsTag:
 *                     type: string
 *                     description: Tag of the action.
 *                     example: Tag Action
 *             templateSampleStatus:
 *               type: string
 *               description: Template sample status.
 *               example: Template sample Status
 *     subscribe:
 *       operationId: newTemplateSampleResponse
 *       summary: Receive response for the initiated template sample.
 *       message:
 *         $ref: '#/components/messages/NewTemplateSampleResponse'
 */
"""

# Initialize logger for the module with a log level set from environment variables, defaulting to 'INFO'.
logger = logging.getLogger(__name__)
logger.setLevel(os.getenv('LOG_LEVEL', 'INFO'))  # Set Log Level

def create(event, context):
    """
    Handles the creation of a new template based on the incoming event data.
    
    Args:
        event (dict): Contains request data and context information.
        context (object): Provides runtime information to the handler.
    
    Returns:
        dict: Constructed API response indicating success or failure of the operation.
    """
    logger.info('Received event: %s', event)  # Log the received event for debugging.
    logger.debug('logging event: %s', event)  # Log the incoming event for debugging purposes.
    logger.info('Inside create function!')  # Log entry into the create function.

    # Initialize DynamoDB resource and specify the table to interact with.
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(os.getenv('TABLE'))

    # Define HTTP status codes for error handling and successful creation.
    STATUS_ERROR = 500
    STATUS_UNPROCESSABLE_ENTITY = 422
    STATUS_CREATED = 201

    # Parse the request body from the event, ensuring boolean values are correctly formatted.
    body = event['body']
    body = re.sub('true', 'true', body, flags=re.IGNORECASE)
    body = re.sub('false', 'false', body, flags=re.IGNORECASE)
    request_body = json.loads(body)  # Convert JSON string to Python dictionary.
    http_method = event['requestContext']['http']['method']  # Extract HTTP method from the request context.

    # Validate the request body against the expected schema and capture any validation errors.
    validation_schema = validate_request_body_schema(http_method, request_body)
    response_result = Responses.result_response(STATUS_ERROR, False, 'Error during the execution.')  # Default error response.

    try:
        # If validation fails, return a 422 response with error details.
        if not validation_schema['success']:
            response_result = Responses.result_response(STATUS_UNPROCESSABLE_ENTITY, False, 'Validation errors.', validation_schema)
            return construct_response(response_result)

        # Check authorization and retrieve the email of the authorized user.
        email = check_authorization(event)

        # Add metadata to the validated data, including creator and timestamps.
        validation_schema['data']['createdBy'] = email
        validation_schema['data']['updatedBy'] = email
        validation_schema['data']['createdAt'] = datetime.now().isoformat()

        # Construct a new item for insertion into the database using the validated data.
        new_item = construct_new_item(validation_schema['data'])

        # Insert the new item into the specified DynamoDB table.
        table.put_item(Item=new_item)

        # Build a successful response indicating the template was created successfully.
        response_result = Responses.result_response(STATUS_CREATED, True, 'Template created successfully.', new_item)

    except Exception as err:
        # Handle any exceptions by constructing an error response with the exception details.
        response_result = Responses.result_response(STATUS_ERROR, False, str(err))

    # Return the constructed response, either success or error.
    return construct_response(response_result)

def construct_new_item(request_body):
    """
    Constructs a new item for database insertion based on the request body.
    
    Args:
        request_body (dict): Validated request data containing template details.
    
    Returns:
        dict: New item ready for insertion into the database.
    """
    request_body['id'] = str(uuid.uuid4())  # Generate a unique identifier for the new item.
    expression = generate_create_query(request_body)  # Prepare the item for database insertion.
    return expression

def generate_create_query(fields):
    """
    Generates a query expression for creating a new item in the database.
    
    Args:
        fields (dict): Key-value pairs representing the item attributes.
    
    Returns:
        dict: Expression containing the item attributes for database insertion.
    """
    exp = {}  # Initialize an empty dictionary to hold the item attributes.
    for key, item in fields.items():
        exp[key] = item  # Populate the dictionary with key-value pairs from the fields.
    return exp  # Return the constructed expression.
