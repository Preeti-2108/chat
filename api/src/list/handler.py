import os  # Provides a way of using operating system dependent functionality
import json  # Provides methods to work with JSON data
import boto3  # AWS SDK for Python to interact with AWS services
import logging  # Provides a way to configure and use loggers
import re  # Provides regular expression matching operations
from text_unidecode import unidecode  # Provides a way to remove accents from characters
from urllib.parse import parse_qs  # Provides methods to parse query strings
from src.helpers.api_responses import Responses  # Custom helper for API responses
from src.helpers.construct_response import construct_response  # Custom helper to construct responses
from src.helpers.schema_validation import validate_request_datas_schema  # Custom helper to validate request data schema
from src.handler_websocket.handler import send_to_client  # Custom helper to send data to a client via WebSocket
from src.helpers.event_utils import extract_event_info  # Custom helper to extract necessary information from the event

"""
/**
 * @asyncapi
 * channels:
 *   templateList:
 *     description: Channel for retrieving a list of templates.
 *     publish:
 *       operationId: templateList
 *       summary: Return a list of templates.
 *       message:
 *         messageId: templateList
 *         contentType: application/json
 *         payload:
 *           type: array
 *           items:
 *             type: object
 *             properties:
 *               templateCompany:
 *                 type: string
 *                 description: Template company name.
 *                 example: Company Name
 *               templateAgent:
 *                 type: string
 *                 description: Template agent name.
 *                 example: Agent Name
 *               templateRootCause:
 *                 type: string
 *                 description: Template root cause.
 *                 example: Root Cause
 *               templateAgentValidation:
 *                 type: boolean
 *                 description: Template agent validation.
 *                 example: true
 *               isActive:
 *                 type: boolean
 *                 description: Is active or not.
 *                 example: true
 *               templateIntentFailed:
 *                 type: boolean
 *                 description: Template intent failed.
 *                 example: false
 *               templateStatus:
 *                 type: string
 *                 description: Template status.
 *                 example: Template Status
 *               createdBy:
 *                 type: string
 *                 description: Template creator.
 *                 example: Firstname Lastname
 *               updatedBy:
 *                 type: string
 *                 description: Template modifier.
 *                 example: Firstname Lastname
 *               createdAt:
 *                 type: string
 *                 format: date-time
 *                 description: Template creation date.
 *                 example: 2023-10-16T13:25:10.666Z
 *               updatedAt:
 *                 type: string
 *                 format: date-time
 *                 description: Template modification date.
 *                 example: 2023-10-16T13:28:40.028Z
 *     subscribe:
 *       operationId: templateListResponse
 *       summary: Retrieve templates based on query parameters.
 *       message:
 *         $ref: '#/components/messages/TemplateListResponse'
 */
"""

# Configure logger
logger = logging.getLogger(__name__)
logger.setLevel(os.getenv('LOG_LEVEL', 'INFO'))  # Set Log Level

