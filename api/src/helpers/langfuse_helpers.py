"""
Langfuse tracing helpers for structured, readable traces
"""
import os
import datetime
import logging
try:
    from langfuse import Langfuse, Trace
except ImportError:
    Langfuse = None
    Trace = None

logger = logging.getLogger(__name__)

# Initialize Langfuse client only if keys are present
LANGFUSE_PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY")
LANGFUSE_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY")
LANGFUSE_HOST = os.getenv("LANGFUSE_HOST")
LANGFUSE_ENVIRONMENT = os.getenv("LANGFUSE_ENVIRONMENT")

print(f"LANGFUSE_PUBLIC_KEY: {LANGFUSE_PUBLIC_KEY}****")
print(f"LANGFUSE_HOST: {LANGFUSE_HOST}+++")
print(f"LANGFUSE_ENVIRONMENT: {LANGFUSE_ENVIRONMENT}---")
print(f"LANGFUSE_SECRET_KEY: {LANGFUSE_SECRET_KEY}^^^^^^^^")

langfuse = None
if LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY and LANGFUSE_HOST:
    langfuse = Langfuse(
        public_key=LANGFUSE_PUBLIC_KEY,
        secret_key=LANGFUSE_SECRET_KEY,
        host=LANGFUSE_HOST,
    )
else:
    logger.warning("Langfuse client not initialized: missing keys or host.")

# --- Minimal Trace Creation ---
def create_langfuse_trace(session_id, name="Chat Trace", handler_name="chat_handler", metadata=None, user_id=None):
    """
    Create a Langfuse trace using the Trace class directly.
    """
    if not langfuse or not Trace:
        logger.warning("Langfuse not available, trace will not be created.")
        return None
    try:
        trace = Trace(
            langfuse,
            session_id=session_id,
            name=name,
            metadata=metadata or {},
            user_id=user_id,
        )
        # Add handler info to metadata
        trace.metadata["handler"] = handler_name
        trace.metadata["timestamp"] = datetime.datetime.utcnow().isoformat()
        trace.metadata["environment"] = os.getenv("ENV", "dev")
        trace.metadata["api_version"] = "v1"
        return trace
    except Exception as e:
        logger.error(f"Failed to create Langfuse trace: {e}")
        return None

# --- Minimal Trace Update ---
def update_langfuse_trace_input(trace, **kwargs):
    if not trace:
        return
    try:
        input_data = {"timestamp": datetime.datetime.utcnow().isoformat()}
        input_data.update(kwargs)
        trace.update(input=input_data)
    except Exception as e:
        logger.warning(f"Failed to update Langfuse trace input: {e}")

def update_langfuse_trace_output(trace, **kwargs):
    if not trace:
        return
    try:
        output_data = {"timestamp": datetime.datetime.utcnow().isoformat()}
        output_data.update(kwargs)
        trace.update(output=output_data)
    except Exception as e:
        logger.warning(f"Failed to update Langfuse trace output: {e}")

def flush_langfuse_trace(trace):
    if not langfuse or not trace:
        return
    try:
        langfuse.flush()
    except Exception as e:
        logger.warning(f"Failed to flush Langfuse trace: {e}")

# --- Usage Example ---
# trace = create_langfuse_trace(session_id)
# update_langfuse_trace_input(trace, query="hello")
# update_langfuse_trace_output(trace, response="world")
# flush_langfuse_trace(trace)
