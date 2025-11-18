# Import necessary modules and packages
import os
import json
import boto3
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

# Import workflow from POST handler to avoid duplication
from src.post.handler import BedrockKnowledgeBaseWorkflow

"""
/**
 * @asyncapi
 * channels:
 *   continue_chat:
 *     description: Channel for continuing an existing chat conversation.
 *     publish:
 *       operationId: continue_chat
 *       summary: Continue an existing chat conversation.
 *       message:
 *         messageId: continue_chat
 *         contentType: application/json
 *         payload:
 *           type: object
 *           required:
 *             - action
 *             - datas
 *           properties:
 *             action:
 *               type: string
 *               description: "The action to perform (continue for existing conversations)."
 *               example: continue
 *             datas:
 *               type: object
 *               required:
 *                 - conversationId
 *                 - query
 *                 - modelName
 *               properties:
 *                 conversationId:
 *                   type: string
 *                   description: The ID of the existing conversation to continue.
 *                   example: "550e8400-e29b-41d4-a716-446655440000"
 *                 query:
 *                   type: string
 *                   description: The user's follow-up query for the AI assistant.
 *                   example: "Can you provide more details about the leave approval process?"
 *                 modelName:
 *                   type: string
 *                   description: The model name to use for the AI assistant.
 *                   example: "AZURE_OPENAI_GPT_4O"
 *                 assistantId:
 *                   type: string
 *                   description: The ID of the chat assistant.
 *                   example: "184CF8DA-B821-4FF4-BD6C-CDAFA166E2E0"
 *                 vectorDb:
 *                   type: string
 *                   description: Optional vector database ID for knowledge base filtering.
 *                   example: "872051E8-E5C8-4AD1-83A8-ADB347D6C2CC"
 *     subscribe:
 *       operationId: continueChatResponse
 *       summary: Receive response for the continued chat conversation.
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

# State interface for LangGraph workflow
class State(Dict[str, Any]):
    """State object for LangGraph workflow"""
    messages: List[Any]
    user_query: str
    context_documents: List[str]
    conversation_id: str
    ai_response: str
    has_context: bool
    chat_history: List[Dict[str, Any]]

# Reusing BedrockKnowledgeBaseWorkflow from POST handler to eliminate duplicate code
    
    def retrieve_conversation_history(self, conversation_id: str) -> List[Dict[str, Any]]:
        """Retrieve existing conversation history from DynamoDB"""
        try:
            table_name = os.getenv('TABLE')
            if not table_name:
                logger.error("TABLE environment variable not set")
                return []
            
            dynamodb = boto3.resource('dynamodb')
            table = dynamodb.Table(table_name)
            
            # Query for existing conversation
            response = table.get_item(
                Key={'id': conversation_id}
            )
            
            if 'Item' in response:
                item = response['Item']
                chat_history = item.get('chatHistory', [])
                logger.info(f"Retrieved {len(chat_history)} messages from conversation {conversation_id}")
                return chat_history
            else:
                logger.warning(f"No existing conversation found with ID: {conversation_id}")
                return []
                
        except Exception as e:
            logger.error(f"Error retrieving conversation history: {e}")
            return []
    
    def process_continuation_query(self, user_query: str, conversation_id: str, vector_db: str = None) -> Dict[str, Any]:
        """
        Process a continuation query with conversation context
        """
        try:
            # Retrieve existing conversation history
            chat_history = self.retrieve_conversation_history(conversation_id)
            
            # For now, return a mock response since we can't use the full workflow
            # In production, this would use the full LangGraph workflow
            
            mock_response = f"Continuing conversation {conversation_id}. Your query: '{user_query}'. This is a continuation of our previous discussion."
            
            if chat_history:
                last_message = chat_history[-1] if chat_history else {}
                mock_response += f" Previously, we discussed: '{last_message.get('user', 'N/A')}'"
            
            return {
                "success": True,
                "ai_response": mock_response,
                "context_used": False,
                "sources_count": 0,
                "conversation_id": conversation_id,
                "model_used": AZURE_OPENAI_MODEL or "AZURE_OPENAI_GPT_4O",
                "timestamp": datetime.now().isoformat(),
                "chat_history": chat_history
            }
            
        except Exception as e:
            logger.error(f"Continuation workflow execution failed: {e}")
            return {
                "success": False,
                "error": "Failed to process continuation query",
                "ai_response": "I apologize, but I encountered an error processing your continuation request.",
                "context_used": False,
                "sources_count": 0,
                "conversation_id": conversation_id,
                "timestamp": datetime.now().isoformat(),
                "chat_history": []
            }

# Initialize global workflow instance (reuse from POST handler)
bedrock_workflow = BedrockKnowledgeBaseWorkflow()

@authenticate_websocket()
# @require_resource_permission('CHATKBBEDROCKCDKWEBSOCKET', 'UPDATE')
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

    # Extract necessary information from the event
    try:
        event_info = extract_event_info(event)
        url = event_info.get('url')
        connectionId = event_info.get('connectionId')
        
        if not connectionId:
            logger.error("No connection ID found in event")
            return {
                'statusCode': STATUS_ERROR,
                'body': json.dumps('Missing connection ID')
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
        conversation_id = validation_schema['datas'].get('conversationId')
        vector_db = validation_schema['datas'].get('vectorDb', KNOWLEDGE_BASE_ID)
        
        if not conversation_id:
            response_result = Responses.result_response(STATUS_UNPROCESSABLE_ENTITY, False, 'conversationId is required for continuing chat.')
            send_to_client(connectionId, json.dumps(construct_response(response_result)), url)
            return {
                'statusCode': STATUS_UNPROCESSABLE_ENTITY,
                'body': json.dumps('conversationId is required')
            }
        
        if user_query:
            logger.info(f"Processing chat continuation with LangGraph workflow: {user_query[:100]}...")
            logger.info(f"Conversation ID: {conversation_id}")
            logger.info(f"Using vector DB: {vector_db}")
            
            try:
                # Execute chat continuation workflow
                workflow_result = bedrock_workflow.process_chat_query(user_query, conversation_id, vector_db)
                
                if workflow_result.get('success', False):
                    # Retrieve existing conversation from DynamoDB
                    existing_conversation = table.get_item(Key={'id': conversation_id})
                    
                    if 'Item' not in existing_conversation:
                        logger.warning(f"Conversation {conversation_id} not found, creating new entry")
                        # Create new conversation entry using helper
                        chat_entry = conversation_builder.build_chat_history_entry(
                            user_query, workflow_result.get('ai_response', ''), conversation_id
                        )
                        new_conversation = {
                            'id': conversation_id,
                            'userId': email,
                            'conversationId': conversation_id,
                            'chatHistory': [chat_entry],
                            'createdBy': email,
                            'updatedBy': email,
                            'createdAt': datetime.now().isoformat(),
                            'updatedAt': datetime.now().isoformat()
                        }
                        
                        table.put_item(Item=new_conversation)
                        updated_chat_history = new_conversation['chatHistory']
                    else:
                        # Update existing conversation
                        existing_item = existing_conversation['Item']
                        existing_chat_history = existing_item.get('chatHistory', [])
                        
                        # Add new chat entry using helper
                        new_chat_entry = conversation_builder.build_chat_history_entry(
                            user_query, workflow_result.get('ai_response', ''), conversation_id
                        )
                        
                        updated_chat_history = existing_chat_history + [new_chat_entry]
                        
                        # Update the conversation in DynamoDB
                        table.update_item(
                            Key={'id': conversation_id},
                            UpdateExpression='SET chatHistory = :history, updatedBy = :updatedBy, updatedAt = :updatedAt',
                            ExpressionAttributeValues={
                                ':history': updated_chat_history,
                                ':updatedBy': email,
                                ':updatedAt': datetime.now().isoformat()
                            }
                        )
                    
                    logger.info("Chat continuation workflow completed successfully")
                    
                    # Send immediate AI response to client via WebSocket using helper
                    websocket_response = conversation_builder.build_websocket_response(
                        user_email=email,
                        conversation_id=conversation_id,
                        user_query=user_query,
                        ai_response=workflow_result.get('ai_response', ''),
                        sources_info=workflow_result.get('sources_info', []),
                        context_used=workflow_result.get('context_used', False),
                        sources_count=workflow_result.get('sources_count', 0),
                        chat_history=updated_chat_history
                    )
                    
                    final_response = conversation_builder.build_final_websocket_response(websocket_response, 200)
                    
                    send_to_client(connectionId, json.dumps(final_response), url)
                    
                    # Prepare success response for return
                    response_result = Responses.result_response(STATUS_UPDATED, True, 'Chat continued successfully.', websocket_response)
                    
                else:
                    # Workflow failed
                    logger.warning(f"Chat continuation workflow failed: {workflow_result.get('error', 'Unknown error')}")
                    response_result = Responses.result_response(STATUS_ERROR, False, 'AI processing temporarily unavailable')
                    
            except Exception as workflow_err:
                logger.error(f"Chat continuation workflow execution error: {workflow_err}")
                response_result = Responses.result_response(STATUS_ERROR, False, 'AI processing encountered an error')
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