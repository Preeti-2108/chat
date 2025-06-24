# Import necessary modules for environment variables, JSON handling, AWS SDK, logging, and string manipulation
import os
import re
import boto3
import logging
from text_unidecode import unidecode
from urllib.parse import parse_qs

# Import custom helper modules for API responses, response construction, and schema validation
from src.helpers.api_responses import Responses
from src.helpers.construct_response import construct_response
from src.helpers.schema_validation import validate_request_body_schema

"""
/**
 * @openapi
 * /:
 *  get:
 *    summary: Return a list of templates based on query parameters.
 *    parameters:
 *      - in: query
 *        name: templateCompany
 *        schema:
 *          type: string
 *        description: Filter templates by company name.
 *        example: Company Name
 *      - in: query
 *        name: templateAgent
 *        schema:
 *          type: string
 *        description: Filter templates by agent name.
 *        example: Agent Name
 *      - in: query
 *        name: templateRootCause
 *        schema:
 *          type: string
 *        description: Filter templates by root cause.
 *        example: Root Cause
 *      - in: query
 *        name: templateAgentValidation
 *        schema:
 *          type: boolean
 *        description: Filter templates by agent validation status.
 *        example: true
 *      - in: query
 *        name: templateIntentFailed
 *        schema:
 *          type: boolean
 *        description: Filter templates by intent failure status.
 *        example: false
 *      - in: query
 *        name: isActive
 *        schema:
 *          type: boolean
 *        description: Filter templates by active status.
 *        example: true
 *      - in: query
 *        name: templateStatus
 *        schema:
 *          type: string
 *        description: Filter templates by completion status.
 *        example: Template Status
 *      - in: query
 *        name: createdBy
 *        schema:
 *          type: string
 *        description: Filter templates by creator's name.
 *        example: Firstname Lastname
 *      - in: query
 *        name: updatedBy
 *        schema:
 *          type: string
 *        description: Filter templates by modifier's name.
 *        example: Firstname Lastname
 *      - in: query
 *        name: createdAt
 *        schema:
 *          type: string
 *          format: date-time
 *        description: Filter templates by creation date.
 *        example: 2023-10-16T13:25:10.666Z
 *      - in: query
 *        name: updatedAt
 *        schema:
 *          type: string
 *          format: date-time
 *        description: Filter templates by modification date.
 *        example: 2023-10-16T13:28:40.028Z
 *      - in: query
 *        name: createdStart
 *        schema:
 *          type: string
 *          format: date-time
 *        description: Filter templates by start creation date.
 *        example: 2023-10-16T13:25:10.666Z
 *      - in: query
 *        name: createdEnd
 *        schema:
 *          type: string
 *          format: date-time
 *        description: Filter templates by end creation date.
 *        example: 2023-10-16T13:28:40.028Z
 *      - in: query
 *        name: updatedStart
 *        schema:
 *          type: string
 *          format: date-time
 *        description: Filter templates by start update date.
 *        example: 2023-10-16T13:25:10.666Z
 *      - in: query
 *        name: updatedEnd
 *        schema:
 *          type: string
 *          format: date-time
 *        description: Filter templates by end update date.
 *        example: 2023-10-16T13:28:40.028Z
 *      - in: query
 *        name: offset
 *        schema:
 *          type: integer
 *        description: Number of initial results to skip.
 *        example: 0
 *      - in: query
 *        name: limit
 *        schema:
 *          type: integer
 *        description: Maximum number of results to return.
 *        example: 5
 *      - in: header
 *        name: Authorization
 *        description: Access token required for authentication.
 *        required: true
 *        schema:
 *          type: string
 *    responses:
 *      '200':
 *        description: Successful retrieval of templates.
 *        content:
 *          application/json:
 *            schema:
 *              $ref: '#/components/schemas/TemplatePython'
 *      '404':
 *        description: No templates found matching the criteria.
 */
 """

# Initialize logger for the module
logger = logging.getLogger(__name__)
logger.setLevel(os.getenv('LOG_LEVEL', 'INFO'))  # Set log level based on environment variable

