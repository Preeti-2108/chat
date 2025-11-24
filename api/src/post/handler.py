import os  # Provides a way of using operating system dependent functionality
import json  # Provides methods to work with JSON data
import uuid  # Provides immutable UUID objects (universally unique identifiers)
import boto3  # AWS SDK for Python to interact with AWS services
import logging  # Provides a way to configure and use loggers
from datetime import datetime  # Provides classes for manipulating dates and times.
from typing import Dict, Any, List

# LangGraph and LangChain imports for workflow orchestration
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langchain_core.messages import HumanMessage, AIMessage
from langchain_openai import AzureChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from botocore.config import Config

from src.helpers.api_responses import Responses  # Custom helper for API responses
from src.helpers.construct_response import construct_response  # Custom helper to construct responses
from src.helpers.schema_validation import validate_request_datas_schema_pydantic  # Custom helper to validate request data schema
from src.handler_websocket.handler import send_to_client  # Custom helper to send data to a client via WebSocket
from src.helpers.event_utils import extract_event_info  # Custom helper to extract necessary information from the event
from src.helpers.auth_middleware import authenticate_websocket  # Cognito authentication
from src.helpers.scope_manager import require_resource_permission  # Scope validation
from src.helpers.queue_helper import send_message_to_queue  # Helper function to send messages to an SQS queue

# New organized helpers to reduce redundancy
from src.helpers.streaming_handler import WordLevelStreamingHandler, send_immediate_streaming_signals
from src.helpers.conversation_builder import conversation_builder, extract_user_email_from_event
from src.helpers.document_analyzer import document_analyzer, build_context_aware_prompt
from src.helpers.system_instructions import get_default_system_instructions, get_error_response_templates
from src.helpers.intent_detector import is_simple_query, get_simple_response, create_mock_streaming_response
from src.helpers.query_rewriter import build_query_rewriter, safe_rewrite_query

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
    rewritten_query: str
    context_documents: List[str]
    conversation_id: str
    ai_response: str
    has_context: bool
    websocket_connection: Dict[str, Any]
    vector_db: str
    is_simple_query: bool
    skip_rag: bool
    skip_llm: bool
    simple_response: str

# WordLevelStreamingHandler moved to src/helpers/streaming_handler.py

