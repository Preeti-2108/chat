import os  # Provides a way of using operating system dependent functionality
import json  # Provides methods to work with JSON data
import uuid  # Provides immutable UUID objects (universally unique identifiers)
import boto3  # AWS SDK for Python to interact with AWS services
import logging  # Provides a way to configure and use loggers
import time  # For timing operations
import asyncio  # For async operations
from datetime import datetime  # Provides classes for manipulating dates and times
from typing import Dict, Any, List

# LangGraph and LangChain imports for workflow orchestration
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langchain_core.messages import HumanMessage, AIMessage
from langchain_openai import AzureChatOpenAI
from botocore.config import Config

from src.helpers.api_responses import Responses  # Custom helper for API responses
from src.helpers.construct_response import construct_response  # Custom helper to construct responses
from src.helpers.schema_validation import validate_request_datas_schema_pydantic  # Custom helper to validate request data schema
from src.handler_websocket.handler import send_to_client  # Custom helper to send data to a client via WebSocket
from src.helpers.event_utils import extract_event_info  # Custom helper to extract necessary information from the event
from src.helpers.auth_middleware import authenticate_websocket  # Cognito authentication
from src.helpers.scope_manager import require_resource_permission  # Scope validation
from src.helpers.queue_helper import send_message_to_queue  # Helper function to send messages to an SQS queue

