# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an AWS CDK Python WebSocket microservice template that provides real-time bidirectional communication through API Gateway WebSocket APIs. The service is deployed using AWS CDK and integrates with Azure API Management for API exposure.

## Coding Conventions

- **Python**: Use snake_case for variables and functions (e.g., `my_var`)
- **JavaScript**: Use camelCase for variables and functions (e.g., `myVar`)
- **Never store secrets in ENV or code** - use AWS Secrets Manager
- Follow SOLID principles for maintainable and scalable code
- Use meaningful variable and function names (avoid `temp`, `data1`, `foo`)
- Keep functions small and focused (single responsibility)
- Document public functions with docstrings (Python) or JSDoc (JavaScript)
- Handle errors properly, never swallow exceptions silently

## Architecture

### Two-Stack Deployment Model

The project uses a **two-stack architecture** that must be deployed in order:

1. **Resources Stack** (`resources/`): Creates foundational AWS resources
   - Main DynamoDB table (configurable name via `TABLE` env var)
   - WebSocket connections tracking table (`{TABLE}-CONNECTIONS`)
   - AWS Secrets Manager secret
   - SQS queue for audit logs with Dead Letter Queue
   - All resources check for existence before creation to avoid conflicts

2. **Lambdas Stack** (`api/`): Deploys Lambda functions and WebSocket API
   - Docker-based Lambda functions deployed via ECR
   - API Gateway WebSocket API with custom routes
   - Lambda functions packaged as Docker images for size optimization

### WebSocket API Routes

The API supports the following WebSocket routes. Note that route names differ from directory names:
- `$connect` - Connection handler with Cognito JWT authentication (in `api/src/connect/handler.py`)
- `$disconnect` - Disconnection handler (in `api/src/disconnect/handler.py`)
- `$default` - Default message handler (in `api/src/default/handler.py`)
- `sendMessage` - Custom message sending (in `api/src/send_message/handler.py`)
- `create` - Create new template (in `api/src/post/handler.py::create`)
- `update` - Update existing template (in `api/src/put/handler.py::edit`)
- `delete` - Delete template (in `api/src/delete/handler.py`)
- `get` - Retrieve single template (in `api/src/get/handler.py`)
- `list` - List/query templates with filtering (in `api/src/list/handler.py`)

Route names are defined in `api/lambdas_stack.py:66-76`.

### Authentication & Authorization

- **Cognito JWT Authentication**: All WebSocket connections require valid JWT tokens
- Token extraction: Tokens can be provided via query parameters (`authorization`) or headers (`Authorization`)
- Connection tracking: Authenticated connections are stored in the CONNECTIONS table with user metadata
- Token storage: JWT tokens are stored with connection info for subsequent message authorization
- Helper modules:
  - `cognito_auth.py` - Token validation and extraction
  - `scope_manager.py` - User permissions management
  - `auth_middleware.py` - Authorization middleware

## Development Commands

### Building and Deployment

The project uses GitLab CI/CD with shared DevOps scripts. Deployment is automated through `.gitlab-ci.yml`:

```bash
# The CI/CD pipeline includes these inherited jobs from shared scripts:
# - deploy_resources_dev/prod: Deploys the resources stack
# - deploy_lambdas_dev/prod: Builds Docker image, pushes to ECR, deploys lambdas stack
```

### Local Development

```bash
# Install Python dependencies (for resources stack)
cd resources
pip install -r requirements.txt

# Install Python dependencies (for API stack)
cd api
pip install -r requirements.txt

# Install Node.js dependencies (for AsyncAPI generation)
cd api
npm install

# Generate AsyncAPI documentation
npm run asyncapi
```

### Testing

Currently, there are no automated tests configured. To add tests:
```bash
# Install pytest for Python
pip install pytest

# Create test files in api/tests/ or resources/tests/
# Run tests with pytest
cd api  # or resources
pytest
```

The `package.json` includes a placeholder test script that can be configured once tests are added.

### CDK Deployment (Manual)

