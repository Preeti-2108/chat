# Import necessary modules and packages
import os
import json
import boto3
import boto3.dynamodb.conditions
import logging
import uuid
from datetime import datetime
from typing import Dict, Any, List

# LangGraph and LangChain imports for workflow orchestration
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langchain_core.messages import HumanMessage, AIMessage
from langchain_openai import AzureChatOpenAI
from botocore.config import Config

from src.helpers.api_responses import Responses
from src.helpers.construct_response import construct_response
from src.helpers.schema_validation import validate_request_datas_schema_pydantic
from src.handler_websocket.handler import send_to_client
from src.helpers.event_utils import extract_event_info  # Custom helper to extract necessary information from the event
from src.helpers.decimal_converter import convert_decimal_to_json_serializable as decimal_to_json_serializable  # Custom helper to convert Decimal objects
from src.helpers.auth_middleware import authenticate_websocket, get_user_email, get_authenticated_user  # Cognito authentication
from src.helpers.scope_manager import require_resource_permission  # Scope validation
from src.helpers.queue_helper import send_message_to_queue  # SQS queue helper

# New organized helpers to reduce redundancy
from src.helpers.streaming_handler import WordLevelStreamingHandler, send_immediate_streaming_signals
from src.helpers.conversation_builder import conversation_builder, extract_user_email_from_event
from src.helpers.document_analyzer import document_analyzer, build_context_aware_prompt
from src.helpers.system_instructions import get_default_system_instructions, get_error_response_templates

# Import shared workflow instance from POST handler for memory continuity
from src.post.handler import bedrock_workflow

from src.helpers.langfuse_helpers import (
            create_update_trace,
            update_trace_input,
            update_trace_output,
            update_trace_error,
            flush_trace,
        )

"""
/**
 * @asyncapi
 * channels:
 *   chatUpdate:
 *     description: Channel for updating a chat conversation by ID.
 *     publish:
 *       operationId: chatUpdate
 *       summary: Update a chat conversation by ID.
 *       message:
 *         messageId: chatUpdate
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
 *                 - query
 *               properties:
 *                 id:
 *                   type: string
 *                   description: The ID of the chat conversation to update.
 *                   example: "123e4567-e89b-12d3-a456-426614174000"
 *                 query:
 *                   type: string
 *                   description: The user's query for the AI assistant.
 *                   example: "Make a descriptive of previous conversation"
 *     subscribe:
 *       operationId: chatUpdateResponse
 *       summary: Receive response for the updated chat.
 *       message:
 *         $ref: '#/components/messages/chatUpdateResponse'
 */
"""

# Configure logger
logger = logging.getLogger(__name__)
logger.setLevel(os.getenv('LOG_LEVEL', 'INFO'))  # Set Log Level

# Configuration
KNOWLEDGE_BASE_ID = os.getenv('KNOWLEDGE_BASE_ID')
AWS_REGION = os.getenv('REGION')  # Use REGION from CDK environment
AZURE_OPENAI_MODEL = os.getenv('AZURE_OPENAI_MODEL')
BASE_URL = os.getenv('BASE_URL')  # Base URL for Azure OpenAI
AZURE_OPENAI_API_ENDPOINT = os.getenv('AZURE_OPENAI_API_ENDPOINT')
AZURE_OPENAI_API_VERSION = os.getenv('AZURE_OPENAI_API_VERSION')
AZURE_OPENAI_API_KEY = os.getenv('AZURE_OPENAI_API_KEY')
AZURE_OPENAI_TEMPERATURE = float(os.getenv('AZURE_OPENAI_TEMPERATURE', '0.7'))
AZURE_OPENAI_MAX_TOKENS = int(os.getenv('AZURE_OPENAI_MAX_TOKENS', '4000'))

