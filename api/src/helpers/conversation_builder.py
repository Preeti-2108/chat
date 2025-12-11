"""
Conversation Data Builder Helper
Handles construction of conversation data structures and DynamoDB items.
Reduces redundancy in data structure creation.
"""

import uuid
import logging
from datetime import datetime
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

class ConversationDataBuilder:
    """Builder class for creating standardized conversation data structures."""
    
    def create_conversation_data(self, user_query: str, ai_response: str, conversation_id: str) -> Dict[str, Any]:
        """
        Create a standardized conversation data entry.
        
        Args:
            user_query: The user's question/input
            ai_response: The AI assistant's response  
            conversation_id: The conversation/trace ID
            
        Returns:
            Dict containing user, aiAssistant, and traceId
        """
        return {
            "user": user_query,
            "aiAssistant": ai_response,
            "traceId": conversation_id
        }
    
    def build_validation_schema_data(self, 
                                   user_query: str,
                                   ai_response: str, 
                                   conversation_id: str,
                                   user_email: str,
                                   assistant_id: str = None,
                                   model_used: str = 'AZURE_OPENAI_GPT_4O',
                                   context_used: bool = False,
                                   sources_count: int = 0,
                                   sources_info: List = None,
                                   llm=None
                                   ) -> Dict[str, Any]:
        """
        Build the validation_schema['datas'] structure used throughout the application.
        
        This standardizes the data structure creation that appears in multiple scenarios:
        - Success case
        - Failure case  
        - Error case
        - No query case
        """
        if sources_info is None:
            sources_info = []
            
        # Create conversation data entry
        conversation_data = self.create_conversation_data(user_query, ai_response, conversation_id)
        
            # Generate title from query using LLM if provided
        title = self._generate_title_from_query(user_query, llm=llm)
        
        # Build the complete data structure
        logger.info(f"Building conversation data for conversation ID: {conversation_id}")
        data_structure = {
            "conversationId": str(conversation_id),
            "assistantId": assistant_id or '',
            "title": title,
            "createdBy": user_email,
            "updatedBy": user_email,
            "languageCode": "en",
            "createdAt": datetime.now().isoformat(),
            "updatedAt": datetime.now().isoformat(),
            "isActive": True,
            "iaModel": model_used,
            "chatHistory": [conversation_data],
            "memoryHistory": [conversation_data],
            
            # Metadata for compatibility
            # "contextUsed": context_used,
            # "sourcesCount": sources_count,
            # "sourcesInfo": sources_info
        }
        
        return data_structure
    
    def build_success_case_data(self, workflow_result: Dict[str, Any], user_query: str, user_email: str, assistant_id: str = None, llm=None) -> Dict[str, Any]:
        """Build data structure for successful workflow execution."""
        return self.build_validation_schema_data(
            user_query=user_query,
            ai_response=workflow_result.get('ai_response', ''),
            conversation_id=workflow_result.get('conversation_id', str(uuid.uuid4())),
            user_email=user_email,
            assistant_id=assistant_id,
            model_used=workflow_result.get('model_used', 'AZURE_OPENAI_GPT_4O'),
            context_used=workflow_result.get('context_used', False),
            sources_count=workflow_result.get('sources_count', 0),
            sources_info=workflow_result.get('sources_info', []),
            llm=llm
        )
    
    def build_failure_case_data(self, user_query: str, conversation_id: str, user_email: str) -> Dict[str, Any]:
        """Build data structure for workflow failure case."""
        return self.build_validation_schema_data(
            user_query=user_query,
            ai_response='AI processing temporarily unavailable',
            conversation_id=conversation_id,
            user_email=user_email,
            model_used='AZURE_OPENAI_GPT_4O',
            context_used=False,
            sources_count=0,
            sources_info=[]
        )
    
    def build_error_case_data(self, user_query: str, conversation_id: str, user_email: str) -> Dict[str, Any]:
        """Build data structure for workflow error case."""
        return self.build_validation_schema_data(
            user_query=user_query,
            ai_response='AI processing encountered an error',
            conversation_id=conversation_id,
            user_email=user_email,
            model_used='AZURE_OPENAI_GPT_4O',
            context_used=False,
            sources_count=0,
            sources_info=[]
        )
    
    def build_no_query_case_data(self, conversation_id: str, user_email: str) -> Dict[str, Any]:
        """Build data structure for no query provided case."""
        return self.build_validation_schema_data(
            user_query="",
            ai_response="No query provided",
            conversation_id=conversation_id,
            user_email=user_email,
            model_used='AZURE_OPENAI_GPT_4O',
            context_used=False,
            sources_count=0,
            sources_info=[]
        )
    
    def build_websocket_response(self, 
                                user_email: str, 
                                conversation_id: str,
                                user_query: str,
                                ai_response: str,
                                sources_info: List = None,
                                context_used: bool = False,
                                sources_count: int = 0) -> Dict[str, Any]:
        """
        Build the WebSocket response format sent to clients.
        
        This creates the 'new_format_response' structure used in WebSocket communications.
        """
        if sources_info is None:
            sources_info = []
            
        # Create chat history entry
        chat_history_entry = self.create_conversation_data(user_query, ai_response, conversation_id)
        
        return {
            "userId": user_email,
            "conversationId": conversation_id,
            "chatHistory": [chat_history_entry],
            "trace_id": conversation_id,
            "sources": sources_info,
            "contextUsed": context_used,
            "sourcesCount": sources_count
        }
    
    def build_final_websocket_response(self, websocket_response_data: Dict[str, Any], status_code: int = 201) -> Dict[str, Any]:
        """Build the final WebSocket response with data and status."""
        return {
            "data": websocket_response_data,
            "status": status_code
        }
    
    def _generate_title_from_query(self, user_query: str, llm=None) -> str:
        """Generate a title from the user query, using LLM if provided."""
        if not user_query:
            return "Empty Chat"
        if llm:
            logger.debug("Using LLM for title generation")
            try:
                response = llm.invoke([
                    {"role": "user", "content": f"Generate a concise chat title for: {user_query}"}
                ])
                title = response.content if hasattr(response, 'content') else str(response)
                if title:
                    # Strip leading/trailing quotes and whitespace
                    title = title.strip().strip('"').strip("'")
                if not title:
                    title = f"Chat - {user_query[:50]}..." if len(user_query) > 50 else f"Chat - {user_query}"
                return title
            except Exception as e:
                # LLM title generation failed, using fallback
                return f"Chat - {user_query[:50]}..." if len(user_query) > 50 else f"Chat - {user_query}"
        logger.debug("Using query-based title generation (no LLM provided)")
        if len(user_query) > 50:
            return f"{user_query[:50]}..."
        else:
            return f"{user_query}"

    def construct_new_dynamodb_item(self, datas: Dict[str, Any]) -> Dict[str, Any]:
        """
        Construct a new DynamoDB item with the proper structure.
        
        Args:
            datas: The conversation data dictionary
            
        Returns:
            Complete DynamoDB item ready for insertion
        """
        # Create the item structure using conversationId as primary key
        # No separate 'id' field needed - conversationId serves as the primary key
        logger.info(f"Constructing DynamoDB item for conversation: {datas.get('conversationId', 'unknown')}")
        item = {
            "conversationId": str(datas.get('conversationId', '')),
            "assistantId": datas.get('assistantId', ''),
            "title": datas.get('title', ''),
            "createdBy": datas.get('createdBy', ''),
            "updatedBy": datas.get('updatedBy', ''),
            "languageCode": datas.get('languageCode', 'en'),
            "createdAt": datas.get('createdAt', ''),
            "updatedAt": datas.get('updatedAt', ''),
            "isActive": datas.get('isActive', True),
            "iaModel": datas.get('iaModel', ''),
            "chatHistory": datas.get('chatHistory', []),
            "memoryHistory": datas.get('memoryHistory', []),
        }
        
        # Add any additional fields that might be present (like sources, etc.)
        for key, value in datas.items():
            if key not in item:  # Don't override the structured fields above
                item[key] = value
        
        return item