```bash
# Deploy resources stack first
cd resources
export API_NAME="your-api-name"
export API_VERSION="v1"
export TABLE="YOUR_TABLE_NAME"
export SECRET_NAME="YOUR_SECRET_NAME"
export SECRET_VALUE='{"key":"value"}'
export COGNITO_POOL_ID="your-pool-id"
cdk deploy

# Then deploy lambdas stack
cd ../api
export AWS_ECR_FOLDER="your-ecr-repo"
export IMAGE_TAG="latest"
export SERVICE_NAME="YOUR_SERVICE_NAME"
export AWS_ACCOUNT_ID="123456789012"
export SQS_QUEUE_NAME="AUDIT_QUEUE"
export DEAD_LETTER_QUEUE_NAME="AUDIT_DLQ"
export VAR_EXAMPLE="example-value"
cdk deploy
```

### Testing WebSocket Connections

WebSocket connections require authentication:
```
wss://{api-id}.execute-api.{region}.amazonaws.com/{stage}?authorization={jwt-token}
```

## Key Files and Their Purpose

### Configuration Files
- `.gitlab-ci.yml` - CI/CD pipeline configuration, includes shared DevOps scripts from `i2s-ics-do/i2s_ics_do_devops_scripts` project
- `api/cdk.json` - CDK app configuration for lambdas stack
- `resources/cdk.json` - CDK app configuration for resources stack
- `api/requirements.txt` - Python dependencies including CDK constructs and Lambda runtime dependencies
- `resources/requirements.txt` - Python dependencies for resource provisioning

### Infrastructure as Code
- `api/app.py` - CDK app entry point for lambdas, reads env vars and instantiates LambdasStack
- `api/lambdas_stack.py` - Defines all Lambda functions, WebSocket API, routes, and IAM permissions
- `resources/app.py` - CDK app entry point for resources, checks resource existence before creation
- `resources/resources_stack.py` - Defines DynamoDB tables, Secrets Manager, SQS queues

### Lambda Handlers
- `api/src/{route}/handler.py` - WebSocket route handlers (connect, disconnect, default, create, update, delete, get, list, send_message)
- Each handler follows pattern: extract event info → validate → authorize → process → send response via WebSocket

### Helper Modules (api/src/helpers/)
- `cognito_auth.py` - Cognito JWT token validation and user extraction
- `event_utils.py` - Extract connection info and access tokens from WebSocket events
- `api_responses.py` - Standardized HTTP response construction
- `construct_response.py` - WebSocket response formatting with JSON Content-Type
- `schema_validation.py` - Request data validation against JSON schemas
- `scope_manager.py` - User authorization and permission management
- `auth_middleware.py` - Authentication decorator for WebSocket handlers with group/scope checking
  - Use `@authenticate_websocket()` decorator to protect handlers
  - Supports `required_groups` and `required_scopes` parameters
  - Helper functions: `get_authenticated_user()`, `get_user_email()`, `has_scope()`, `has_resource_permission()`, etc.
- `queue_helper.py` - SQS audit queue operations
- `get_secret.py` - AWS Secrets Manager retrieval
- `decimal_converter.py` - Convert DynamoDB Decimal objects to JSON-serializable types
- `model.py` - AsyncAPI schema definitions for Template data model
- `asyncapi.js` - Node.js script to generate AsyncAPI documentation from Python docstrings

### Deployment Integration
- `api/src/terraform/main.tf` - Terraform configuration for Azure API Management integration
- Uploads AsyncAPI documentation to Azure Storage
- Creates WebSocket API in Azure API Management

## Important Patterns

### Lambda Environment Variables
All Lambda functions receive these environment variables (set in `lambdas_stack.py`):
- `TABLE` - Main DynamoDB table name
- `CONNECTIONS_TABLE` - WebSocket connections table name
- `REGION` - AWS region
- `COGNITO_POOL_ID` - Cognito User Pool ID for JWT validation
- `SERVICE_NAME` - Service identifier
- `AWS_ACCOUNT_ID` - AWS account ID
- `SQS_QUEUE_NAME` - Audit queue name
- `DEAD_LETTER_QUEUE_NAME` - DLQ name
- `WEBSOCKET_ENDPOINT_URL` - WebSocket API endpoint for posting messages to connections
- `VAR_EXAMPLE` - Example custom variable