def list(event, context):
    """
    Handles the retrieval of templates based on query parameters from an HTTP GET request.

    Args:
        event (dict): Contains request data, including query parameters and HTTP method.
        context (object): Provides runtime information to the handler.

    Returns:
        dict: Constructed response containing status code, success flag, message, and data.
    """
    logger.debug('logging event: %s', event)  # Log the incoming event for debugging
    logger.info('Inside list function')  # Log entry into the function

    # Define HTTP status codes for response
    STATUS_ERROR = 500
    STATUS_UNPROCESSABLE_ENTITY = 422
    STATUS_OK = 200

    # Initialize DynamoDB resource and table
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(os.getenv('TABLE'))

    # Parse query parameters from the event and convert numeric values
    query_parameters = {k: int(v[0]) if v[0].isdigit() else v[0] for k, v in parse_qs(event['rawQueryString']).items()}
    http_method = event['requestContext']['http']['method']  # Extract HTTP method from the event

    # Validate the request body schema based on HTTP method and query parameters
    validation_schema = validate_request_body_schema(http_method, query_parameters)

    # Default response for error during execution
    response_result = Responses.result_response(STATUS_ERROR, False, 'Error during the execution.')

    try:
        # If validation fails, return a 422 response with validation errors
        if not validation_schema['success']:
            response_result = Responses.result_response(STATUS_UNPROCESSABLE_ENTITY, False, 'Validation errors.', validation_schema)
            return construct_response(response_result)

        # Construct parameters for DynamoDB scan operation based on query filters
        params = construct_params(query_parameters)
        templates = table.scan(**params)  # Execute scan operation on DynamoDB table
        items = format_results(templates, query_parameters)  # Format the results based on offset and limit

        # Determine response based on the number of items retrieved
        if items['count'] > 0:
            response_result = Responses.result_response(STATUS_OK, True, 'Templates retrieved successfully.', items)
        else:
            response_result = Responses.result_response(STATUS_OK, True, 'No templates found with these filters.', items)
    except Exception as err:
        # Handle exceptions and return a 500 response with error details
        response_result = Responses.result_response(STATUS_ERROR, False, str(err))

    return construct_response(response_result)  # Return the constructed response