logger.info(f"AWS Region: {AWS_REGION}")
logger.info(f"Knowledge Base ID: {KNOWLEDGE_BASE_ID}")
logger.info(f"Azure OpenAI Model: {AZURE_OPENAI_MODEL}")
logger.info(f"Base URL for Azure OpenAI: {BASE_URL}")
logger.info(f"Azure OpenAI Endpoint configured: {AZURE_OPENAI_API_ENDPOINT}")
logger.info(f"Azure OpenAI Temperature: {AZURE_OPENAI_TEMPERATURE}")
logger.info(f"Azure OpenAI Max Tokens: {AZURE_OPENAI_MAX_TOKENS}")

# No local state or workflow classes needed - using shared workflow from POST handler
# The bedrock_workflow imported above contains:
# - BedrockKnowledgeBaseWorkflow class with MemorySaver
# - Memory methods: get_memory_checkpoints(), get_conversation_context()
# - All workflow nodes and LangGraph logic
# This ensures conversation continuity between POST and PUT operations

# Use shared workflow instance from POST handler for memory continuity
# bedrock_workflow is imported from src.post.handler above
logger.info(f"🧠 [PUT INIT] Using shared workflow instance with memory from POST handler")

@authenticate_websocket()
@require_resource_permission('CHATKBBEDROCKCDKWEBSOCKET', 'UPDATE')
def continue_chat(event, context):
    """
    Main function to handle the continuation of an existing chat conversation.
    
    This function processes incoming events to continue a chat conversation,
    retrieves conversation history, generates AI responses, and updates 
    the conversation in DynamoDB. It also handles errors and sends responses 
    back to the client via WebSocket.
    
    :param event: The event data received from the client.
    :param context: The context in which the function is executed.
    :return: A dictionary containing the status code and body message.
    """
    logger.debug('logging event: %s', event)
    logger.info('Inside continue chat function')

    # Define status codes
    STATUS_ERROR = 500
    STATUS_UNPROCESSABLE_ENTITY = 422
    STATUS_UPDATED = 200
    
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

    logger.info(f"Event received: {event}")

    # Extract necessary information from the event
    try:
        # Extract WebSocket connection info from requestContext
        event_info = extract_event_info(event)
        url = event_info.get('url')
        connectionId = event_info.get('connectionId')

        # Extract conversation ID from request body
        body = json.loads(event.get('body', '{}'))
        conversation_id_from_body = body.get('datas', {}).get('id')
        
        logger.info("URL length: %s", len(url) if url else 0)
        logger.info("WebSocket Connection ID: %s", connectionId)
        logger.info("Conversation ID from body: %s", conversation_id_from_body)
        
        if not connectionId:
            logger.error("No connection ID found in event")
            return {
                'statusCode': STATUS_ERROR,
                'body': json.dumps('Missing connection ID')
            }
            
        if not conversation_id_from_body:
            logger.error("No conversation ID found in request body")
            return {
                'statusCode': STATUS_ERROR,
                'body': json.dumps('Missing conversation ID in request body')
            }
    except Exception as event_err:
        logger.error(f"Error extracting event info: {str(event_err)}")
        return {
            'statusCode': STATUS_ERROR,
            'body': json.dumps('Error processing event')
        }

    try:
        # Parse the body of the event
        try:
            body = json.loads(event.get('body', '{}'))
        except json.JSONDecodeError as json_err:
            logger.error(f"Error parsing JSON body: {str(json_err)}")
            response_result = Responses.result_response(STATUS_UNPROCESSABLE_ENTITY, False, 'Invalid JSON format in request body.')
            send_to_client(connectionId, json.dumps(construct_response(response_result)), url)
            return {
                'statusCode': STATUS_UNPROCESSABLE_ENTITY,
                'body': json.dumps('Invalid JSON format')
            }
        
        action = body.get('action')
        datas = body.get('datas')
        
        # DEBUG: Log PUT handler usage for conversation continuation
        logger.info(f"🔄 [PUT HANDLER] Processing conversation continuation - action: '{action}'")
        logger.info(f"🔄 [PUT HANDLER] Request datas keys: {list(datas.keys()) if datas else 'None'}")
        if datas and datas.get('id'):
            logger.info(f"🔄 [PUT HANDLER] Continuing conversation_id: {datas.get('id')}")

        # Validate the request data schema using pydantic (similar to POST)
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
            logger.debug('Validation failed: %s', validation_schema)
            send_to_client(connectionId, json.dumps(construct_response(response_result)), url)
            return {
                'statusCode': STATUS_UNPROCESSABLE_ENTITY,
                'body': json.dumps('Validation failed')
            }

        # Get authenticated user info from the JWT token (added by auth middleware)
        user_info = event.get('auth', {}).get('user_info', {})
        email = user_info.get('email') or user_info.get('username', 'unknown@example.com')
        user_id = user_info.get('user_id', 'unknown')
        
        logger.info(f"Continuing chat for authenticated user: {email} (ID: {user_id})")
        
        # Extract chat continuation parameters
        user_query = validation_schema['datas'].get('query', '')
        conversation_id = validation_schema['datas'].get('id')  # This should match conversation_id_from_body
        vector_db = validation_schema['datas'].get('vectorDb', KNOWLEDGE_BASE_ID)
        
        # Debug: Log the exact values being extracted
        logger.info(f"DEBUG: From validation_schema - conversation_id: '{conversation_id}' (type: {type(conversation_id)})")
        logger.info(f"DEBUG: From body directly - conversation_id_from_body: '{conversation_id_from_body}' (type: {type(conversation_id_from_body)})")
        logger.info(f"DEBUG: Extracted user_query: '{user_query}'")
        logger.info(f"DEBUG: Full validation_schema['datas']: {validation_schema['datas']}")
        
        # Use the conversation_id from validation (should be the same as conversation_id_from_body)
        if not conversation_id:
            logger.error(f"No conversation ID found in validation_schema. Raw body conversation ID: {conversation_id_from_body}")
            response_result = Responses.result_response(STATUS_UNPROCESSABLE_ENTITY, False, 'Conversation ID is required for continuing chat.')
            send_to_client(connectionId, json.dumps(construct_response(response_result)), url)
            return {
                'statusCode': STATUS_UNPROCESSABLE_ENTITY,
                'body': json.dumps('Conversation ID is required')
            }
        
        # Ensure both IDs match for consistency
        if conversation_id != conversation_id_from_body:
            logger.warning(f"ID mismatch: validation_schema ID '{conversation_id}' != body ID '{conversation_id_from_body}'")
            # Use the one from validation_schema as it's been validated
            logger.info(f"Using conversation_id from validation_schema: '{conversation_id}'")
        
        if user_query:
            logger.info(f"Processing chat continuation with LangGraph workflow: {user_query[:100]}...")
            logger.info(f"Conversation ID: {conversation_id}")
            logger.info(f"Using vector DB: {vector_db}")

            try:
                # FIRST: Check if conversation exists before calling workflow
                # Retrieve existing conversation from DynamoDB using conversationId field
                existing_conversation = None
                try:
                    conversation_id_str = str(conversation_id)
                    response = table.get_item(Key={'conversationId': conversation_id_str})
                    if 'Item' in response:
                        existing_conversation = response['Item']
                except Exception as scan_err:
                    logger.error(f"Error scanning for conversation: {scan_err}")
                    existing_conversation = None

                if not existing_conversation:
                    logger.error(f"Conversation {conversation_id} not found. PUT operation requires existing conversation.")
                    response_result = Responses.result_response(STATUS_ERROR, False, f'Conversation {conversation_id} not found. Use POST to create a new conversation.')
                    send_to_client(connectionId, json.dumps(construct_response(response_result)), url)
                    return {
                        'statusCode': STATUS_ERROR,
                        'body': json.dumps('Conversation not found')
                    }

                # --- Langfuse Trace Creation ---
                trace = create_update_trace(session_id=str(uuid.uuid4()), conversation_id=conversation_id)
                update_trace_input(trace, query=user_query, user_id=email)

                # Conversation exists, now execute the AI workflow
                websocket_connection = {
                    "connectionId": connectionId,
                    "url": url
                }
                workflow_result = bedrock_workflow.process_chat_query(user_query, conversation_id, vector_db, websocket_connection)

                if workflow_result.get('success', False):
                    # Update existing conversation with AI response
                    existing_chat_history = existing_conversation.get('chatHistory', [])
                    new_chat_entry = conversation_builder.create_conversation_data(
                        user_query, workflow_result.get('ai_response', ''), conversation_id
                    )
                    updated_chat_history = existing_chat_history + [new_chat_entry]
                    table.update_item(
                        Key={'conversationId': conversation_id_str},
                        UpdateExpression='SET chatHistory = :history, memoryHistory = :memoryHistory, updatedBy = :updatedBy, updatedAt = :updatedAt',
                        ExpressionAttributeValues={
                            ':history': updated_chat_history,
                            ':memoryHistory': updated_chat_history,
                            ':updatedBy': email,
                            ':updatedAt': datetime.now().isoformat()
                        }
                    )
                    logger.info("Chat continuation workflow completed successfully")
                    websocket_response = conversation_builder.build_websocket_response(
                        user_email=email,
                        conversation_id=conversation_id,
                        user_query=user_query,
                        ai_response=workflow_result.get('ai_response', ''),
                        sources_info=workflow_result.get('sources_info', []),
                        context_used=workflow_result.get('context_used', False),
                        sources_count=workflow_result.get('sources_count', 0)
                    )
                    websocket_response['chatHistory'] = updated_chat_history
                    final_response = conversation_builder.build_final_websocket_response(websocket_response, 200)
                    send_to_client(connectionId, json.dumps(final_response), url)
                    response_result = Responses.result_response(STATUS_UPDATED, True, 'Chat continued successfully.', websocket_response)
                    # Remove unnecessary fields before updating trace output
                    wf_result_clean = dict(workflow_result)
                    for k in [
                        "context_used", "sources_count", "sources_info", "model_used",
                        "processing_method", "cost_optimized", "memory_enabled", "thread_id", "streaming_used"
                    ]:
                        wf_result_clean.pop(k, None)
                    update_trace_output(trace, response_data=wf_result_clean, status="success")
                    flush_trace(trace)
                else:
                    logger.warning(f"Chat continuation workflow failed: {workflow_result.get('error', 'Unknown error')}")
                    response_result = Responses.result_response(STATUS_ERROR, False, 'AI processing temporarily unavailable')
                    update_trace_error(trace, error_type="WorkflowError", error_message=workflow_result.get('error', 'Unknown error'))
                    flush_trace(trace)
            except Exception as workflow_err:
                logger.error(f"Chat continuation workflow execution error: {workflow_err}")
                response_result = Responses.result_response(STATUS_ERROR, False, 'AI processing encountered an error')
                update_trace_error(trace, error_type=type(workflow_err).__name__, error_message=str(workflow_err))
                flush_trace(trace)
        else:
            logger.warning("No query provided for AI processing")
            response_result = Responses.result_response(STATUS_UNPROCESSABLE_ENTITY, False, 'Query is required for chat continuation.')

    except Exception as err:
        # Handle general errors
        logger.error(f"Error occurred: {str(err)}, Event: {json.dumps(event)}")
        response_result = Responses.result_response(STATUS_ERROR, False, 'Error during the execution.')

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

# Helper functions for chat continuation API

def construct_chat_continuation_item(datas, email):
    """
    Construct a new chat continuation item with updated data.
    
    :param datas: The data to be included in the continuation item.
    :param email: The user's email for tracking purposes.
    :return: A dictionary representing the continuation item.
    """
    datas['updatedBy'] = email
    datas['updatedAt'] = datetime.now().isoformat()
    return datas

def validate_continuation_request(datas):
    """
    Validate that the continuation request has required fields.
    
    :param datas: The request data to validate.
    :return: Tuple of (is_valid, error_message).
    """
    required_fields = ['conversationId', 'query']
    
    for field in required_fields:
        if not datas.get(field):
            return False, f"Missing required field: {field}"
    
    return True, None