"""
/**
 * @asyncapi
 * channels:
 *   create:
 *     description: Channel for posting and creating a new chat conversation.
 *     publish:
 *       operationId: create
 *       summary: Post and initiate a new chat.
 *       message:
 *         messageId: create
 *         contentType: application/json
 *         payload:
 *           type: object
 *           required:
 *             - action
 *             - datas
 *           properties:
 *             action:
 *               type: string
 *               description: "The action to perform (create for new conversations)."
 *               example: create
 *             datas:
 *               type: object
 *               required:
 *                 - query
 *                 - modelName
 *                 - assistantId
 *               properties:
 *                 query:
 *                   type: string
 *                   description: The user's query for the AI assistant.
 *                   example: "What is the process to apply for leave?"
 *                 modelName:
 *                   type: string
 *                   description: The model name to use for the AI assistant.
 *                   example: "AZURE_OPENAI_GPT_4O"
 *                 assistantId:
 *                   type: string
 *                   description: The ID of the chat assistant.
 *                   example: "184CF8DA-B821-4FF4-BD6C-CDAFA166E2E0"
 *     subscribe:
 *       operationId: createResponse
 *       summary: Receive response for the initiated chat  .
 *       message:
 *         $ref: '#/components/messages/CreateResponse'
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
AZURE_OPENAI_TEMPERATURE = float(os.getenv('AZURE_OPENAI_TEMPERATURE'))
AZURE_OPENAI_MAX_TOKENS = int(os.getenv('AZURE_OPENAI_MAX_TOKENS'))
ENABLE_WEBSOCKET_STREAMING = os.getenv('ENABLE_WEBSOCKET_STREAMING', 'true').lower() == 'true'

logger.info(f"AWS Region: {AWS_REGION}")
logger.info(f"Knowledge Base ID: {KNOWLEDGE_BASE_ID}")
logger.info(f"Azure OpenAI Model: {AZURE_OPENAI_MODEL}")
logger.info(f"Base URL for Azure OpenAI: {BASE_URL}")
logger.info(f"Azure OpenAI Endpoint configured: {AZURE_OPENAI_API_ENDPOINT}")
logger.info(f"Azure OpenAI API Key configured: {AZURE_OPENAI_API_KEY}")
logger.info(f"Azure OpenAI Temperature: {AZURE_OPENAI_TEMPERATURE}")
logger.info(f"Azure OpenAI Max Tokens: {AZURE_OPENAI_MAX_TOKENS}")

# State interface for LangGraph workflow
class State(Dict[str, Any]):
    """State object for LangGraph workflow with enhanced memory"""
    messages: List[Any]  # LangGraph manages this automatically with add_messages
    user_query: str
    context_documents: List[str]
    conversation_id: str
    ai_response: str
    has_context: bool
    websocket_connection: Dict[str, Any]
    vector_db: str
    # Enhanced memory fields
    conversation_summary: str  # For long conversations
    memory_mode: str  # 'full', 'summary', or 'sliding_window'
    max_memory_turns: int  # How many turns to remember

class WordLevelStreamingHandler:
    """
    Specialized handler for per-word streaming to UI.
    Optimized for smooth, natural word-by-word delivery.
    """
    
    def __init__(self, connection_id: str, websocket_url: str, conversation_id: str = None, trace_id: str = None):
        self.connection_id = connection_id
        self.websocket_url = websocket_url
        self.conversation_id = conversation_id
        self.trace_id = trace_id
        self.full_response = ""
        self.chunk_count = 0
        self.last_send_time = datetime.now().timestamp()
        self.sent_chunks = set()  # Track sent chunks to avoid duplicates
        self.start_signal_sent = False  # Track if start signal was already sent
        
        # Ultra-optimized timing configuration
        self.min_interval = 0.001  # Ultra-fast: 1ms minimum
        self.max_interval = 0.005  # Ultra-fast: 5ms maximum
        self.enable_word_breaking = True
        
    def send_streaming_chunk(self, chunk: str, is_final: bool = False):
        """
        Send a streaming chunk to the WebSocket client.
        """
        try:
            # Build the streaming response payload
            streaming_payload = {
                "type": "streaming_response",
                "chunk": chunk,
                "chunk_index": self.chunk_count,
                "is_final": is_final,
                "full_response": self.full_response,  # Always include accumulated response
                "partial_response": self.full_response,  # Current accumulated text
                "streaming_mode": "word_level",
                "response_length": len(self.full_response)  # Length for debugging
            }
            
            # Send the chunk to the client
            send_to_client(
                self.connection_id, 
                json.dumps(streaming_payload), 
                self.websocket_url
            )
            
            self.chunk_count += 1
            logger.debug(f"Sent word chunk {self.chunk_count}: '{chunk}' to {self.connection_id}")
            logger.debug(f"Full response so far ({len(self.full_response)} chars): '{self.full_response[:100]}...'")
            
        except Exception as e:
            logger.error(f"Error sending word chunk: {str(e)}")
    
    def send_start_signal(self):
        """Send a signal indicating that word-level streaming has started."""
        if self.start_signal_sent:
            logger.debug("Start signal already sent, skipping duplicate")
            return
            
        try:
            start_payload = {
                "type": "streaming_start",
                "message": "AI is generating response word by word...",
                "streaming_mode": "word_level"
            }
            
            if self.conversation_id:
                start_payload["conversation_id"] = self.conversation_id
                start_payload["id"] = self.conversation_id
            
            if self.trace_id:
                start_payload["trace_id"] = self.trace_id
            
            send_to_client(
                self.connection_id, 
                json.dumps(start_payload), 
                self.websocket_url
            )
            self.start_signal_sent = True
            logger.info(f"Sent word-level streaming start signal to {self.connection_id}")
        except Exception as e:
            logger.error(f"Error sending streaming start signal: {str(e)}")
    
    def send_error_signal(self, error_message: str):
        """Send an error signal to the client."""
        try:
            error_payload = {
                "type": "streaming_error",
                "error": error_message,
                "streaming_mode": "word_level"
            }
            send_to_client(
                self.connection_id, 
                json.dumps(error_payload), 
                self.websocket_url
            )
            logger.error(f"Sent streaming error signal to {self.connection_id}: {error_message}")
        except Exception as e:
            logger.error(f"Error sending streaming error signal: {str(e)}")
    
    def send_text(self, text: str):
        """Send text content as a streaming chunk."""
        try:
            self.full_response += text
            self.send_streaming_chunk(text)
            logger.info(f"Sent additional text content to {self.connection_id}: {text[:50]}...")
        except Exception as e:
            logger.error(f"Error sending text content: {str(e)}")
    
    def process_word_streaming(self, llm_response_generator):
        """
        Process the streaming response from the LLM and send individual words to the client.
        """
        try:
            generator = llm_response_generator

            # Handle non-iterable responses
            if generator is not None and not hasattr(generator, '__iter__') and hasattr(generator, 'response_gen'):
                try:
                    generator = generator.response_gen
                except Exception:
                    generator = None

            # Handle non-streaming responses
            if generator is None or not hasattr(generator, '__iter__'):
                final_text = self._extract_clean_text(getattr(llm_response_generator, 'response', llm_response_generator))
                if final_text:
                    self._send_immediate_chunk(final_text)
                    self.full_response += final_text
                    self.send_streaming_chunk("", is_final=True)
                    return self.full_response

            # Process each chunk from the LLM with optimized timing
            chunk_count = 0
            for chunk in generator:
                chunk_text = self._extract_clean_text(chunk)
                if chunk_text:
                    # Add to full response before processing
                    self.full_response += chunk_text
                    chunk_count += 1
                    
                    # Send first chunk immediately for faster perceived response
                    if chunk_count == 1:
                        self._send_immediate_chunk(chunk_text)
                    else:
                        # Process for word-level streaming with optimized timing
                        self._process_word_chunks_optimized(chunk_text)
            
            # Send final chunk
            self.send_streaming_chunk("", is_final=True)
            
            logger.info(f"Completed word-level streaming for {self.connection_id} with {chunk_count} chunks")
            return self.full_response
            
        except Exception as e:
            error_msg = f"Error in word-level streaming: {str(e)}"
            logger.error(error_msg)
            self.send_error_signal(error_msg)
            raise
    
    def _send_immediate_chunk(self, text: str):
        """Send the first chunk immediately for faster perceived response."""
        try:
            self.send_streaming_chunk(text)
            self.last_send_time = datetime.now().timestamp()
            logger.debug(f"Sent immediate chunk: '{text}' to {self.connection_id}")
        except Exception as e:
            logger.error(f"Error sending immediate chunk: {str(e)}")
    
    def _process_word_chunks_optimized(self, text: str):
        """Process text and send individual words with optimized timing."""
        words = self._break_into_words(text) if self.enable_word_breaking else text.split()
        
        for word in words:
            if word.strip():
                self._send_word_with_optimized_timing(word)
    
    def _send_word_with_optimized_timing(self, word: str):
        """Send a word with optimized timing for faster response."""
        current_time = datetime.now().timestamp()
        time_since_last = current_time - self.last_send_time
        
        # Ultra-fast streaming - minimal delay for natural feel
        optimized_min_interval = max(0.0005, self.min_interval * 0.05)  # 95% faster
        
        if time_since_last < optimized_min_interval:
            time.sleep(optimized_min_interval - time_since_last)
        
        word_hash = hash(word)
        
        if word_hash not in self.sent_chunks:
            self.send_streaming_chunk(word + " ")  # Add space for natural separation
            self.sent_chunks.add(word_hash)
            self.last_send_time = datetime.now().timestamp()
            logger.debug(f"Sent optimized word: '{word}'")
    
    def _break_into_words(self, text: str) -> List[str]:
        """Advanced word breaking for better streaming."""
        import re
        words = re.findall(r'\S+|\s+', text)
        return [word for word in words if word.strip()]
    
    def _extract_clean_text(self, chunk) -> str:
        """Enhanced text extraction with better LangChain response handling."""
        try:
            if hasattr(chunk, 'content'):
                content = chunk.content
                if isinstance(content, str):
                    return content
                elif isinstance(content, dict):
                    if 'response' in content:
                        return str(content['response'])
                    elif 'text' in content:
                        return str(content['text'])
                    else:
                        return str(content)
                else:
                    return str(content)
            elif isinstance(chunk, dict):
                if 'response' in chunk:
                    response_content = chunk['response']
                    if isinstance(response_content, str):
                        return response_content
                    elif isinstance(response_content, dict) and 'content' in response_content:
                        return str(response_content['content'])
                    else:
                        return str(response_content)
                elif 'content' in chunk:
                    return str(chunk['content'])
                elif 'text' in chunk:
                    return str(chunk['text'])
                elif 'message' in chunk:
                    return str(chunk['message'])
                else:
                    for key, value in chunk.items():
                        if isinstance(value, str) and value.strip() and key not in ['input', 'history']:
                            return value
                    return ""
            elif isinstance(chunk, str):
                return chunk
            else:
                return str(chunk)
        except Exception as e:
            logger.warning(f"Error extracting text from chunk: {str(e)}")
            return ""

class BedrockKnowledgeBaseWorkflow:
    """
    LangGraph workflow that orchestrates Bedrock Knowledge Base retrieval and chat generation
    Based on AWS samples: aws-samples/langgraph-bedrock-knowledge-bases
    """
    
    def __init__(self):
        self.bedrock_agent_client = self._setup_bedrock_agent()
        self.chat_model = self._setup_chat_model()
        self.workflow = self._create_workflow()
    
    def _setup_bedrock_agent(self):
        """Setup AWS Bedrock Agent Runtime client for Knowledge Base queries"""
        try:
            config = Config(
                region_name=AWS_REGION,
                retries={'max_attempts': 3, 'mode': 'standard'}
            )
            logger.info(f"Setting up Bedrock agent client in region: {AWS_REGION}")
            return boto3.client('bedrock-agent-runtime', config=config)
        except Exception as e:
            logger.error(f"Failed to setup Bedrock agent client: {e}")
            return None
    
    def _setup_chat_model(self):
        """Setup Azure OpenAI chat model using LangChain"""
        try:
            # Validate required Azure OpenAI configuration
            if not AZURE_OPENAI_API_KEY:
                logger.error("❌ AZURE_OPENAI_API_KEY not set, chat model will not be available")
                return None
            
            if not AZURE_OPENAI_API_ENDPOINT:
                logger.error("❌ AZURE_OPENAI_API_ENDPOINT not set, chat model will not be available")
                return None
                
            logger.info(f"🔧 Setting up Azure OpenAI with deployment: {AZURE_OPENAI_MODEL}")
            logger.info(f"🔧 Azure OpenAI Endpoint: {AZURE_OPENAI_API_ENDPOINT}")
            logger.info(f"🔧 Azure OpenAI API Version: {AZURE_OPENAI_API_VERSION}")
            logger.info(f"🔧 Azure OpenAI API Key (first 8 chars): {AZURE_OPENAI_API_KEY[:8]}...")
            
            llm = AzureChatOpenAI(
                deployment_name=AZURE_OPENAI_MODEL,
                azure_endpoint=f"{BASE_URL}{AZURE_OPENAI_API_ENDPOINT}",
                api_version=AZURE_OPENAI_API_VERSION,
                api_key=AZURE_OPENAI_API_KEY,
                temperature=AZURE_OPENAI_TEMPERATURE,
                max_tokens=AZURE_OPENAI_MAX_TOKENS,
            )
            
            logger.info("✅ Azure OpenAI chat model setup successful")
            return llm
            
        except Exception as e:
            logger.error(f"❌ Failed to setup Azure OpenAI chat model: {e}")
            logger.error(f"❌ Model: {AZURE_OPENAI_MODEL}")
            logger.error(f"❌ Endpoint: {AZURE_OPENAI_API_ENDPOINT}")
            return None
    
    def _create_workflow(self):
        """Create the LangGraph workflow with nodes and edges"""
        workflow = StateGraph(State)
        
        # Add nodes
        workflow.add_node("manage_memory", self.manage_conversation_memory)
        workflow.add_node("retrieve_from_kb", self.retrieve_from_knowledge_base)
        workflow.add_node("generate_response", self.generate_chat_response)
        
        # Add edges - workflow flow with memory management
        workflow.set_entry_point("manage_memory")
        workflow.add_edge("manage_memory", "retrieve_from_kb")
        workflow.add_edge("retrieve_from_kb", "generate_response")
        workflow.add_edge("generate_response", END)
        
        return workflow.compile()
    
    def manage_conversation_memory(self, state: State) -> State:
        """
        LangGraph Memory Management Node - handles conversation memory efficiently
        """
        logger.info("Managing conversation memory")
        
        conversation_id = state.get("conversation_id", "")
        messages = state.get("messages", [])
        memory_mode = state.get("memory_mode", "sliding_window")
        max_turns = state.get("max_memory_turns", 10)
        
        # Apply memory management strategy
        if memory_mode == "sliding_window":
            # Keep only the most recent N turns (2 messages per turn)
            max_messages = max_turns * 2
            if len(messages) > max_messages:
                # Keep system message (if any) + recent messages
                system_messages = [msg for msg in messages if getattr(msg, 'type', None) == 'system']
                recent_messages = messages[-max_messages:]
                managed_messages = system_messages + recent_messages
            else:
                managed_messages = messages
                
        elif memory_mode == "summary":
            # Summarize older conversations (implement if needed)
            managed_messages = self._summarize_old_messages(messages, max_turns)
            
        else:  # "full" - keep all messages
            managed_messages = messages
        
        # Update state with managed memory
        state["messages"] = managed_messages
        
        logger.info(f"Memory management: {len(messages)} -> {len(managed_messages)} messages (mode: {memory_mode})")
        return state
    
    def _summarize_old_messages(self, messages: List, max_turns: int) -> List:
        """
        Summarize older messages to save tokens while preserving context
        """
        max_recent_messages = max_turns * 2
        
        if len(messages) <= max_recent_messages:
            return messages
        
        # Keep recent messages as-is
        recent_messages = messages[-max_recent_messages:]
        old_messages = messages[:-max_recent_messages]
        
        # Create summary of old messages
        old_content = "\n".join([
            f"User: {msg.content}" if hasattr(msg, 'content') and msg.__class__.__name__ == 'HumanMessage' 
            else f"Assistant: {msg.content}" if hasattr(msg, 'content') 
            else str(msg)
            for msg in old_messages
        ])
        
        summary_content = f"Previous conversation summary: {old_content[:500]}..."
        summary_message = AIMessage(content=f"[SUMMARY] {summary_content}")
        
        return [summary_message] + recent_messages
    
    def retrieve_from_knowledge_base(self, state: State) -> State:
        """
        Node 1: Retrieve relevant context from Bedrock Knowledge Base
        """
        logger.info("Retrieving context from Bedrock Knowledge Base")
        
        user_query = state.get("user_query", "")
        context_documents = []
        
        if self.bedrock_agent_client and user_query and KNOWLEDGE_BASE_ID:
            
            try:
                logger.info(f"🔍 Querying Knowledge Base ID: {KNOWLEDGE_BASE_ID}")
                
                # Get environment and vector_db parameters
                env = os.getenv('ENV', 'dev')  # Default to 'dev' if not set
                vector_db = "872051E8-E5C8-4AD1-83A8-ADB347D6C2CC"  # Use KB ID as fallback
                
                # Enhanced retrieval configuration for complex queries
                query_complexity = self._assess_query_complexity(user_query)
                results_count = min(10 if query_complexity == 'complex' else 5, 10)  # Max 10 for complex
                
                retrieval_config = {
                    "vectorSearchConfiguration": {
                        "numberOfResults": results_count,
                        "overrideSearchType": "SEMANTIC",
                        "filter": {
                            "andAll": [
                                {"equals": {"key": "knowledgeBaseId", "value": vector_db}},
                                {
                                    "startsWith": {
                                        "key": "x-amz-bedrock-kb-source-uri",
                                        "value": f"s3://docops-kb-{env}/{vector_db}/",
                                    }
                                },
                            ]
                        }
                    }
                }
                
                logger.info(f"Query complexity: {query_complexity}, retrieving {results_count} documents")
                
                logger.info(f"🔍 Using filters - Environment: {env}, Vector DB: {vector_db}")
                logger.info(f"🔍 S3 path filter: s3://docops-kb-{env}/{vector_db}/")
                
                response = self.bedrock_agent_client.retrieve(
                    knowledgeBaseId=KNOWLEDGE_BASE_ID,
                    retrievalQuery={'text': user_query},
                    retrievalConfiguration=retrieval_config
                )
                
                # Extract retrieved content
                for i, result in enumerate(response.get('retrievalResults', []), 1):
                    metadata = result.get('metadata', {})
                    content_text = result.get('content', {}).get('text', '')
                    score = result.get('score', 0)
                    
                    document_info = {
                        'content': content_text,
                        'score': score,  # Relevance score
                        'metadata': result.get('metadata', {})  # Additional metadata
                    }
                    context_documents.append(document_info)
                    
                    # Enhanced logging for debugging
                    logger.info(f"Document {i}: Title='{metadata.get('title', 'N/A')}', Score={score:.3f}, Content_length={len(content_text)}")
                    logger.debug(f"Document {i} content preview: {content_text[:200]}...")
                        
                logger.info(f"Retrieved {len(context_documents)} documents from Knowledge Base")
                        
            except Exception as e:
                logger.error(f"Error retrieving from Knowledge Base: {e}")
        elif not KNOWLEDGE_BASE_ID:
            logger.warning("⚠️  Knowledge Base retrieval skipped: KNOWLEDGE_BASE_ID not configured")
        elif not user_query:
            logger.warning("⚠️  Knowledge Base retrieval skipped: No user query provided")
        elif not self.bedrock_agent_client:
            logger.warning("⚠️  Knowledge Base retrieval skipped: Bedrock agent client not available")
        
        # Update state
        state["context_documents"] = context_documents
        state["has_context"] = bool(context_documents)
        return state
    
    def generate_chat_response(self, state: State) -> State:
        """
        Node 2: Generate response using Bedrock chat model with retrieved context
        """
        logger.info("Generating chat response using Bedrock model")
        
        user_query = state.get("user_query", "")
        context_documents = state.get("context_documents", [])
        conversation_id = state.get("conversation_id", "")
        
        # Prepare context-aware prompt with detailed system instructions
        system_instructions = """You are an AI assistant designed to provide accurate and comprehensive answers based on information from the vector database. Follow these guidelines:

1. **Context-Based Information**:
- Use only the data available in the current context from the vector database.
- If you have context documents but they don't directly answer the specific question, try to provide related information from the context that might be helpful.
- Only respond with "I am not able to obtain an answer for this particular query" if the context is completely unrelated to the question or if no context is provided.

2. **Detailed Information**:
- Provide thorough and well-organized responses using the context data.
- Use headings, bullet points, or numbered lists to structure information clearly.
- Apply bold or italic formatting for emphasis where needed.

3. **Emotes**:
- Incorporate appropriate emotes based on the content and tone of the query.
- Use positive emotes for encouraging responses and neutral or informative emotes for factual information.

4. **Table Generation**:
- If the query requests data in a table format, generate and present the information using the context data.
- Ensure the table is well-organized with headers and properly aligned columns.
- Use Markdown or other formatting tools to enhance readability.

5. **Chat Format**:
- For chat or conversation-related queries, structure your response in a conversational format.
- Use formatting to differentiate between user inputs and responses.

6. **Specific Formats**:
- If the user requests information in a specific format (e.g., JSON, XML, Markdown), provide the response using the context data.
- Ensure the format is applied correctly and the data is structured appropriately.

7. **Non-Professional Topics**:
- If the query concerns non-professional subjects (e.g., politics, sports), politely redirect the user to relevant professional topics.
- Suggest related professional queries and provide a concise explanation.