# Global instance for easy import and use
conversation_builder = ConversationDataBuilder()


def extract_user_email_from_event(event: Dict[str, Any]) -> str:
    """
    Extract user email from event with multiple fallback methods.
    
    This consolidates the redundant user email extraction logic
    that appears multiple times in the original code.
    """
    
    try:
        # Method 1: From authentication middleware
        auth_info = event.get('auth', {})
        if auth_info and auth_info.get('is_authenticated'):
            user_info = auth_info.get('user_info', {})
            user_email = user_info.get('email', '')
            if user_email:
                logger.debug("Email extracted from auth middleware")
                return user_email
        
        # Method 2: From requestContext (for REST APIs)
        user_email = event.get('requestContext', {}).get('authorizer', {}).get('email', '')
        if user_email:
            logger.debug("Email extracted from requestContext")
            return user_email
        
        # Method 3: Extract from JWT token directly as fallback
        try:
            from src.helpers.cognito_auth import extract_token_from_event, extract_user_info
            token = extract_token_from_event(event)
            if token:
                user_info = extract_user_info(token)
                user_email = user_info.get('email', '')
                if user_email:
                    logger.debug("Email extracted from JWT token")
                    return user_email
        except ImportError:
            logger.warning("Cognito auth helpers not available for JWT extraction")
            
    except Exception as e:
        pass
    
    # Final fallback
    if not user_email or user_email == '':
        logger.warning("Could not extract user email, using fallback")
    
    return user_email