def construct_params(query_parameters):
    """
    Constructs parameters for DynamoDB scan operation based on query filters.

    Args:
        query_parameters (dict): Dictionary of query parameters from the request.

    Returns:
        dict: Parameters for DynamoDB scan operation including filter expressions and attribute values.
    """
    # Extract individual query parameters for filtering
    template_company = query_parameters.get('templateCompany')
    template_agent = query_parameters.get('templateAgent')
    template_root_cause = query_parameters.get('templateRootCause')
    template_agent_validation = query_parameters.get('templateAgentValidation')
    template_intent_failed = query_parameters.get('templateIntentFailed')
    template_status = query_parameters.get('templateStatus')
    created_by = query_parameters.get('createdBy')
    updated_by = query_parameters.get('updatedBy')
    created_at = query_parameters.get('createdAt')
    updated_at = query_parameters.get('updatedAt')
    created_start = query_parameters.get('createdStart')
    created_end = query_parameters.get('createdEnd')
    updated_start = query_parameters.get('updatedStart')
    updated_end = query_parameters.get('updatedEnd')

    # Initialize parameters for DynamoDB scan operation
    params = {
        'TableName': os.getenv('TABLE'),
        'ExpressionAttributeValues': {},
        'ExpressionAttributeNames': {},
        'FilterExpression': '',
    }

    # Define filters with corresponding attribute names and types
    filters = [
        {'name': 'templateCompany', 'type': 'string', 'value': template_company, 'attribute': '#templateCompany'},
        {'name': 'templateAgent', 'type': 'string', 'value': template_agent, 'attribute': '#templateAgent'},
        {'name': 'templateRootCause', 'type': 'string', 'value': template_root_cause, 'attribute': '#templateRootCause'},
        {'name': 'templateAgentValidation', 'type': 'boolean', 'value': template_agent_validation, 'attribute': '#templateAgentValidation'},
        {'name': 'templateIntentFailed', 'type': 'boolean', 'value': template_intent_failed, 'attribute': '#templateIntentFailed'},
        {'name': 'templateStatus', 'type': 'string', 'value': template_status, 'attribute': '#templateStatus'},
        {'name': 'createdBy', 'type': 'string', 'value': created_by, 'attribute': '#createdBy'},
        {'name': 'updatedBy', 'type': 'string', 'value': updated_by, 'attribute': '#updatedBy'},
        {'name': 'createdAt', 'type': 'date', 'value': created_at, 'attribute': '#createdAt'},
        {'name': 'updatedAt', 'type': 'date', 'value': updated_at, 'attribute': '#updatedAt'},
        {'name': 'createdStart', 'type': 'compare-date', 'value': created_start, 'attribute': '#createdStart', 'operator': '>=', 'comparateDate': 'createdAt'},
        {'name': 'createdEnd', 'type': 'compare-date', 'value': created_end, 'attribute': '#createdEnd', 'operator': '<=', 'comparateDate': 'createdAt'},
        {'name': 'updatedStart', 'type': 'compare-date', 'value': updated_start, 'attribute': '#updatedStart', 'operator': '>=', 'comparateDate': 'updatedAt'},
        {'name': 'updatedEnd', 'type': 'compare-date', 'value': updated_end, 'attribute': '#updatedEnd', 'operator': '<=', 'comparateDate': 'updatedAt'},
    ]

    # Construct filter expression, attribute values, and attribute names for each filter
    for filter in filters:
        if filter['value'] is not None:
            if filter['type'] == 'boolean':
                # Convert boolean string to actual boolean value
                val = filter['value']
                val = re.sub('true', 'true', val, flags=re.IGNORECASE)
                val = re.sub('false', 'false', val, flags=re.IGNORECASE)
                val = True if filter['value'].lower() == 'true' else False
                params['ExpressionAttributeValues'][f":{filter['name']}"] = val
                params['ExpressionAttributeNames'][filter['attribute']] = filter['name']
                params['FilterExpression'] += f" AND {filter['attribute']} = :{filter['name']}" if params['FilterExpression'] else f"{filter['attribute']} = :{filter['name']}"
            elif filter['type'] == 'compare-date':
                # Handle date comparison filters
                params['ExpressionAttributeValues'][f":{filter['name']}"] = filter['value'].upper()
                params['ExpressionAttributeNames'][f"#{filter['comparateDate']}"] = filter['comparateDate']
                params['FilterExpression'] += f" AND #{filter['comparateDate']} {filter['operator']} :{filter['name']}" if params['FilterExpression'] else f"#{filter['comparateDate']} {filter['operator']} :{filter['name']}"
            elif filter['type'] == 'string':
                # Handle string filters with accent removal
                params['ExpressionAttributeValues'][f":{filter['name']}"] = remove_accents(filter['value'].upper())
                params['ExpressionAttributeNames'][filter['attribute']] = filter['name']
                params['FilterExpression'] += f" AND {filter['attribute']} = :{filter['name']}" if params['FilterExpression'] else f"{filter['attribute']} = :{filter['name']}"
            elif filter['type'] == 'integer':
                # Handle integer filters
                params['ExpressionAttributeValues'][f":{filter['name']}"] = int(filter['value'])
                params['ExpressionAttributeNames'][filter['attribute']] = filter['name']
                params['FilterExpression'] += f" AND {filter['attribute']} = :{filter['name']}" if params['FilterExpression'] else f"{filter['attribute']} = :{filter['name']}"
            else:
                # Default handling for other types
                params['ExpressionAttributeValues'][f":{filter['name']}"] = filter['value']
                params['ExpressionAttributeNames'][filter['attribute']] = filter['name']
                params['FilterExpression'] += f" AND {filter['attribute']} = :{filter['name']}" if params['FilterExpression'] else f"{filter['attribute']} = :{filter['name']}"

    # Remove unnecessary attributes if no filter expression is constructed
    if not params['FilterExpression']:
        del params['ExpressionAttributeValues']
        del params['ExpressionAttributeNames']
        del params['FilterExpression']

    return params  # Return constructed parameters for DynamoDB scan

def format_results(items, query_parameters):
    """
    Formats the results from DynamoDB scan operation based on offset and limit.

    Args:
        items (dict): Results from DynamoDB scan operation.
        query_parameters (dict): Dictionary of query parameters including offset and limit.

    Returns:
        dict: Formatted results including items and count.
    """
    items = items['Items'].copy()  # Copy items from scan results
    offset = int(query_parameters.get('offset', 0))  # Get offset from query parameters
    limit = int(query_parameters.get('limit', len(items)))  # Get limit from query parameters

    # Apply offset and limit to the items list
    if offset:
        items = items[offset:]
    if limit:
        items = items[:limit]

    return {
        'items': items,  # List of items after applying offset and limit
        'count': len(items),  # Count of items in the final list
    }

def remove_accents(input_str):
    """
    Removes accents from a given string using unidecode.

    Args:
        input_str (str): String from which accents need to be removed.

    Returns:
        str: String with accents removed.
    """
    return unidecode(input_str)  # Use unidecode to remove accents from the input string