def list(event, context):
    """
    Main function to handle the listing of items.
    
    This function processes incoming events to retrieve a list of templates from a DynamoDB table.
    It validates the request, constructs query parameters, and formats the response to be sent back to the client.
    
    :param event: The event data received from the client, containing query parameters and action.
    :param context: The context in which the function is executed, providing runtime information.
    :return: A dictionary containing the HTTP status code and a message indicating the result of the operation.
    """
    logger.debug('logging event: %s', event)  # Log the incoming event
    logger.info('Inside list function')  # Log entry into the function

    # Define status codes for different outcomes
    STATUS_ERROR = 500
    STATUS_UNPROCESSABLE_ENTITY = 422
    STATUS_OK = 200

    # Initialize DynamoDB resource and table
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(os.getenv('TABLE'))

    # Extract necessary information from the event
    event_info = extract_event_info(event)
    url = event_info.get('url')
    connectionId = event_info.get('connectionId')

    try:
        # Parse the body of the event
        body = json.loads(event.get('body', '{}'))
        action = body.get('action')
        datas = body.get('datas', {})

        # Check if action parameter is provided (mandatory)
        if not action:
            response_result = Responses.result_response(STATUS_UNPROCESSABLE_ENTITY, False, 'Action parameter is required.')
            send_to_client(connectionId, json.dumps(construct_response(response_result)), url)
            return {
                'statusCode': STATUS_UNPROCESSABLE_ENTITY,
                'body': json.dumps('Action parameter is required.')
            }

        # Convert query string format to dictionary if datas is a string
        if isinstance(datas, str):
            datas = {k: int(v[0]) if v[0].isdigit() else v[0] for k, v in parse_qs(datas).items()}
        elif not isinstance(datas, dict):
            datas = {}

    except json.JSONDecodeError:
        # Handle JSON parsing errors
        response_result = Responses.result_response(STATUS_UNPROCESSABLE_ENTITY, False, 'Invalid JSON format.')
        send_to_client(connectionId, json.dumps(construct_response(response_result)), url)
        return {
            'statusCode': STATUS_UNPROCESSABLE_ENTITY,
            'body': json.dumps('Invalid JSON format.')
        }

    # Validate the request and retrieve validation errors
    validation_schema = validate_request_datas_schema(action, datas)

    # Default response in case of an error
    response_result = Responses.result_response(STATUS_ERROR, False, 'Error during the execution.')

    try:
        # In case of validation errors, return a 422 response with error details
        if not validation_schema['success']:
            response_result = Responses.result_response(STATUS_UNPROCESSABLE_ENTITY, False, 'Validation errors.', validation_schema)
            send_to_client(connectionId, json.dumps(construct_response(response_result)), url)
            return {
                'statusCode': STATUS_UNPROCESSABLE_ENTITY,
                'body': json.dumps('Validation errors.')
            }

        # Construct parameters for DynamoDB scan
        params = construct_params(datas)
        templates = table.scan(**params)  # Execute the scan operation
        items = format_results(templates, datas)  # Format the results based on offset and limit
        
        # Check if items were found and construct the appropriate response
        if items['count'] > 0:
            response_result = Responses.result_response(STATUS_OK, True, 'Templates retrieved successfully.', items)
        else:
            response_result = Responses.result_response(STATUS_OK, True, 'No templates found with these filters.', items)
    except Exception as err:
        # Handle any exceptions that occur during processing
        response_result = Responses.result_response(STATUS_ERROR, False, str(err))

    # Send the response to the client
    send_to_client(connectionId, json.dumps(construct_response(response_result)), url)

    return {
        'statusCode': 200,
        'body': json.dumps('Message sent successfully.')
    }

