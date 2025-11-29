# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an **Internal Knowledge Base Chatbot** built on AWS CDK, providing a RAG (Retrieval-Augmented Generation) chat assistant via WebSocket API. The service combines:
- **AWS Bedrock Knowledge Base** for document retrieval
- **Azure OpenAI (GPT-4o)** for response generation via LangChain/LangGraph
- **Real-time word-level streaming** to WebSocket clients
- **Cognito JWT authentication** for secure access

The DynamoDB table `CONVERSATION_INTERNALKB_HISTORY` stores conversation history for multi-turn chat support.

## Coding Conventions

- **Python**: Use snake_case for variables and functions (e.g., `my_var`)
- **JavaScript**: Use camelCase for variables and functions (e.g., `myVar`)
- **Never store secrets in ENV or code** - use AWS Secrets Manager
- Follow SOLID principles for maintainable and scalable code
- Document public functions with docstrings (Python) or JSDoc (JavaScript)
- Handle errors properly, never swallow exceptions silently

## Architecture

### Two-Stack Deployment Model

Deploy in order:

1. **Resources Stack** (`resources/`): Creates foundational AWS resources
   - Main DynamoDB table (`CONVERSATION_INTERNALKB_HISTORY`)
   - WebSocket connections tracking table (`{TABLE}-CONNECTIONS`)
   - AWS Secrets Manager secret
   - SQS queue for audit logs with Dead Letter Queue

2. **Lambdas Stack** (`api/`): Deploys Lambda functions and WebSocket API
   - Docker-based Lambda functions deployed via ECR
   - API Gateway WebSocket API with custom routes
   - IAM permissions for Bedrock Knowledge Base access

### RAG Chat Flow

```
User Query → Query Rewriting → Bedrock KB Retrieval → Context Building → Azure OpenAI → Streaming Response
```

1. **Intent Detection** (`intent_detector.py`): Simple queries (greetings, thanks) bypass RAG for speed
2. **Query Rewriting** (`query_rewriter.py`): Expands user queries with synonyms and domain terminology
3. **Bedrock Retrieval** (`bedrock_tuner.py`): Retrieves relevant documents from Knowledge Base
4. **Document Analysis** (`document_analyzer.py`): Builds context-aware prompts with source citations
5. **LangGraph Workflow** (`post/handler.py`): Orchestrates the RAG pipeline with state management
6. **Streaming** (`streaming_handler.py`): Word-level streaming to WebSocket clients

### WebSocket API Routes

Route names defined in `api/lambdas_stack.py:80-89`:
- `$connect` - Connection handler with Cognito JWT auth (`api/src/connect/handler.py`)
- `$disconnect` - Disconnection handler (`api/src/disconnect/handler.py`)
- `$default` - Fallback for unmatched routes (`api/src/default/handler.py`)
- `create` - **Start new chat conversation** (`api/src/post/handler.py::start_chat`)
- `update` - **Continue existing conversation** (`api/src/put/handler.py::continue_chat`)
- `delete` - Delete conversation (`api/src/delete/handler.py`)
- `get` - Retrieve conversation (`api/src/get/handler.py`)
- `list` - List conversations (`api/src/list/handler.py`)
- `sendMessage` - Generic message sending (`api/src/send_message/handler.py`)

### Authentication & Authorization

- **Cognito JWT Authentication**: All WebSocket connections require valid JWT tokens
- Token extraction via query parameters (`authorization`) or headers (`Authorization`)
- Connection tracking in DynamoDB with user metadata
- Helper modules: `cognito_auth.py`, `scope_manager.py`, `auth_middleware.py`

## Development Commands

### Local Development

```bash
# Install Python dependencies (for API stack)
cd api
pip install -r requirements.txt

# Install Node.js dependencies (for AsyncAPI generation)
npm install

# Generate AsyncAPI documentation
npm run asyncapi
```

### Testing

No automated tests configured yet. To add tests:
```bash
pip install pytest
cd api
pytest
```

### CDK Deployment (Manual)

```bash
# Deploy resources stack first
cd resources
export TABLE="CONVERSATION_INTERNALKB_HISTORY"
export SECRET_NAME="SLS-CHATINTERNALKBBEDROCKWEBSOCKET"
cdk deploy

# Then deploy lambdas stack
cd ../api
export AWS_ECR_FOLDER="cdk-chat-internal-kb-bedrock-websocket-v10"
export KNOWLEDGE_BASE_ID="your-kb-id"
export AZURE_OPENAI_API_KEY="your-key"
cdk deploy
```