8. **Accuracy and Citations**:
- Ensure responses are accurate and solely based on the data in the current context.
- Do not provide information not mentioned in the context. Do not add any additional information that is not present in the context.

Keep your responses clear, informative, and engaging, ensuring they are derived exclusively from the provided context."""

        # Initialize selected_docs
        selected_docs = []
        
        if context_documents:
            # Enhanced context selection for complex queries
            selected_docs = self._select_optimal_documents(context_documents, user_query)
            context = "\n\n---DOCUMENT SEPARATOR---\n\n".join([doc['content'] for doc in selected_docs])
            
            # Log the context for debugging
            logger.info(f"Context documents found: {len(context_documents)}")
            logger.info(f"Selected documents: {len(selected_docs)}")
            logger.info(f"Context content length: {len(context)} characters")
            logger.info(f"First 200 chars of context: {context[:200]}...")
            
            # Check if we have meaningful content
            if context.strip() and len(context.strip()) > 10:
                # Build sources text for inclusion in the AI response
                sources_text = self._build_sources_text(selected_docs)
                
                prompt = f"""{system_instructions}

Context:
{context}

User Question: {user_query}

Please provide a well-formatted answer based on the context above following the guidelines specified. Reference the source numbers when citing information.

IMPORTANT: After providing your main answer, you MUST include the following sources section exactly as shown:

{sources_text}

This sources section should be included as part of your response to help users access the original documents."""
            else:
                # No meaningful content found in documents
                logger.warning("Documents retrieved but no meaningful content found")
                prompt = f"""{system_instructions}

User Question: {user_query}

Since the retrieved documents do not contain sufficient information to answer your query, please respond with: "I am not able to obtain an answer for this particular query." and suggest the user provide more specific information or try rephrasing their question."""
        else:
            prompt = f"""{system_instructions}

User Question: {user_query}

Since no specific context is available from the vector database, please respond with: "I am not able to obtain an answer for this particular query." and suggest the user provide more specific information or try rephrasing their question."""
        
        try:
            if self.chat_model:
                # Use LangGraph-managed conversation history
                previous_messages = state.get("messages", [])
                
                # Create messages including conversation history
                messages = previous_messages + [HumanMessage(content=prompt)]
                
                # Log conversation context
                logger.info(f"Using {len(previous_messages)} previous messages from current session")
                logger.info("Starting Azure OpenAI streaming response...")
                
                # Check if WebSocket connection info is available in state
                connection_info = state.get("websocket_connection", {})
                connection_id = connection_info.get("connectionId")
                url = connection_info.get("url")
                
                if connection_id and url and ENABLE_WEBSOCKET_STREAMING:
                    # Use WordLevelStreamingHandler for advanced streaming
                    streaming_handler = WordLevelStreamingHandler(
                        connection_id=connection_id,
                        websocket_url=url,
                        conversation_id=conversation_id,
                        trace_id=conversation_id
                    )
                    
                    # Send start signal immediately
                    streaming_handler.send_start_signal()
                    
                    # Process streaming response
                    logger.info("Using word-level streaming handler for response")
                    logger.info(f"Messages sent to model: {messages}")
                    ai_response = streaming_handler.process_word_streaming(
                        self.chat_model.stream(messages)
                    )
                else:
                    # Fallback to regular invoke if no WebSocket info or streaming disabled
                    logger.info("Using regular invoke (streaming disabled or no WebSocket info)")
                    response = self.chat_model.invoke(messages)
                    ai_response = response.content if hasattr(response, 'content') else str(response)
                
                logger.info("Successfully generated AI response")
                
            else:
                ai_response = "I apologize, but the AI service is currently unavailable. Please try again later."
                logger.error("Chat model not available")
                
        except Exception as e:
            logger.error(f"Error generating AI response: {e}")
            logger.error(f"Error type: {type(e).__name__}")
            if hasattr(e, 'status_code'):
                logger.error(f"HTTP Status Code: {e.status_code}")
            if hasattr(e, 'response'):
                logger.error(f"Response: {e.response}")
            ai_response = "I encountered an error while processing your request. Please try again."
        
        # Update state with response using LangGraph's add_messages pattern
        state["ai_response"] = ai_response
        
        # Use LangGraph's recommended message handling
        new_messages = [
            HumanMessage(content=user_query),
            AIMessage(content=ai_response)
        ]
        state["messages"] = add_messages(state.get("messages", []), new_messages)
        
        # Extract source information from context documents
        sources_info = []
        logger.info(f"Processing {len(context_documents)} context documents for source extraction")
        
        # for i, doc in enumerate(context_documents):
        #     logger.info(f"Document {i+1} structure: {type(doc)}")
        #     logger.info(f"Document {i+1} keys: {doc.keys() if isinstance(doc, dict) else 'Not a dict'}")
            
        #     if isinstance(doc, dict):
        #         location = doc.get('location', {})
        #         logger.info(f"Document {i+1} location: {location}")
                
        #         # Handle different possible location structures
        #         uri = ''
        #         if 's3Location' in location:
        #             uri = location.get('s3Location', {}).get('uri', '')
        #         elif 'uri' in location:
        #             uri = location.get('uri', '')
                
        #         source_info = {
        #             'uri': uri,
        #             'score': doc.get('score', 0),
        #             'type': location.get('type', 'unknown'),
        #             'metadata': doc.get('metadata', {}),
        #             'location_raw': location  # Include raw location for debugging
        #         }
        #         sources_info.append(source_info)
        #         logger.info(f"Added source info: {source_info}")
        
        # logger.info(f"Final sources_info: {sources_info}")
        # state["sources_info"] = sources_info
        return state
    
    def _select_optimal_documents(self, context_documents: List[Dict], user_query: str) -> List[Dict]:
        """
        Select optimal documents based on query complexity and token limits
        """
        if not context_documents:
            return []
            
        # Simple query indicators (can be enhanced with NLP analysis)
        simple_indicators = ['what is', 'how to', 'define', 'explain']
        complex_indicators = ['troubleshoot', 'issue', 'problem', 'error', 'failure', 'multiple', 'compare', 'analyze']
        
        query_lower = user_query.lower()
        is_complex_query = any(indicator in query_lower for indicator in complex_indicators)
        is_simple_query = any(indicator in query_lower for indicator in simple_indicators)
        
        # Estimate token usage (rough approximation: 4 chars per token)
        max_context_tokens = AZURE_OPENAI_MAX_TOKENS * 0.6  # Reserve 40% for response
        current_tokens = 0
        selected_docs = []
        
        # Sort documents by relevance score (highest first)
        sorted_docs = sorted(context_documents, key=lambda x: x.get('score', 0), reverse=True)
        
        # Log the scores for debugging
        logger.info("Document scores: " + ", ".join([f"{doc.get('score', 0):.3f}" for doc in sorted_docs[:5]]))
        
        for doc in sorted_docs:
            content = doc.get('content', '').strip()
            doc_score = doc.get('score', 0)
            
            # Skip documents with no content
            if not content or len(content) < 10:
                logger.warning(f"Skipping document with insufficient content (length: {len(content)})")
                continue
            
            doc_tokens = len(content) / 4  # Rough token estimation
            
            # Decision logic based on query complexity
            if is_complex_query:
                # For complex queries, prioritize more documents up to token limit
                # Lower the score threshold for complex queries
                if current_tokens + doc_tokens <= max_context_tokens and len(selected_docs) < 4 and doc_score > 0.3:
                    selected_docs.append(doc)
                    current_tokens += doc_tokens
                    logger.info(f"Complex query: Added document with score {doc_score:.3f}")
            elif is_simple_query:
                # For simple queries, use fewer but highest-quality documents
                # Be more selective for simple queries
                if len(selected_docs) < 1 or (len(selected_docs) < 2 and doc_score > 0.5):
                    selected_docs.append(doc)
                    current_tokens += doc_tokens
                    logger.info(f"Simple query: Added high-score document {doc_score:.3f}")
            else:
                # Default behavior for moderate complexity
                # Use a moderate threshold
                if len(selected_docs) < 3 and doc_score > 0.4:
                    selected_docs.append(doc)
                    current_tokens += doc_tokens
                    logger.info(f"Default: Added document with score {doc_score:.3f}")
            
            # Stop if we've reached reasonable limits
            if current_tokens >= max_context_tokens:
                logger.info(f"Token limit reached. Using {len(selected_docs)} documents.")
                break
        
        # If no documents meet the score threshold, take the best one anyway
        if not selected_docs and sorted_docs:
            best_doc = sorted_docs[0]
            if best_doc.get('content', '').strip():
                selected_docs.append(best_doc)
                logger.info(f"Fallback: Added best document with score {best_doc.get('score', 0):.3f}")
        
        scores_list = [f"{doc.get('score', 0):.3f}" for doc in selected_docs]
        logger.info(f"Selected {len(selected_docs)} documents for query. Scores: {scores_list}")
        return selected_docs
    
    def _build_sources_text(self, selected_docs: List[Dict]) -> str:
        """
        Build formatted sources text with clickable links for streaming inclusion
        """
        if not selected_docs:
            return ""
        
        sources_lines = ["\n\n**Source[s]:**"]
        
        for i, doc in enumerate(selected_docs, 1):
            metadata = doc.get('metadata', {})
            title = metadata.get('title', f'Document {i}')
            doc_link = metadata.get('docLink', '')
            
            if doc_link:
                # Create markdown link format
                source_line = f"{i}. [{title}]({doc_link})"
            else:
                # Just show the title if no link available
                source_line = f"{i}. {title}"
            
            sources_lines.append(source_line)
        
        return "\n".join(sources_lines)
    
    def _assess_query_complexity(self, user_query: str) -> str:
        """
        Assess query complexity to determine retrieval strategy
        """
        query_lower = user_query.lower()
        
        # Complex query patterns
        complex_patterns = [
            'multiple', 'several', 'various', 'different',
            'compare', 'versus', 'vs', 'difference between',
            'troubleshoot', 'diagnose', 'analyze', 'investigate',
            'step by step', 'detailed', 'comprehensive',
            'issue', 'problem', 'error', 'failure', 'bug',
            'and', '&', 'also', 'additionally', 'furthermore'
        ]
        
        # Simple query patterns  
        simple_patterns = [
            'what is', 'define', 'meaning of',
            'how to', 'show me', 'explain',
            'list', 'give me', 'provide'
        ]
        
        complex_score = sum(1 for pattern in complex_patterns if pattern in query_lower)
        simple_score = sum(1 for pattern in simple_patterns if pattern in query_lower)
        
        # Additional complexity indicators
        word_count = len(user_query.split())
        has_technical_terms = any(term in query_lower for term in [
            'kubernetes', 'docker', 'pod', 'container', 'service',
            'deployment', 'configmap', 'secret', 'ingress'
        ])
        
        if complex_score >= 2 or word_count > 15 or (complex_score >= 1 and has_technical_terms):
            return 'complex'
        elif simple_score >= 1 and word_count <= 8:
            return 'simple'
        else:
            return 'moderate'
    
    def process_chat_query(self, user_query: str, conversation_id: str = None, vector_db: str = None, websocket_connection: Dict = None, previous_messages: List = None) -> Dict[str, Any]:
        """
        Main method to process a chat query through the LangGraph workflow
        """
        try:
            # Initialize state with enhanced memory configuration
            initial_state = {
                "user_query": user_query,
                "conversation_id": conversation_id or str(uuid.uuid4()),
                "context_documents": [],
                "messages": previous_messages or [],  # Include previous messages from this session
                "ai_response": "",
                "has_context": False,
                "vector_db": vector_db or KNOWLEDGE_BASE_ID,
                "websocket_connection": websocket_connection or {},
                # Enhanced memory settings
                "memory_mode": "sliding_window",  # Options: 'full', 'sliding_window', 'summary'
                "max_memory_turns": 8,  # Keep last 8 conversation turns
                "conversation_summary": ""
            }
            
            # Execute the workflow
            final_state = self.workflow.invoke(initial_state)
            
            # Return structured response with LangGraph state
            return {
                "success": True,
                "ai_response": final_state.get("ai_response", ""),
                "context_used": final_state.get("has_context", False),
                "sources_count": len(final_state.get("context_documents", [])),
                "sources_info": final_state.get("sources_info", []),
                "conversation_id": final_state.get("conversation_id", ""),
                "model_used": AZURE_OPENAI_MODEL,
                "timestamp": datetime.now().isoformat(),
                "final_state": final_state  # Include full state for memory extraction
            }
            
        except Exception as e:
            logger.error(f"LangGraph workflow execution failed: {e}")
            return {
                "success": False,
                "error": "Failed to process chat query",
                "ai_response": "I apologize, but I encountered an error processing your request.",
                "context_used": False,
                "sources_count": 0,
                "conversation_id": conversation_id or str(uuid.uuid4()),
                "timestamp": datetime.now().isoformat()
            }

# Initialize global workflow instance
bedrock_workflow = BedrockKnowledgeBaseWorkflow()

@authenticate_websocket()
# @require_resource_permission('CHATKBBEDROCKCDKWEBSOCKET', 'CREATE')
def create(event, context):
    """
    Main function to handle the creation of a new item.
    
    This function processes incoming events to create a new item in a DynamoDB table.
    It validates the request data, constructs the item and
    inserts it into the database. It also handles errors and sends responses back to
    the client via WebSocket.
    
    :param event: The event data received from the client.
    :param context: The context in which the function is executed.
    :return: A dictionary containing the status code and body message.
    """
    logger.debug('logging event: %s', event)  # Log the incoming event
    logger.info('Inside create function')  # Log entry into the function
    
    # Define status codes
    STATUS_ERROR = 500
    STATUS_UNPROCESSABLE_ENTITY = 422
    STATUS_CREATED = 201
    
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

        # Validate the request data schema
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
            # If validation fails, send a response to the client and return
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
        
        logger.info(f"Creating item for authenticated user: {email} (ID: {user_id})")
        
        # SEND IMMEDIATE STREAMING SIGNALS - BEFORE ANY PROCESSING
        try:
            # Send thinking signal immediately to show processing has started
            thinking_payload = {
                "type": "streaming_thinking",
                "message": "Processing your request...",
                "streaming_mode": "word_level"
            }
            send_to_client(connectionId, json.dumps(thinking_payload), url)
            logger.info("⚡ IMMEDIATE thinking signal sent - no processing delay")
            
            # Send start signal immediately
            start_payload = {
                "type": "streaming_start",
                "message": "AI is generating response word by word...",
                "streaming_mode": "word_level",
                "conversation_id": str(uuid.uuid4())
            }
            send_to_client(connectionId, json.dumps(start_payload), url)
            logger.info("⚡ IMMEDIATE streaming start signal sent - no processing delay")
        except Exception as e:
            logger.warning(f"Failed to send immediate streaming signals: {str(e)}")
        
        # Process chat query using LangGraph workflow with Bedrock Knowledge Base
        user_query = validation_schema['datas'].get('query', '')
        conversation_id = validation_schema['datas'].get('conversationId', str(uuid.uuid4()))
        vector_db = validation_schema['datas'].get('vectorDb', KNOWLEDGE_BASE_ID)  # Get vector DB parameter
        
        # Get previous messages from request (LangGraph will manage these)
        previous_messages_data = validation_schema['datas'].get('previousMessages', [])
        
        # Convert to LangChain format for LangGraph state
        previous_messages = []
        for msg in previous_messages_data:
            if msg.get('role') == 'user':
                previous_messages.append(HumanMessage(content=msg.get('content', '')))
            elif msg.get('role') == 'assistant':
                previous_messages.append(AIMessage(content=msg.get('content', '')))
        
        if user_query:
            logger.info(f"Processing chat query with LangGraph workflow: {user_query[:100]}...")
            logger.info(f"Using vector DB: {vector_db}")
            
            try:
                # Prepare WebSocket connection info for streaming
                websocket_connection = {
                    "connectionId": connectionId,
                    "url": url
                }
                
                # Execute LangGraph workflow with vector DB filter and WebSocket streaming
                workflow_result = bedrock_workflow.process_chat_query(user_query, conversation_id, vector_db, websocket_connection, previous_messages)
                
                if workflow_result.get('success', False):
                    # Add AI response data to the item being stored
                    validation_schema['datas']['aiResponse'] = workflow_result.get('ai_response', '')
                    validation_schema['datas']['contextUsed'] = workflow_result.get('context_used', False)
                    validation_schema['datas']['sourcesCount'] = workflow_result.get('sources_count', 0)
                    validation_schema['datas']['sourcesInfo'] = workflow_result.get('sources_info', [])
                    validation_schema['datas']['modelUsed'] = workflow_result.get('model_used', AZURE_OPENAI_MODEL)
                    validation_schema['datas']['conversationId'] = workflow_result.get('conversation_id', conversation_id)
                    
                    logger.info("LangGraph workflow completed successfully")
                    
                    # Send immediate AI response to client via WebSocket
                    # Extract user info from the event (from authentication middleware)
                    user_email = 'unknown@example.com'  # Default fallback
                    
                    try:
                        # Method 1: From authentication middleware (added by @authenticate_websocket decorator)
                        auth_info = event.get('auth', {})
                        if auth_info and auth_info.get('is_authenticated'):
                            user_info = auth_info.get('user_info', {})
                            user_email = user_info.get('email', '')
                            if user_email:
                                logger.info(f"Found email from auth middleware: {user_email}")
                        
                        # Method 2: From requestContext (for REST APIs)
                        if not user_email:
                            user_email = event.get('requestContext', {}).get('authorizer', {}).get('email', '')
                            if user_email:
                                logger.info(f"Found email in requestContext: {user_email}")
                        
                        # Method 3: Extract from JWT token directly as fallback
                        if not user_email:
                            from src.helpers.cognito_auth import extract_token_from_event, extract_user_info
                            token = extract_token_from_event(event)
                            if token:
                                user_info = extract_user_info(token)
                                user_email = user_info.get('email', '')
                                if user_email:
                                    logger.info(f"Found email from JWT token: {user_email}")
                            
                    except Exception as e:
                        logger.error(f"Error extracting user email: {e}")
                    
                    # Final fallback
                    if not user_email or user_email == '':
                        user_email = 'unknown@example.com'
                        logger.warning("Could not extract user email, using fallback")
                    
                    logger.info(f"Using user email: {user_email}")
                    
                    # Create chat history entry
                    chat_history_entry = {
                        "user": validation_schema['datas'].get('query', ''),
                        "aiAssistant": workflow_result.get('ai_response', ''),
                        "traceId": workflow_result.get('conversation_id', conversation_id)
                    }
                    
                    # Build current session messages managed by LangGraph
                    final_state_messages = workflow_result.get('final_state', {}).get('messages', [])
                    
                    # Convert LangGraph messages back to frontend format
                    session_messages = []
                    for msg in final_state_messages:
                        if hasattr(msg, 'content'):
                            role = 'user' if msg.__class__.__name__ == 'HumanMessage' else 'assistant'
                            session_messages.append({
                                "role": role,
                                "content": msg.content
                            })
                    
                    # Create new response format with LangGraph-managed memory
                    new_format_response = {
                        "userId": user_email,
                        "conversationId": workflow_result.get('conversation_id', conversation_id),
                        "chatHistory": [chat_history_entry],
                        "sessionMessages": session_messages,  # LangGraph-managed memory
                        "memoryInfo": {
                            "memoryMode": "sliding_window",
                            "managedMessages": len(session_messages),
                            "maxTurns": 8
                        },
                        "trace_id": workflow_result.get('conversation_id', conversation_id),
                        "sources": workflow_result.get('sources_info', []),
                        "contextUsed": workflow_result.get('context_used', False),
                        "sourcesCount": workflow_result.get('sources_count', 0)
                    }
                    
                    # Final response with data and status at top level
                    final_response = {
                        "data": new_format_response,
                        "status": 201
                    }
                    
                    send_to_client(connectionId, json.dumps(final_response), url)
                    
                else:
                    # Workflow failed, but continue with regular processing
                    logger.warning(f"LangGraph workflow failed: {workflow_result.get('error', 'Unknown error')}")
                    validation_schema['datas']['aiResponse'] = 'AI processing temporarily unavailable'
                    validation_schema['datas']['contextUsed'] = False
                    validation_schema['datas']['sourcesCount'] = 0
                    validation_schema['datas']['modelUsed'] = 'AZURE_OPENAI_GPT_4O'
                    validation_schema['datas']['conversationId'] = conversation_id
                    
            except Exception as workflow_err:
                logger.error(f"LangGraph workflow execution error: {workflow_err}")
                # Continue with regular processing even if AI workflow fails
                validation_schema['datas']['aiResponse'] = 'AI processing encountered an error'
                validation_schema['datas']['contextUsed'] = False
                validation_schema['datas']['sourcesCount'] = 0
                validation_schema['datas']['modelUsed'] = 'AZURE_OPENAI_GPT_4O'
                validation_schema['datas']['conversationId'] = conversation_id
        else:
            logger.warning("No query provided for AI processing")
            validation_schema['datas']['conversationId'] = conversation_id
        
        validation_schema['datas']['createdBy'] = email
        validation_schema['datas']['updatedBy'] = email
        validation_schema['datas']['createdAt'] = datetime.now().isoformat()
        validation_schema['datas']['updatedAt'] = datetime.now().isoformat()

        # Construct the new item to be inserted
        try:
            new_item = construct_new_item(validation_schema['datas'])
            logger.debug('New item to be inserted: %s', new_item)
        except Exception as construct_err:
            logger.error(f"Error constructing new item: {str(construct_err)}")
            response_result = Responses.result_response(STATUS_ERROR, False, 'Error constructing item.')
            send_to_client(connectionId, json.dumps(construct_response(response_result)), url)
            return {
                'statusCode': STATUS_ERROR,
                'body': json.dumps('Error constructing item')
            }

        try:
            # Insert the new item into the DynamoDB table
            table.put_item(Item=new_item)
            # Iterate over each field in the new item and send a message for each field
            try:
                for key, value in new_item.items():
                    if key == 'updatedBy':  # Skip the 'updatedBy' field
                        continue
                    
                    params_for_queue = {
                        'timestamp': datetime.now().isoformat(),  # Current timestamp
                        'actionType': 'CREATE',  # Action type for the queue message
                        'entityType': os.getenv('SERVICE_NAME', os.getenv('TABLE')),  # Entity type, derived from the service name
                        'fieldName': key,  # The name of the field
                        'oldValue': '-',  # Set oldValue to a hyphen
                        'newValue': value,  # The new value of the field
                        'userId': email,  # The email of the user who created the item
                    }
                    
                    # Send the message to the SQS queue
                    send_message_to_queue(params_for_queue)
            except Exception as queue_error:
                logger.error(f"Failed to send audit messages: {str(queue_error)}")
                # Don't fail the main operation if audit logging fails
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
    try:
        send_to_client(connectionId, json.dumps(construct_response(response_result)), url)
    except Exception as websocket_err:
        logger.error(f"Error sending response to client: {str(websocket_err)}")
        # Don't return error here as the main operation might have succeeded

    return {
        'statusCode': STATUS_CREATED,
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