def construct_params(datas):
    """
    Construct parameters for DynamoDB scan based on provided query parameters.
    
    This function builds the filter expression and attribute mappings required for querying the DynamoDB table.
    
    :param datas: A dictionary containing query parameters extracted from the event.
    :return: A dictionary containing the constructed parameters for the DynamoDB scan operation.
    """
    # Extract the relevant filters from the provided query parameters
    template_company = datas.get('templateCompany')
    template_agent = datas.get('templateAgent')
    template_root_cause = datas.get('templateRootCause')
    template_agent_validation = datas.get('templateAgentValidation')
    template_intent_failed = datas.get('templateIntentFailed')
    template_status = datas.get('templateStatus')
    created_by = datas.get('createdBy')
    updated_by = datas.get('updatedBy')
    created_at = datas.get('createdAt')
    updated_at = datas.get('updatedAt')
    created_start = datas.get('createdStart')
    created_end = datas.get('createdEnd')
    updated_start = datas.get('updatedStart')
    updated_end = datas.get('updatedEnd')

    # Initialize parameters for the scan operation
    params = {
        'TableName': os.getenv('TABLE'),
        'ExpressionAttributeValues': {},
        'ExpressionAttributeNames': {},
        'FilterExpression': '',
    }

    # Define the filters with their corresponding DynamoDB attribute names
    filters = [
        {'name': 'templateCompany', 'type': 'string_contains', 'value': template_company, 'attribute': '#templateCompany'},
        {'name': 'templateAgent', 'type': 'string_contains', 'value': template_agent, 'attribute': '#templateAgent'},
        {'name': 'templateRootCause', 'type': 'string_contains', 'value': template_root_cause, 'attribute': '#templateRootCause'},
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

    # Iterate over each filter to construct the filter expression, attribute values, and attribute names
    for filter in filters:
        if filter['value'] is not None:
            if filter['type'] == 'boolean':
                # Convert string boolean values to actual boolean types
                val = filter['value']
                val = re.sub('true', 'true', val, flags=re.IGNORECASE)
                val = re.sub('false', 'false', val, flags=re.IGNORECASE)
                val = True if filter['value'].lower() == 'true' else False
                params['ExpressionAttributeValues'][f":{filter['name']}"] = val
                params['ExpressionAttributeNames'][filter['attribute']] = filter['name']
                params['FilterExpression'] += f" AND {filter['attribute']} = :{filter['name']}" if params['FilterExpression'] else f"{filter['attribute']} = :{filter['name']}"
            elif filter['type'] == 'compare-date':
                # Handle date comparisons
                params['ExpressionAttributeValues'][f":{filter['name']}"] = filter['value'].upper()
                params['ExpressionAttributeNames'][f"#{filter['comparateDate']}"] = filter['comparateDate']
                params['FilterExpression'] += f" AND #{filter['comparateDate']} {filter['operator']} :{filter['name']}" if params['FilterExpression'] else f"#{filter['comparateDate']} {filter['operator']} :{filter['name']}"
            elif filter['type'] == 'string':
                # Handle string comparisons, removing accents
                params['ExpressionAttributeValues'][f":{filter['name']}"] = remove_accents(filter['value'].upper())
                params['ExpressionAttributeNames'][filter['attribute']] = filter['name']
                params['FilterExpression'] += f" AND {filter['attribute']} = :{filter['name']}" if params['FilterExpression'] else f"{filter['attribute']} = :{filter['name']}"
            elif filter['type'] == 'string_contains':
                # Handle string comparisons with partial matching, removing accents
                params['ExpressionAttributeValues'][f":{filter['name']}"] = remove_accents(filter['value'].upper())
                params['ExpressionAttributeNames'][filter['attribute']] = filter['name']
                params['FilterExpression'] += f" AND contains({filter['attribute']}, :{filter['name']})" if params['FilterExpression'] else f"contains({filter['attribute']}, :{filter['name']})"
            elif filter['type'] == 'integer':
                # Handle integer comparisons
                params['ExpressionAttributeValues'][f":{filter['name']}"] = int(filter['value'])
                params['ExpressionAttributeNames'][filter['attribute']] = filter['name']
                params['FilterExpression'] += f" AND {filter['attribute']} = :{filter['name']}" if params['FilterExpression'] else f"{filter['attribute']} = :{filter['name']}"
            else:
                # Default case for other types
                params['ExpressionAttributeValues'][f":{filter['name']}"] = filter['value']
                params['ExpressionAttributeNames'][filter['attribute']] = filter['name']
                params['FilterExpression'] += f" AND {filter['attribute']} = :{filter['name']}" if params['FilterExpression'] else f"{filter['attribute']} = :{filter['name']}"

    # If there's no filter expression, remove the related attributes from the parameters
    if not params['FilterExpression']:
        del params['ExpressionAttributeValues']
        del params['ExpressionAttributeNames']
        del params['FilterExpression']

    return params

def format_results(items, datas):
    """
    Format the results from DynamoDB scan based on offset and limit.
    
    This function slices the list of items based on the provided offset and limit to control pagination.
    
    :param items: The raw items retrieved from the DynamoDB scan.
    :param datas: A dictionary containing query parameters, including offset and limit.
    :return: A dictionary containing the formatted list of items and their count.
    """
    items = items['Items'].copy()  # Copy the list of items to avoid modifying the original
    offset = int(datas.get('offset', 0))  # Get the offset value, defaulting to 0
    limit = int(datas.get('limit', len(items)))  # Get the limit value, defaulting to the length of items

    if offset:
        items = items[offset:]  # Apply offset to the list of items
    if limit:
        items = items[:limit]  # Apply limit to the list of items

    return {
        'items': items,
        'count': len(items),  # Return the count of items after applying offset and limit
    }

def remove_accents(input_str):
    """
    Remove accents from the input string.
    
    This function uses the unidecode library to convert accented characters to their unaccented counterparts.
    
    :param input_str: The string from which to remove accents.
    :return: The unaccented version of the input string.
    """
    return unidecode(input_str)