class BedrockKnowledgeBaseWorkflow:
    """
    LangGraph workflow that orchestrates Bedrock Knowledge Base retrieval and chat generation
    Based on AWS samples: aws-samples/langgraph-bedrock-knowledge-bases
    """
    
    def __init__(self):
        self.bedrock_agent_client = self._setup_bedrock_agent()
        self.chat_model = self._setup_chat_model()
        # Initialize dynamic query rewriter
        self.query_rewriter = build_query_rewriter(self.chat_model)
        # Initialize memory for conversation continuity (following reference pattern)
        self.memory = MemorySaver()
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
        workflow.add_node("detect_intent", self.detect_query_intent)
        workflow.add_node("rewrite_query", self.rewrite_query_node)
        workflow.add_node("retrieve_from_kb", self.retrieve_from_knowledge_base)  
        workflow.add_node("generate_response", self.generate_chat_response)
        workflow.add_node("handle_simple_query", self.handle_simple_query)
        
        # Add edges - workflow flow with conditional routing
        workflow.set_entry_point("detect_intent")
        
        # Conditional edge: if simple query, skip RAG and LLM
        workflow.add_conditional_edges(
            "detect_intent",
            self.route_based_on_intent,
            {
                "simple": "handle_simple_query",
                "complex": "rewrite_query"
            }
        )
        
        # After rewriting, proceed to retrieval
        workflow.add_edge("rewrite_query", "retrieve_from_kb")
        workflow.add_edge("retrieve_from_kb", "generate_response")
        workflow.add_edge("generate_response", END)
        workflow.add_edge("handle_simple_query", END)
        
        compiled_workflow = workflow.compile(checkpointer=self.memory)
        logger.info(f"✅ [WORKFLOW DEBUG] LangGraph workflow compiled successfully with memory checkpointer")
        logger.info(f"🔗 [WORKFLOW DEBUG] Workflow nodes: detect_intent, rewrite_query, retrieve_from_kb, generate_response, handle_simple_query")
        logger.info(f"🔗 [WORKFLOW DEBUG] Conditional edges: detect_intent -> {{simple: handle_simple_query, complex: rewrite_query}}")
        
        return compiled_workflow
    
    def detect_query_intent(self, state: State) -> State:
        """
        Node 0: Detect if query is simple and can be handled without RAG/LLM
        """
        user_query = state.get("user_query", "")
        logger.info(f"🧠 Detecting intent for query: '{user_query[:50]}...'")
        
        # Use document analyzer's skip_rag method for comprehensive analysis
        skip_decision = document_analyzer.should_skip_rag(user_query)
        
        state["is_simple_query"] = skip_decision["skip_rag"]
        state["skip_rag"] = skip_decision["skip_rag"]
        state["skip_llm"] = skip_decision["skip_llm"]
        
        if skip_decision["skip_rag"]:
            state["simple_response"] = skip_decision["simple_response"]
            logger.info(f"✅ Simple query detected - Cost savings: {skip_decision['estimated_savings']['cost']}")
            logger.info(f"📊 Processing method: {skip_decision['estimated_savings']['processing_method']}")
        else:
            logger.info(f"🔄 Complex query - Proceeding with RAG + LLM: {skip_decision['reason']}")
        
        logger.info(f"🔍 [WORKFLOW DEBUG] Final state after detect_intent: skip_rag={state.get('skip_rag')}, is_simple_query={state.get('is_simple_query')}")
        
        return state
    
    def rewrite_query_node(self, state: State) -> State:
        """
        Node: Dynamically rewrite query for better document retrieval
        """
        user_query = state.get("user_query", "")
        logger.info(f"🔧 [REWRITE_QUERY_NODE] EXECUTING! Query: '{user_query[:50]}...'")
        logger.info(f"🔧 [REWRITE_QUERY_NODE] State keys: {list(state.keys())}")
        
        # Use the dynamic query rewriter with safe fallback
        rewritten_query = safe_rewrite_query(self.query_rewriter, user_query)
        
        if rewritten_query != user_query:
            logger.info(f"✅ [REWRITE_QUERY_NODE] Query optimized: '{user_query}' → '{rewritten_query}'")
        else:
            logger.info(f"💡 [REWRITE_QUERY_NODE] Query unchanged: '{user_query}'")
            
        state["rewritten_query"] = rewritten_query
        logger.info(f"🔧 [REWRITE_QUERY_NODE] COMPLETED! Rewritten query set in state")
        return state
    
    def route_based_on_intent(self, state: State) -> str:
        """
        Conditional routing function to determine next node based on query complexity
        """
        skip_rag = state.get("skip_rag", False)
        user_query = state.get("user_query", "")
        
        if skip_rag:
            logger.info(f"🚀 Routing to SIMPLE query handler for: '{user_query[:30]}...'")
            return "simple"
        else:
            logger.info(f"🔍 Routing to QUERY REWRITER for complex query: '{user_query[:30]}...'")
            return "complex"
    
    def handle_simple_query(self, state: State) -> State:
        """
        Node for handling simple queries with predefined responses
        """
        user_query = state.get("user_query", "")
        simple_response = state.get("simple_response", "")
        conversation_id = state.get("conversation_id", "")
        
        logger.info(f"💬 [HANDLE_SIMPLE_QUERY] Handling simple query with predefined response")
        
        # DEBUG: Log state keys to verify websocket_connection is present
        logger.info(f"💬 [HANDLE_SIMPLE_QUERY] State keys: {list(state.keys())}")
        
        # Check if WebSocket streaming is available
        connection_info = state.get("websocket_connection", {})
        connection_id = connection_info.get("connectionId")
        url = connection_info.get("url")
        
        # DEBUG: Log WebSocket connection details for simple queries
        logger.info(f"💬 [WEBSOCKET DEBUG] Simple query connection info: {connection_info}")
        logger.info(f"💬 [WEBSOCKET DEBUG] Connection ID: {connection_id}")
        logger.info(f"💬 [WEBSOCKET DEBUG] URL: {url}")
        
        if connection_id and url and ENABLE_WEBSOCKET_STREAMING:
            # Send simple response via WebSocket streaming for consistency
            try:
                streaming_handler = WordLevelStreamingHandler(
                    connection_id=connection_id,
                    websocket_url=url,
                    conversation_id=conversation_id,
                    trace_id=conversation_id
                )
                
                # Send start signal
                streaming_handler.send_start_signal()
                
                # Create a streaming response that matches LLM streaming pattern
                mock_streaming_generator = create_mock_streaming_response(simple_response)
                
                # Process streaming response just like LLM responses
                ai_response = streaming_handler.process_word_streaming(mock_streaming_generator)
                
                # Update the simple_response with the streamed result
                simple_response = ai_response
                
                logger.info("✅ Simple response sent via WebSocket streaming")
                
            except Exception as e:
                logger.error(f"❌ Error sending simple response via WebSocket: {e}")
                # Fallback to basic response if streaming fails
                logger.info("📤 Falling back to non-streaming simple response")
        
        # Update state with the response
        state["ai_response"] = simple_response
        state["has_context"] = False  # Simple queries don't use context
        
        logger.info(f"✅ Simple query processed in ~50ms with $0 cost")
        return state
    
    def retrieve_from_knowledge_base(self, state: State) -> State:
        """
        Node 1: Retrieve relevant context from Bedrock Knowledge Base
        """
        logger.info(f"📚 [RETRIEVE_FROM_KB] EXECUTING! Retrieving context from Bedrock Knowledge Base")
        logger.info(f"📚 [RETRIEVE_FROM_KB] State keys: {list(state.keys())}")
        
        # Use rewritten query for optimal retrieval, fallback to original
        retrieval_query = state.get("rewritten_query") or state.get("user_query", "")
        original_query = state.get("user_query", "")
        
        logger.info(f"🔍 [RETRIEVE_FROM_KB] QUERY ANALYSIS:")
        logger.info(f"🔍   Original query: '{original_query}'")
        logger.info(f"🔍   Retrieval query: '{retrieval_query}'")
        logger.info(f"🔍   Query was rewritten: {retrieval_query != original_query}")
        
        if state.get("rewritten_query"):
            logger.info(f"✅ [RETRIEVE_FROM_KB] Using REWRITTEN query for retrieval")
        else:
            logger.warning(f"⚠️ [RETRIEVE_FROM_KB] No rewritten_query found! Using original query")
            logger.warning(f"⚠️ [RETRIEVE_FROM_KB] This suggests rewrite_query_node was SKIPPED!")
        
        # Test specific queries for debugging
        test_queries = [
            "Do you have any information about microsoft?",
            "How to open an incident on microsoft?",
            "Support Windows Microsoft",
            "Windows license support",
            "Support des Licences Windows"
        ]
        
        if retrieval_query.lower() in [q.lower() for q in test_queries]:
            logger.info(f"🔍 ⚠️  DEBUGGING KNOWN PROBLEMATIC QUERY: '{retrieval_query}'")
        context_documents = []
        
        if self.bedrock_agent_client and retrieval_query and KNOWLEDGE_BASE_ID:
            
            try:
                logger.info(f"🔍 Querying Knowledge Base ID: {KNOWLEDGE_BASE_ID}")
                
                # Get environment and vector_db parameters
                env = os.getenv('ENV', 'dev')  # Default to 'dev' if not set
                vector_db = "872051E8-E5C8-4AD1-83A8-ADB347D6C2CC"  # Use KB ID as fallback
                
                # Use helper to get retrieval configuration
                retrieval_config = document_analyzer.get_retrieval_config(retrieval_query, env, vector_db)
                
                logger.info(f"🔍 Using filters - Environment: {env}, Vector DB: {vector_db}")
                logger.info(f"🔍 S3 path filter: s3://docops-kb-{env}/{vector_db}/")
                
                response = self.bedrock_agent_client.retrieve(
                    knowledgeBaseId=KNOWLEDGE_BASE_ID,
                    retrievalQuery={'text': retrieval_query},
                    retrievalConfiguration=retrieval_config
                )
                
                # 🔍 DEBUG: Log detailed Bedrock response
                logger.info(f"🔍 BEDROCK RESPONSE DEBUG:")
                logger.info(f"🔍 Query used: '{retrieval_query}'")
                
                if 'retrievalResults' in response:
                    results = response['retrievalResults']
                    logger.info(f"🔍 Total results returned: {len(results)}")
                    
                    for i, result in enumerate(results[:5]):  # Log first 5 results
                        score = result.get('score', 0)
                        content = result.get('content', {}).get('text', '')[:200]  # First 200 chars
                        location = result.get('location', {})
                        uri = location.get('s3Location', {}).get('uri', 'No URI')
                        
                        logger.info(f"🔍 Result {i+1}: Score={score:.4f}")
                        logger.info(f"🔍   URI: {uri}")
                        logger.info(f"🔍   Content preview: '{content}...'")
                        
                        # Check for French content
                        french_indicators = ['licence', 'support des', 'windows', 'microsoft']
                        has_french = any(indicator in content.lower() for indicator in french_indicators)
                        logger.info(f"🔍   Contains French indicators: {has_french}")
                        logger.info(f"🔍   ---")
                else:
                    logger.warning(f"🔍 No retrievalResults in Bedrock response!")
                    logger.info(f"🔍 Response keys: {list(response.keys())}")
                
                # Use helper to process retrieval results
                context_documents = document_analyzer.process_retrieval_results(response)
                        
            except Exception as e:
                logger.error(f"Error retrieving from Knowledge Base: {e}")
        elif not KNOWLEDGE_BASE_ID:
            logger.warning("⚠️  Knowledge Base retrieval skipped: KNOWLEDGE_BASE_ID not configured")
        elif not retrieval_query:
            logger.warning("⚠️  Knowledge Base retrieval skipped: No query provided")
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
        logger.info("🤖 [GENERATE_CHAT_RESPONSE] Starting response generation")
        
        user_query = state.get("user_query", "")
        context_documents = state.get("context_documents", [])
        conversation_id = state.get("conversation_id", "")
        
        # DEBUG: Log state keys to verify websocket_connection is present
        logger.info(f"🤖 [GENERATE_CHAT_RESPONSE] State keys: {list(state.keys())}")
        
        # Use helper to build context-aware prompt
        system_instructions = get_default_system_instructions()
        prompt = build_context_aware_prompt(
            system_instructions=system_instructions,
            context_documents=context_documents,
            user_query=user_query,
            max_tokens=AZURE_OPENAI_MAX_TOKENS
        )
        
        try:
            if self.chat_model:
                # Create message for the chat model
                messages = [HumanMessage(content=prompt)]
                
                logger.info("🤖 [GENERATE_CHAT_RESPONSE] Starting Azure OpenAI streaming response...")
                
                # Check if WebSocket connection info is available in state
                connection_info = state.get("websocket_connection", {})
                connection_id = connection_info.get("connectionId")
                url = connection_info.get("url")
                
                # DEBUG: Log WebSocket connection details
                logger.info(f"🤖 [WEBSOCKET DEBUG] Connection info: {connection_info}")
                logger.info(f"🤖 [WEBSOCKET DEBUG] Connection ID: {connection_id}")
                logger.info(f"🤖 [WEBSOCKET DEBUG] URL: {url}")
                logger.info(f"🤖 [WEBSOCKET DEBUG] ENABLE_WEBSOCKET_STREAMING: {ENABLE_WEBSOCKET_STREAMING}")
                
                if connection_id and url and ENABLE_WEBSOCKET_STREAMING:
                    # Use WordLevelStreamingHandler for advanced streaming
                    logger.info(f"🤖 [STREAMING] Initializing WordLevelStreamingHandler with connection_id: {connection_id}")
                    
                    streaming_handler = WordLevelStreamingHandler(
                        connection_id=connection_id,
                        websocket_url=url,
                        conversation_id=conversation_id,
                        trace_id=conversation_id
                    )
                    
                    # Send start signal immediately
                    logger.info("🤖 [STREAMING] Sending start signal...")
                    streaming_handler.send_start_signal()
                    
                    # Process streaming response
                    logger.info("🤖 [STREAMING] Starting word-level streaming...")
                    logger.info(f"🤖 [STREAMING] Messages sent to model: {[msg.content[:50] + '...' for msg in messages]}")
                    ai_response = streaming_handler.process_word_streaming(
                        self.chat_model.stream(messages)
                    )
                    logger.info(f"🤖 [STREAMING] Streaming completed. Response length: {len(ai_response)}")
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
        
        # Extract source information from context documents
        sources_info = []
        logger.info(f"Processing {len(context_documents)} context documents for source extraction")

        return state
    
    # Document analysis methods moved to src/helpers/document_analyzer.py
    
    def get_memory_checkpoints(self, thread_id: str):
        """
        Get conversation memory checkpoints for a thread_id (following reference pattern)
        Similar to process_checkpoints in reference code
        """
        try:
            checkpoints = list(self.memory.list({"configurable": {"thread_id": thread_id}}))
            logger.info(f"🧠 [MEMORY] Found {len(checkpoints)} checkpoints for thread_id: {thread_id}")
            return checkpoints
        except Exception as e:
            logger.error(f"❌ [MEMORY] Error retrieving checkpoints: {e}")
            return []
    
    def get_conversation_context(self, thread_id: str) -> str:
        """
        Get conversation context summary for debugging (following reference pattern)
        """
        try:
            checkpoints = self.get_memory_checkpoints(thread_id)
            if not checkpoints:
                return "No conversation history"
                
            # Get the latest checkpoint
            latest_checkpoint = checkpoints[0].checkpoint if checkpoints else None
            if not latest_checkpoint:
                return "No checkpoint data"
                
            messages = latest_checkpoint["channel_values"].get("messages", [])
            if not messages:
                return "No messages in conversation"
                
            context_summary = []
            for msg in messages[-5:]:  # Last 5 messages
                if isinstance(msg, HumanMessage):
                    context_summary.append(f"User: {msg.content[:100]}...")
                elif isinstance(msg, AIMessage):
                    context_summary.append(f"AI: {msg.content[:100]}...")
                    
            return "\n".join(context_summary)
        except Exception as e:
            return f"Error loading context: {e}"
    
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
                "websocket_connection": websocket_connection or {},
                "is_simple_query": False,
                "skip_rag": False,
                "skip_llm": False,
                "simple_response": ""
            }
            
            # Execute the workflow with memory using stream pattern (following reference code)
            thread_id = conversation_id or str(uuid.uuid4())
            logger.info(f"🚀 [WORKFLOW DEBUG] Starting LangGraph execution with memory: thread_id={thread_id}, user_query='{user_query[:30]}...'")
            
            # Load existing conversation context for debugging
            context = self.get_conversation_context(thread_id)
            if context != "No conversation history":
                logger.info(f"🧠 [MEMORY] Previous conversation context:")
                logger.info(f"🧠 [MEMORY] {context}")
            
            # Use stream with thread_id for memory persistence (following reference pattern)
            final_state = None
            for chunk in self.workflow.stream(
                initial_state,  # Use initial_state instead of messages format
                {"configurable": {"thread_id": thread_id}}
            ):
                logger.debug(f"🔄 [MEMORY STREAM] Processing chunk: {list(chunk.keys())}")
                # Get the last node's output as final state
                if chunk:
                    for node_name, node_state in chunk.items():
                        final_state = node_state
            
            # Fallback to invoke if stream didn't return any chunks
            if final_state is None:
                logger.warning("🔄 [MEMORY] Stream returned no chunks, falling back to invoke")
                final_state = self.workflow.invoke(
                    initial_state,
                    {"configurable": {"thread_id": thread_id}}
                )
            
            logger.info(f"✅ [WORKFLOW DEBUG] LangGraph execution completed with memory. Final state keys: {list(final_state.keys())}")
            
            # Update conversation_id to be the thread_id for consistency
            if isinstance(final_state, dict):
                final_state["conversation_id"] = thread_id
            
            # Check if streaming was used by examining WebSocket connection
            streaming_used = bool(
                websocket_connection and 
                websocket_connection.get("connectionId") and 
                websocket_connection.get("url") and
                ENABLE_WEBSOCKET_STREAMING
            )
            
            # Return structured response with memory status
            return {
                "success": True,
                "ai_response": final_state.get("ai_response", ""),
                "context_used": final_state.get("has_context", False),
                "sources_count": len(final_state.get("context_documents", [])),
                "sources_info": final_state.get("sources_info", []),
                "conversation_id": final_state.get("conversation_id", ""),
                "model_used": AZURE_OPENAI_MODEL if not final_state.get("is_simple_query", False) else "rule_based",
                "processing_method": "simple_response" if final_state.get("is_simple_query", False) else "rag_llm",
                "cost_optimized": final_state.get("is_simple_query", False),
                "memory_enabled": True,  # Memory is now enabled following reference pattern
                "thread_id": thread_id,  # Include thread_id for continuation
                "streaming_used": streaming_used,  # Indicate whether streaming was used
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

# Initialize global workflow instance with memory support
bedrock_workflow = BedrockKnowledgeBaseWorkflow()
logger.info(f"🧠 [POST INIT] Initialized workflow with memory checkpointer")

@authenticate_websocket()
# @require_resource_permission('CHATKBBEDROCKCDKWEBSOCKET', 'CREATE')
def start_chat(event, context):
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
        conversation_id = validation_schema['datas'].get('conversationId', str(uuid.uuid4()))
        send_immediate_streaming_signals(connectionId, url, conversation_id)
        
        # Process chat query using LangGraph workflow with Bedrock Knowledge Base
        user_query = validation_schema['datas'].get('query', '')
        vector_db = validation_schema['datas'].get('vectorDb', KNOWLEDGE_BASE_ID)  # Get vector DB parameter
        
        # Extract user email using helper
        user_email = extract_user_email_from_event(event)
        
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
                    # Use helper to build success case data structure
                    validation_schema['datas'] = conversation_builder.build_success_case_data(
                        workflow_result, user_query, user_email
                    )
                    
                    logger.info("✅ [POST HANDLER] LangGraph workflow completed successfully")
                    
                    # Check if streaming was actually used
                    streaming_used = workflow_result.get('streaming_used', False)
                    if streaming_used:
                        logger.info("📡 [POST HANDLER] Streaming response already sent during workflow execution")
                        logger.info("🔄 [POST HANDLER] Skipping duplicate WebSocket response to maintain streaming integrity")
                    else:
                        logger.warning("⚠️ [POST HANDLER] Streaming may have failed - sending fallback WebSocket response")
                        
                        # Send fallback WebSocket response if streaming didn't work
                        websocket_response = conversation_builder.build_websocket_response(
                            user_email=user_email,
                            conversation_id=workflow_result.get('conversation_id', conversation_id),
                            user_query=user_query,
                            ai_response=workflow_result.get('ai_response', ''),
                            sources_info=workflow_result.get('sources_info', []),
                            context_used=workflow_result.get('context_used', False),
                            sources_count=workflow_result.get('sources_count', 0)
                        )
                        
                        final_response = conversation_builder.build_final_websocket_response(websocket_response, 201)
                        send_to_client(connectionId, json.dumps(final_response), url)
                        logger.info("📡 [POST HANDLER] Fallback WebSocket response sent")
                    
                else:
                    # Workflow failed, but continue with regular processing
                    logger.warning(f"LangGraph workflow failed: {workflow_result.get('error', 'Unknown error')}")
                    
                    # Use helper to build failure case data structure
                    validation_schema['datas'] = conversation_builder.build_failure_case_data(
                        user_query=user_query,
                        conversation_id=conversation_id,
                        user_email=user_email
                    )
                    
            except Exception as workflow_err:
                logger.error(f"LangGraph workflow execution error: {workflow_err}")
                
                # Use helper to build error case data structure  
                validation_schema['datas'] = conversation_builder.build_error_case_data(
                    user_query=user_query,
                    conversation_id=conversation_id,
                    user_email=user_email
                )
        else:
            logger.warning("No query provided for AI processing")
            
            # Use helper to build no query case data structure
            validation_schema['datas'] = conversation_builder.build_no_query_case_data(
                conversation_id=conversation_id,
                user_email=user_email
            )

        # Construct the new item to be inserted using helper
        try:
            new_item = conversation_builder.construct_new_dynamodb_item(validation_schema['datas'])
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

    # Send the response to the client only if streaming wasn't already handled
    try:
        # Check if this is a successful workflow response (streaming already handled)
        is_streaming_response = (
            response_result and 
            isinstance(response_result, dict) and 
            response_result.get('success') and
            user_query  # Only if there was a query to process
        )
        
        if not is_streaming_response:
            # Send non-streaming response (errors, validation failures, etc.)
            logger.info("📡 [POST HANDLER] Sending non-streaming response (error/validation)")
            send_to_client(connectionId, json.dumps(construct_response(response_result)), url)
        else:
            logger.info("📡 [POST HANDLER] Skipping final response - streaming already completed")
            
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
    Format exactly as specified with proper conversation structure.
    
    :param datas: The data to be included in the new item.
    :return: A dictionary representing the new item in exact format.
    """
    # Create the item structure exactly as requested
    item = {
        "id": str(uuid.uuid4()),  # Generate a unique ID for the new item
        "conversationId": str(datas.get('conversationId', '')),
        "assistantId": '268f80b4-61f4-470e-bd8d-e6091e09a3cb',
        "title": datas.get('title', ''),
        "createdBy": datas.get('createdBy', ''),
        "updatedBy": datas.get('updatedBy', ''),
        "languageCode": datas.get('languageCode', 'en'),
        "createdAt": datas.get('createdAt', ''),
        "updatedAt": datas.get('updatedAt', ''),
        "isActive": datas.get('isActive', True),
        "iaModel": datas.get('iaModel', ''),
        "chatHistory": datas.get('chatHistory', []),     # Current Q&A pair
        "memoryHistory": datas.get('memoryHistory', []), # Full conversation memory
    }
    
    # Add any additional fields that might be present (like sources, etc.)
    for key, value in datas.items():
        if key not in item:  # Don't override the structured fields above
            item[key] = value
    
    return item

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