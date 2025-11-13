import os  # Provides a way of using operating system dependent functionality
import json  # Provides methods to work with JSON data
import uuid  # Provides immutable UUID objects (universally unique identifiers)
import boto3  # AWS SDK for Python to interact with AWS services
import logging  # Provides a way to configure and use loggers
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
    """State object for LangGraph workflow"""
    messages: List[Any]
    user_query: str
    context_documents: List[str]
    conversation_id: str
    ai_response: str
    has_context: bool
    websocket_connection: Dict[str, Any]
    vector_db: str

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
    
    def process_word_streaming(self, llm_response_generator):
        """
        Process the streaming response from the LLM and send individual words to the client.
        """
        try:
            import time
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
        import time
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
        workflow.add_node("retrieve_from_kb", self.retrieve_from_knowledge_base)
        workflow.add_node("generate_response", self.generate_chat_response)
        
        # Add edges - workflow flow
        workflow.set_entry_point("retrieve_from_kb")
        workflow.add_edge("retrieve_from_kb", "generate_response")
        workflow.add_edge("generate_response", END)
        
        return workflow.compile()
    
    def retrieve_from_knowledge_base(self, state: State) -> State:
        """
        Node 1: Retrieve relevant context from Bedrock Knowledge Base
        """
        logger.info("Retrieving context from Bedrock Knowledge Base")
        
        user_query = state.get("user_query", "")
        context_documents = []
        
        if self.bedrock_agent_client and user_query and KNOWLEDGE_BASE_ID:
            
            try:
                logger.info(f"Querying Knowledge Base ID: {KNOWLEDGE_BASE_ID}")
                
                # Get environment and vector_db parameters
                env = os.getenv('ENV', 'dev')  # Default to 'dev' if not set
                vector_db = "872051E8-E5C8-4AD1-83A8-ADB347D6C2CC"  # Use KB ID as fallback
                
                # Build retrieval configuration with filters
                retrieval_config = {
                    "vectorSearchConfiguration": {
                        "numberOfResults": 5,
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
                

                
                response = self.bedrock_agent_client.retrieve(
                    knowledgeBaseId=KNOWLEDGE_BASE_ID,
                    retrievalQuery={'text': user_query},
                    retrievalConfiguration=retrieval_config
                )
                
                # Extract retrieved content
                for result in response.get('retrievalResults', []):
                    document_info = {
                        'content': result.get('content', {}).get('text', ''),
                        'score': result.get('score', 0),  # Relevance score
                        'location': result.get('location', {}),  # Source location
                        'metadata': result.get('metadata', {})  # Additional metadata
                    }
                    context_documents.append(document_info)
                    logger.debug(f"Retrieved context snippet: {document_info['content'][:100]}...")
                        
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
        
        # Prepare STRICT KB-only prompt with strong enforcement
        system_instructions = """You are an AI assistant designed to provide accurate and comprehensive answers based on information from the vector database. You have two search tools at your disposal:

                1. **Context-Based Information**:
                - Use only the data available in the current context from the vector database.
                - If the required information is not present in the context, respond with: "I am not able to obtain an answer for this particular query."

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

                Keep your responses clear, informative, and engaging, ensuring they are derived exclusively from the provided context.
                """

        if context_documents:
            # Use top 2 most relevant documents and validate relevance
            relevant_docs = []
            context_texts = []
            
            for doc in context_documents[:2]:
                content = doc['content']
                score = doc.get('score', 0)
                
                # Only include documents with sufficient relevance score
                if score > 0.3:  # Minimum relevance threshold (lowered to include more sources)
                    relevant_docs.append(doc)
                    context_texts.append(f"Document {len(relevant_docs)} (Relevance: {score:.2f}):\n{content}")
                    logger.info(f"Including document with score {score:.2f}: {content[:100]}...")
                else:
                    logger.info(f"Excluding low-relevance document (score: {score:.2f}): {content[:100]}...")
            
            if relevant_docs:
                context = "\n\n".join(context_texts)
                logger.info(f"📚 KB-ONLY MODE: Using {len(relevant_docs)} relevant documents for response")
                prompt = f"""{system_instructions}

PROVIDED CONTEXT DOCUMENTS:
{context}

USER QUESTION: {user_query}

INSTRUCTIONS: Answer using ONLY the information from the context documents above. Start your response with "Based on the available documents:" """
            else:
                # No sufficiently relevant documents found
                logger.warning(f"📚 KB-ONLY MODE: No documents met relevance threshold (>0.3) for query: {user_query}")
                prompt = f"""{system_instructions}

USER QUESTION: {user_query}

RESPONSE: I cannot find relevant information in the available documents for this query. The documents in our knowledge base do not appear to contain information about this topic."""
        else:
            # No context documents retrieved
            logger.warning(f"📚 KB-ONLY MODE: No context documents retrieved for query: {user_query}")
            prompt = f"""{system_instructions}

USER QUESTION: {user_query}

RESPONSE: I cannot find relevant information in the available documents for this query. Please try a different question or provide more specific details."""
        
        try:
            if self.chat_model:
                # Create message for the chat model
                messages = [HumanMessage(content=prompt)]
                
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
        
        # Update state with response
        state["ai_response"] = ai_response
        state["messages"] = state.get("messages", []) + [
            HumanMessage(content=user_query),
            AIMessage(content=ai_response)
        ]
        
        # Update the AI response in state
        state["ai_response"] = ai_response
        
        return state
    
    def process_chat_query(self, user_query: str, conversation_id: str = None, vector_db: str = None, websocket_connection: Dict = None) -> Dict[str, Any]:
        """
        Main method to process a chat query through the LangGraph workflow
        """
        try:
            # Initialize state
            initial_state = {
                "user_query": user_query,
                "conversation_id": conversation_id or str(uuid.uuid4()),
                "context_documents": [],
                "messages": [],
                "ai_response": "",
                "has_context": False,
                "vector_db": vector_db or KNOWLEDGE_BASE_ID,
                "websocket_connection": websocket_connection or {}
            }
            
            # Execute the workflow
            final_state = self.workflow.invoke(initial_state)
            
            # Return structured response
            return {
                "success": True,
                "ai_response": final_state.get("ai_response", ""),
                "context_used": final_state.get("has_context", False),
                "sources_count": 0,
                "conversation_id": final_state.get("conversation_id", ""),
                "model_used": AZURE_OPENAI_MODEL,
                "timestamp": datetime.now().isoformat()
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

    logger.debug('logging event: %s', event)
    logger.info('Inside create function')
    
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
        
        # Process chat query using LangGraph workflow with Bedrock Knowledge Base
        user_query = validation_schema['datas'].get('query', '')
        conversation_id = validation_schema['datas'].get('conversationId', str(uuid.uuid4()))
        vector_db = validation_schema['datas'].get('vectorDb', KNOWLEDGE_BASE_ID)  # Get vector DB parameter
        
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
                workflow_result = bedrock_workflow.process_chat_query(user_query, conversation_id, vector_db, websocket_connection)
                
                if workflow_result.get('success', False):
                    # Add AI response data to the item being stored
                    validation_schema['datas']['aiResponse'] = workflow_result.get('ai_response', '')
                    validation_schema['datas']['contextUsed'] = workflow_result.get('context_used', False)
                    validation_schema['datas']['sourcesCount'] = workflow_result.get('sources_count', 0)
                    
                    # Convert complex sourcesInfo to JSON string for DynamoDB compatibility
                    validation_schema['datas']['sourcesInfo'] = '[]'
                    
                    validation_schema['datas']['modelUsed'] = workflow_result.get('model_used', AZURE_OPENAI_MODEL)
                    validation_schema['datas']['conversationId'] = workflow_result.get('conversation_id', conversation_id)
                    
                    logger.info("LangGraph workflow completed successfully")
                    
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
            logger.error(f"DynamoDB Error Type: {type(dynamo_err).__name__}")
            logger.error(f"Item that failed to insert: {json.dumps(new_item, default=str, indent=2)}")
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

def sanitize_for_dynamodb(obj):
    """
    Sanitize data for DynamoDB compatibility by converting unsupported types
    """
    if obj is None:
        return None
    elif isinstance(obj, (str, int, float, bool)):
        return obj
    elif isinstance(obj, dict):
        return {k: sanitize_for_dynamodb(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [sanitize_for_dynamodb(item) for item in obj]
    elif isinstance(obj, datetime):
        return obj.isoformat()
    else:
        # Convert any other type to string
        return str(obj)

def construct_new_item(datas):
    datas['id'] = str(uuid.uuid4())  # Generate a unique ID for the new item
    
    # Sanitize data for DynamoDB compatibility
    sanitized_datas = sanitize_for_dynamodb(datas)
    
    expression = generate_create_query(sanitized_datas)  # Generate the item expression
    return expression

def generate_create_query(fields):
    exp = {}
    for key, item in fields.items():
        exp[key] = item  # Add each field to the expression
    return exp