## Key Files

### Core Chat Handlers
- `api/src/post/handler.py` - **Main entry point**: `start_chat()` creates new conversations with RAG workflow
- `api/src/put/handler.py` - `continue_chat()` handles follow-up messages with conversation history

### RAG Pipeline Helpers (api/src/helpers/)
- `query_rewriter.py` - Expands queries with synonyms and domain terminology for better retrieval
- `bedrock_tuner.py` - Configures and executes Bedrock Knowledge Base retrieval
- `document_analyzer.py` - Analyzes retrieved documents, builds context prompts, extracts citations
- `intent_detector.py` - Detects simple queries (greetings) to bypass expensive RAG calls
- `streaming_handler.py` - `WordLevelStreamingHandler` for real-time word-by-word delivery
- `conversation_builder.py` - Builds conversation history for multi-turn context
- `system_instructions.py` - Default system prompts and error response templates

### Infrastructure
- `api/lambdas_stack.py` - Defines Lambda functions, WebSocket API, IAM permissions (including Bedrock)
- `resources/resources_stack.py` - DynamoDB tables, Secrets Manager, SQS queues

### Auth & Utilities
- `auth_middleware.py` - `@authenticate_websocket()` decorator for handler protection
- `cognito_auth.py` - JWT token validation using Cognito JWKS
- `event_utils.py` - Extract connection info and access tokens from WebSocket events
- `decimal_converter.py` - Convert DynamoDB Decimal to JSON-serializable types

## Lambda Environment Variables

Set in `lambdas_stack.py`:
- `TABLE` - Main DynamoDB table name (`CONVERSATION_INTERNALKB_HISTORY`)
- `CONNECTIONS_TABLE` - WebSocket connections table
- `REGION` - AWS region
- `COGNITO_POOL_ID` - Cognito User Pool ID for JWT validation
- `KNOWLEDGE_BASE_ID` - AWS Bedrock Knowledge Base ID
- `AZURE_OPENAI_API_ENDPOINT` - Azure OpenAI endpoint path
- `AZURE_OPENAI_MODEL` - Model name (e.g., `gpt-4o`)
- `AZURE_OPENAI_API_VERSION` - API version
- `AZURE_OPENAI_API_KEY` - Azure OpenAI API key
- `AZURE_OPENAI_TEMPERATURE` - Model temperature (default: 0.2)
- `AZURE_OPENAI_MAX_TOKENS` - Max tokens (default: 4000)
- `BASE_URL` - Base URL for Azure OpenAI service
- `WEBSOCKET_ENDPOINT_URL` - WebSocket API endpoint for sending responses

## Important Patterns

### RAG Workflow with LangGraph

The main chat workflow in `post/handler.py` uses LangGraph for state management:

```python
from langgraph.graph import StateGraph, END
from langchain_openai import AzureChatOpenAI

class BedrockKnowledgeBaseWorkflow:
    def __init__(self, knowledge_base_id, streaming_handler):
        self.llm = AzureChatOpenAI(...)
        self.graph = self._build_graph()

    def _build_graph(self):
        # Nodes: retrieve_docs → analyze_context → generate_response
        workflow = StateGraph(ConversationState)
        ...
```

### Streaming Response Pattern

```python
from src.helpers.streaming_handler import WordLevelStreamingHandler

handler = WordLevelStreamingHandler(connection_id, websocket_url, conversation_id)
handler.send_streaming_chunk(chunk, is_final=False)
handler.send_streaming_chunk(final_text, is_final=True)
```

### Query Rewriting for Better Retrieval

```python
from src.helpers.query_rewriter import rewrite_query_for_better_similarity

expanded_queries = rewrite_query_for_better_similarity(user_query)
# Returns multiple variations for better semantic matching
```

## CI/CD Pipeline

The `.gitlab-ci.yml` includes shared pipeline definitions from `i2s-ics-do/i2s_ics_do_devops_scripts:2.0.0`:
- AI-powered code review on merge requests
- Docker image building with Kaniko and ECR push
- Resources deployment (DynamoDB, Secrets, SQS)
- Lambda deployment with CDK
- Terraform execution for Azure API Management
- Separate dev/prod environments with manual approval for production

## Security Notes

- Never commit secrets - use AWS Secrets Manager
- JWT tokens validated using Cognito JWKS
- Azure OpenAI API key stored in GitLab CI/CD variables (should migrate to Secrets Manager)
- All DynamoDB/Bedrock operations use IAM role permissions
- WebSocket connections without valid tokens return 401/403
