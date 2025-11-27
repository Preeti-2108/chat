"""
Langfuse tracing helpers for structured, readable traces
"""
import os
import datetime
import logging
from langfuse import Langfuse

logger = logging.getLogger(__name__)

# Initialize Langfuse client
langfuse = Langfuse(
    public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
    secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
    host=os.getenv("LANGFUSE_HOST"),
)

def create_clean_trace(session_id, name, handler_name, metadata=None, user_id=None):
    """
    Create a clean, structured Langfuse trace with consistent metadata
    """
    default_metadata = {
        "handler": handler_name,
        "timestamp": datetime.datetime.utcnow().isoformat(),
        "environment": os.getenv("ENV", "dev"),
        "api_version": "v1",
        "request_type": "api_request"
    }
    if metadata:
        default_metadata.update(metadata)
    trace_kwargs = {
        "session_id": session_id,
        "name": name,
        "metadata": default_metadata,
    }
    if user_id:
        trace_kwargs["user_id"] = user_id
    return langfuse.create(**trace_kwargs)

def update_trace_input(trace, **kwargs):
    """
    Update trace with clean, structured input data
    """
    try:
        input_data = {
            "timestamp": datetime.datetime.utcnow().isoformat()
        }
        input_data.update(kwargs)
        trace.update(input=input_data)
    except Exception as e:
        logger.warning(f"Failed to update trace input: {str(e)}")

def update_trace_input_structured(trace, query=None, internal_response=None, external_response=None, chat_history=None, max_iterations=None, **kwargs):
    """
    Update trace with structured input data separating query, responses, and sources
    """
    try:
        input_data = {
            "timestamp": datetime.datetime.utcnow().isoformat()
        }
        if query is not None:
            input_data["query"] = query
        if internal_response is not None:
            input_data["internal_response"] = internal_response
        if external_response is not None:
            input_data["external_response"] = external_response
        if chat_history is not None:
            input_data["chat_history"] = chat_history
        if max_iterations is not None:
            input_data["max_iterations"] = max_iterations
        input_data.update(kwargs)
        trace.update(input=input_data)
        logger.info("Updated trace with structured input data")
    except Exception as e:
        logger.warning(f"Failed to update trace with structured input: {str(e)}")
        try:
            update_trace_input(trace, **kwargs)
        except Exception:
            pass

def update_trace_output(trace, response_data=None, status="success", **kwargs):
    """
    Update trace with clean, structured output data
    """
    try:
        output_data = {
            "status": status,
            "timestamp": datetime.datetime.utcnow().isoformat()
        }
        if response_data is not None:
            if isinstance(response_data, dict):
                if "chatHistory" in response_data:
                    output_data["chatHistory"] = response_data["chatHistory"]
                    chat_history = response_data["chatHistory"]
                    if chat_history and len(chat_history) > 0:
                        last_message = chat_history[-1]
                        if isinstance(last_message, dict) and "aiAssistant" in last_message:
                            output_data["aiResponse"] = last_message["aiAssistant"]
                else:
                    output_data.update(response_data)
            else:
                output_data["response"] = str(response_data)
        output_data.update(kwargs)
        trace.update(output=output_data)
    except Exception as e:
        logger.warning(f"Failed to update trace output: {str(e)}")
        try:
            trace.update(output={"status": status, "timestamp": datetime.datetime.utcnow().isoformat()})
        except Exception:
            pass

def update_trace_error(trace, error_type, error_message, **kwargs):
    """
    Update trace with clean error information
    """
    try:
        error_data = {
            "status": "error",
            "error_type": error_type,
            "error_message": error_message,
            "timestamp": datetime.datetime.utcnow().isoformat()
        }
        error_data.update(kwargs)
        trace.update(output=error_data)
    except Exception as e:
        logger.warning(f"Failed to update trace with error: {str(e)}")

def create_structured_response_data(response_text, sources=None, status=200, error=False):
    """
    Create structured response data for internal/external KB responses
    """
    return {
        "response": response_text,
        "sources": sources or [],
        "status": status,
        "error": error
    }

def parse_combined_user_msg(user_msg_string):
    """
    Parse a combined user_msg string into structured components
    """
    try:
        return {
            "query": "Parsed query from user_msg",
            "internal_response": {
                "response": "Parsed internal response",
                "sources": [],
                "status": 200,
                "error": False
            },
            "external_response": {
                "response": "Parsed external response", 
                "sources": [],
                "status": 200,
                "error": False
            }
        }
    except Exception as e:
        logger.warning(f"Failed to parse user_msg: {str(e)}")
        return None

def flush_trace(trace):
    """
    Flush the trace to ensure it's sent to Langfuse
    """
    try:
        langfuse.flush()
    except Exception as e:
        logger.warning(f"Failed to flush trace: {str(e)}")

def create_websocket_trace(session_id, conversation_id=None, user_id=None):
    """Create a trace for WebSocket chat operations"""
    metadata = {"request_type": "websocket_chat"}
    if conversation_id:
        metadata["conversationId"] = conversation_id
    return create_clean_trace(
        session_id=session_id,
        name="Post Chat - Bedrock KB (Create)",
        handler_name="post_chat_handler",
        metadata=metadata,
        user_id=user_id
    )

def create_query_trace(session_id):
    """Create a trace for query operations"""
    return create_clean_trace(
        session_id=session_id,
        name="Internal KB -Bedrock Query API",
        handler_name="query API",
        metadata={"request_type": "query"}
    )

def create_update_trace(session_id, conversation_id=None):
    """Create a trace for update operations"""
    metadata = {"request_type": "update"}
    if conversation_id:
        metadata["conversationId"] = conversation_id
    return create_clean_trace(
        session_id=session_id,
        name="Update Chat - Bedrock KB",
        handler_name="put_chat API",
        metadata=metadata
    )