### WebSocket Message Flow
1. Client connects with JWT token → `connect` handler validates & stores connection
2. Client sends message with route key → corresponding handler processes message
3. Handler uses `apigatewaymanagementapi` to post response back to connection
4. Client disconnects → `disconnect` handler cleans up connection from DynamoDB

### Error Handling Pattern
All handlers can follow this pattern, optionally using the authentication decorator:
```python
from src.helpers.auth_middleware import authenticate_websocket, get_user_email

# Option 1: Using authentication decorator (recommended)
@authenticate_websocket(required_scopes=['TEMPLATE:CREATE'])
def create(event, context):
    try:
        # Validate request schema
        validation = validate_request_datas_schema(action, datas)
        if not validation['success']:
            return error_response

        # Get authenticated user (added by decorator)
        user_email = get_user_email(event)

        # Process business logic
        result = process_data(...)

        # Send response via WebSocket
        send_to_client(url, connectionId, response)

    except ClientError as e:
        logger.error(...)
        return error_response

# Option 2: Manual authorization (legacy approach)
def handler(event, context):
    try:
        # Validate request schema
        validation = validate_request_datas_schema(action, datas)
        if not validation['success']:
            return error_response

        # Check authorization manually
        user_email = check_authorization(event)

        # Process business logic
        result = process_data(...)

        # Send response via WebSocket
        send_to_client(url, connectionId, response)

    except ClientError as e:
        logger.error(...)
        return error_response
```

### Audit Logging
Use `queue_helper.py` to send audit events to SQS:
```python
from src.helpers.queue_helper import send_to_audit_queue

send_to_audit_queue({
    'action': 'CREATE',
    'resource': 'template',
    'user': user_email,
    'timestamp': time.time()
})
```

## AsyncAPI Documentation

The project uses AsyncAPI 2.x for WebSocket API documentation:
- Schema definitions in `api/src/helpers/model.py`
- Generation script: `api/src/helpers/asyncapi.js`
- Output: `api/src/api/asyncapi.json`
- Run `npm run asyncapi` to regenerate documentation
- Documentation is automatically uploaded to Azure Storage during deployment

## Security Notes

- Never commit secrets - use AWS Secrets Manager (accessed via `SECRET_NAME` env var)
- JWT tokens are validated using Cognito JWKS
- All DynamoDB operations use IAM role permissions (no hardcoded credentials)
- WebSocket connections without valid tokens return 403/401 and are rejected
- Connection tracking table has TTL enabled for automatic cleanup
- Secrets Manager secrets use `RemovalPolicy.RETAIN` to prevent accidental deletion

## CI/CD Pipeline

The `.gitlab-ci.yml` includes shared pipeline definitions from `i2s-ics-do/i2s_ics_do_devops_scripts:2.0.0`:
- AI-powered code review on merge requests
- Automated testing
- Docker image building with Kaniko and ECR push
- Resources deployment (DynamoDB, Secrets, SQS)
- Lambda deployment with CDK
- Terraform execution for Azure API Management
- AsyncAPI documentation generation and upload
- Separate dev/prod environments with manual approval for production

## Environment Variables Reference

Required environment variables for deployment:
- `API_NAME` - API identifier
- `API_VERSION` - API version (e.g., v1, v10)
- `API_PRODUCT` - Azure APIM product name
- `TABLE` - DynamoDB table name
- `SECRET_NAME` - Secrets Manager secret name
- `SECRET_VALUE` - Secret value (JSON string)
- `COGNITO_POOL_ID` - Cognito User Pool ID
- `SERVICE_NAME` - Service identifier
- `AWS_ACCOUNT_ID` - AWS account ID
- `AWS_ECR_FOLDER` - ECR repository name
- `IMAGE_TAG` - Docker image tag (default: latest)
- `VAR_EXAMPLE` - Example application variable
