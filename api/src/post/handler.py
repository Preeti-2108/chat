import os  # Provides a way of using operating system dependent functionality
import json  # Provides methods to work with JSON data
import uuid  # Provides immutable UUID objects (universally unique identifiers)
import boto3  # AWS SDK for Python to interact with AWS services
import logging  # Provides a way to configure and use loggers
from datetime import datetime  # Provides classes for manipulating dates and times
from src.helpers.check_authorization import check_authorization  # Custom helper to check authorization
from src.helpers.api_responses import Responses  # Custom helper for API responses
from src.helpers.construct_response import construct_response  # Custom helper to construct responses
from src.helpers.schema_validation import validate_request_datas_schema  # Custom helper to validate request data schema
from src.handler_websocket.handler import send_to_client  # Custom helper to send data to a client via WebSocket
from src.helpers.event_utils import extract_event_info  # Custom helper to extract necessary information from the event

"""
/**
 * @asyncapi
 * channels:
 *   newTemplate:
 *     description: Channel for posting and initiating new template.
 *     publish:
 *       operationId: newTemplate
 *       summary: Post and initiate a new template.
 *       message:
 *         messageId: newTemplate
 *         contentType: application/json
 *         payload:
 *           type: object
 *           required:
 *             - templateCompany
 *             - templateAgent
 *             - templateActionsTag
 *             - templateActionsTimeStamp
 *           properties:
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
 *             templateIntentFailed:
 *               type: boolean
 *               description: Template intent failed.
 *               example: false
 *             isActive:
 *               type: boolean
 *               description: Is active or not.
 *               example: true
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
 *       operationId: newTemplateResponse
 *       summary: Receive response for the initiated template.
 *       message:
 *         $ref: '#/components/messages/NewTemplateResponse'
 */
"""

# Configure logger
logger = logging.getLogger(__name__)
logger.setLevel(os.getenv('LOG_LEVEL', 'INFO'))  # Set Log Level

def create(event, context):
    """
    Main function to handle the creation of a new item.
    
    This function processes incoming events to create a new item in a DynamoDB table.
    It validates the request data, checks authorization, constructs the item, and
    inserts it into the database. It also handles errors and sends responses back to
    the client via WebSocket.
    
    :param event: The event data received from the client.
    :param context: The context in which the function is executed.
    :return: A dictionary containing the status code and body message.
    """
    logger.debug('logging event: %s', event)  # Log the incoming event
    logger.info('Inside create function')  # Log entry into the function
    
    # Initialize DynamoDB resource and table
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(os.getenv('TABLE'))

    # Extract necessary information from the event
    event_info = extract_event_info(event)
    url = event_info.get('url')
    connectionId = event_info.get('connectionId')

    # Define status codes
    STATUS_ERROR = 500
    STATUS_UNPROCESSABLE_ENTITY = 422
    STATUS_CREATED = 201

    try:
        # Parse the body of the event
        body = json.loads(event.get('body', '{}'))
        action = body.get('action')
        datas = body.get('datas')

        print('action:', action)
        print('datas:', datas)
        print('toto')

        # Validate the request data schema
        validation_schema = validate_request_datas_schema(action, datas)

        if not validation_schema['success']:
            # If validation fails, send a response to the client and return
            response_result = Responses.result_response(STATUS_UNPROCESSABLE_ENTITY, False, 'Validation errors.', validation_schema)
            logger.debug('Validation failed: %s', validation_schema)
            send_to_client(connectionId, json.dumps(construct_response(response_result)), url)
            return {
                'statusCode': STATUS_UNPROCESSABLE_ENTITY,
                'body': json.dumps('Validation failed')
            }

        # Check authorization and add metadata to the data
        email = check_authorization(body)
        validation_schema['datas']['createdBy'] = email
        validation_schema['datas']['updatedBy'] = email
        validation_schema['datas']['createdAt'] = datetime.now().isoformat()
        validation_schema['datas']['updatedAt'] = datetime.now().isoformat()

        # Construct the new item to be inserted
        new_item = construct_new_item(validation_schema['datas'])
        logger.debug('New item to be inserted: %s', new_item)

        try:
            # Insert the new item into the DynamoDB table
            table.put_item(Item=new_item)
            logger.info('Item successfully inserted into DynamoDB')
            response_result = Responses.result_response(STATUS_CREATED, True, 'Item created successfully.', new_item)
        except Exception as dynamo_err:
            # Handle DynamoDB insertion errors
            logger.error(f"Error inserting item into DynamoDB: {str(dynamo_err)}")
            response_result = Responses.result_response(STATUS_ERROR, False, 'Failed to insert item into DynamoDB.')

    except Exception as err:
        # Handle general errors
        logger.error(f"Error occurred: {str(err)}, Event: {json.dumps(event)}")
        response_result = Responses.result_response(STATUS_ERROR, False, 'Error during the execution.')

    # Send the response to the client
    send_to_client(connectionId, json.dumps(construct_response(response_result)), url)

    return {
        'statusCode': 200,
        'body': json.dumps('Message processed')
    }

def construct_new_item(datas):
    """
    Construct a new item with a unique ID and the provided data.
    
    This function generates a unique identifier for the new item and prepares
    the data for insertion into the database.
    
    :param datas: The data to be included in the new item.
    :return: A dictionary representing the new item.
    """
    datas['id'] = str(uuid.uuid4())  # Generate a unique ID for the new item
    expression = generate_create_query(datas)  # Generate the item expression
    return expression

def generate_create_query(fields):
    """
    Generate a query expression for creating a new item.
    
    This function constructs a dictionary expression from the provided fields,
    which is used to insert the item into the database.
    
    :param fields: The fields to be included in the query expression.
    :return: A dictionary representing the query expression.
    """
    exp = {}
    for key, item in fields.items():
        exp[key] = item  # Add each field to the expression
    return exp