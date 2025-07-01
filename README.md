# AWS Microservice [Name of the service]

## Introduction

### Architecture diagram

![Architecture](architecture.drawio.svg)

### File structure

#### Rules:
- Never store secrets in ENV or code, use AWS Secret Manager.
- Coding conventions:
- Python: Use snake_case (e.g., ma_var).
- JavaScript: Use camelCase (e.g., maVar).
- Follow the SOLID principles for maintainable and scalable code.
- Use environment variables for configuration, but never for secrets.
- Write unit tests for critical functionalities.
- Use meaningful variable and function names (no temp, data1, foo).
- Keep functions small and focused (single responsibility).
- Always lint and format your code (e.g., ESLint, Prettier for JS, Black for Python).
- Document public functions and APIs (Docstrings for Python, JSDoc for JavaScript).
- Handle errors properly, never swallow exceptions silently.
- Use dependency management (requirements.txt or pipenv for Python, package.json for JavaScript).
- Log useful information, but avoid logging sensitive data.

#### 📂 Project - File Structure

The microservice contains two directories:

- **api**: Contains all the code for business logic, this directory provides AWS Lambda & Gateway.

- **resources**: Contains all the necessary resources to provide in AWS (DynamoDb, Secret Manager, Bucket, ...).

- **root directory**: Contains serverless compose for deploying api & resources, gitlab-ci.yml for CI/CD pipeline, architecture.svg.drawio to give a view of the architecture of the microservice.

```yaml
/:
  - README.md
  - architecture.drawio.svg
api/:
  - Dockerfile
  - app.py
  - cdk.json
  - lambdas_stack.py
  - package.json
  - requirements.txt
  src/:
    api/:
      - asyncapi.json
      - policies.xml
    connect/:
      - handler.py
    default/:
      - handler.py
    delete/:
      - handler.py
    disconnect/:
      - handler.py
    get/:
      - handler.py
    handler_websocket/:
      - handler.py
    helpers/:
      - api_responses.py
      - asyncapi.js
      - check_authorization.py
      - construct_response.py
      - event_utils.py
      - get_secret.py
      - model.py
      - schema_validation.py
    list/:
      - handler.py
    post/:
      - handler.py
    put/:
      - handler.py
    send_message/:
      - handler.py
    terraform/:
      - main.tf
resources/:
  - app.py
  - cdk.json
  - requirements.txt
  - resources_stack.py
```

## Service configuration

### Resources service

This service is responsible for managing AWS resources for an application. The resources include a DynamoDB table and/or a Secrets Manager secret.

#### Resources configuration

The configuration for the service is defined in the custom section of the serverless.yml file. Here are the key configuration options:

- **owner**: The team owning the MCO about the microservice.
- **application**: The application or solution why this microservice is created.
- **customer**: The number of the agency for billing purposes.
- **tableName**: The name of the DynamoDB table.
- **secretName**: The name of the Secrets Manager secret.

#### AWS Resources

The AWS resources for the service are defined in the resources section of the serverless.yml file. Here are the key resources:

- **Table**: A DynamoDB table with a single attribute `id` as the hash key. The table name, deletion policy, and point-in-time recovery settings can be customized based on the environment (dev or prod).
- **Secret**: A Secrets Manager secret that stores sensitive information for the microservice.

#### Outputs

The Outputs section provides the ARN and name of the DynamoDB table, and the ID and name of the Secrets Manager secret. These outputs can be used in other AWS resources or in AWS IAM policies.

### Api service

This service is designed for creating microservices on AWS using the Serverless Framework. It includes configuration for AWS resources such as VPC, IAM, API Gateway, and environment variables.

#### Api configuration

The configuration for the service is defined in the `custom` section of the `serverless.yml` files. Here are the key configuration options:

- **owner**, **application**, and **customer**: These are customizable fields that specify the team owning the microservice, the application for which the microservice is created, and the agency number for billing purposes.
- **vpcConfigurationSg** and **vpcConfigurationSubnets**: With these values, we deploy the MS in our VPC, in specific subnets, for accessing AWS resources in our tenant.
- **deploymentBucketMap**: This maps the deployment bucket names for different environments (dev and prod) to environment variables.
- **logLevelMap** and **logRetentionMap**: These map the log level and log retention settings for different environments (dev and prod) to environment variables.

### Api resources configuration

The AWS resources for the service are defined in the `provider` section of the `serverless.yml` files. Here are the key resources:

- **vpc**: This specifies the VPC configuration for the service, including the security group IDs and subnet IDs.
- **apiGateway**: This specifies the API Gateway configuration for the service, including the resource policy.
- **environment**: This specifies the environment variables for the service, including the DynamoDB table name, AWS region, and Cognito user pool ID.
- **iam**: This specifies the IAM role for the service, including permissions for Cognito, DynamoDB, and Secrets Manager.

### Functions

The `functions` section of the `serverless.yml` file defines the AWS Lambda functions for the service. Each function has a handler, an HTTP event trigger, and an authorizer.

## Function codes

### 📌 Documentation for `connect\handler.py`

# Serverless Connection Handler

## Overview

This script is designed for serverless applications, specifically to handle connection events. It is typically used in environments such as AWS Lambda, where it can be triggered by an event like an API Gateway request. The primary purpose of this script is to establish a connection and return a successful HTTP response.

## Main Functionalities

- **Event Handling**: The script is triggered by an event, which is usually an API Gateway request in a serverless architecture.
- **Connection Establishment**: It processes the event to establish a connection.
- **HTTP Response**: Returns a successful HTTP response with a status code and a message body indicating a successful connection.

## How to Use

### Prerequisites

- Ensure you have a serverless environment set up, such as AWS Lambda.
- The script should be integrated with an API Gateway or similar service that can trigger the function.

### Function Parameters

- **event (dict)**: This parameter contains information about the triggering event. It includes request parameters and headers that are necessary for processing the connection.
  
- **context (object)**: This parameter provides runtime information about the function execution. It includes details such as the function name and memory limits, which can be useful for logging and monitoring purposes.

### Execution Steps

1. **Trigger the Function**: The function is triggered by an event, typically an API Gateway request. Ensure that the event contains the necessary information in the form of a dictionary.

2. **Process the Event**: The function processes the event to establish a connection. This involves interpreting the event data and preparing a response.

3. **Return HTTP Response**: The function returns a dictionary representing an HTTP response. This response includes:
   - `statusCode`: An HTTP status code of 200, indicating a successful request.
   - `body`: A message body with the text "Connected", confirming the connection status.

### Integration

- Integrate this function with your serverless application by deploying it to a platform like AWS Lambda.
- Configure the API Gateway or equivalent service to trigger this function upon receiving a connection request.

## Additional Information

For detailed examples and further documentation, please refer to the Swagger documentation associated with this script. This will provide comprehensive examples and additional context for integrating and using the function within your serverless architecture.

### 📌 Documentation for `default\handler.py`

# Default Route AWS Lambda Function

## Overview

This script is designed to handle the default route for an AWS Lambda function. It serves as a fallback or catch-all route when no other specific route matches an incoming request. The function returns a simple HTTP response with a status code of 200 and a message indicating that the default route has been accessed.

## Main Functionalities

- **Fallback Route Handling**: The function acts as a default handler for requests that do not match any other predefined routes in your AWS Lambda setup.
- **HTTP Response Generation**: It generates a basic HTTP response with a status code of 200, indicating a successful request, and a body message stating "Default route".

## How to Use

This function is intended to be deployed as part of an AWS Lambda setup. It is typically used in conjunction with AWS API Gateway or other routing mechanisms that direct unmatched requests to this default handler.

### Deployment Steps

1. **Create an AWS Lambda Function**: 
   - Log in to your AWS Management Console.
   - Navigate to the AWS Lambda service.
   - Create a new Lambda function and choose the appropriate runtime (Python).

2. **Configure the Function**:
   - Copy the provided script into the Lambda function code editor.
   - Set up any necessary permissions and environment variables.

3. **Set Up API Gateway (Optional)**:
   - If using AWS API Gateway, configure a new API or update an existing one to route unmatched requests to this Lambda function.

4. **Test the Function**:
   - Use the AWS Lambda console to test the function with events.
   - Verify that the function returns a response with a status code of 200 and the message "Default route".

### Function Parameters

- **event (dict)**: Contains information about the invoking event, such as request data and headers.
- **context (object)**: Provides runtime information to the handler, including function name and memory limit.

### Return Value

- The function returns a dictionary representing an HTTP response:
  - `statusCode`: An integer (200) indicating a successful HTTP request.
  - `body`: A string message ("Default route") included in the response body.

## Additional Information

For detailed examples and further configuration options, please refer to the Swagger documentation associated with your API setup. This will provide specific use cases and integration details tailored to your environment.

### 📌 Documentation for `delete\handler.py`

# Template Deletion Script

## Overview

This script is designed to handle the deletion of templates stored in an AWS DynamoDB table. It is implemented in Python and leverages AWS services to manage and delete template data based on incoming event requests. The script is intended to be used in a serverless environment, such as AWS Lambda, and communicates with clients via WebSocket.

## Main Functionalities

- **Event Handling**: Processes incoming events to extract necessary information for template deletion.
- **DynamoDB Interaction**: Connects to a DynamoDB table to check for the existence of a template and delete it if found.
- **Schema Validation**: Validates incoming requests against a predefined schema to ensure data integrity.
- **WebSocket Communication**: Sends responses back to the client using WebSocket, providing real-time feedback on the operation's success or failure.
- **Logging**: Logs various stages of the process for debugging and monitoring purposes.

## Usage

### Prerequisites

- **AWS Credentials**: Ensure that your environment is configured with the necessary AWS credentials to access DynamoDB.
- **Environment Variables**: Set the following environment variables:
  - `TABLE`: The name of the DynamoDB table.
  - `LOG_LEVEL`: The desired logging level (e.g., `INFO`, `DEBUG`).

### Execution

1. **Event Trigger**: The script is triggered by an event, typically from an AWS Lambda function. The event should contain the necessary data for processing, including the template ID to be deleted.

2. **Extract Event Information**: The script extracts the WebSocket URL and connection ID from the event to facilitate communication with the client.

3. **Request Validation**: The script checks if the template ID is provided in the request body. If not, it responds with an error message indicating that the ID parameter is required.

4. **Schema Validation**: The request is validated against a predefined schema. If validation fails, an error response is sent back to the client.

5. **DynamoDB Operations**:
   - **Check Existence**: The script checks if the template with the specified ID exists in the DynamoDB table.
   - **Delete Template**: If the template exists, it is deleted from the table. If not, a not-found error is returned.

6. **Error Handling**: The script handles potential errors, such as DynamoDB client errors or unexpected exceptions, and logs them for further analysis.

7. **Response Construction**: A response is constructed based on the operation's outcome and sent back to the client via WebSocket.

### Logging

The script uses Python's logging module to log information and errors. The log level can be configured through the `LOG_LEVEL` environment variable.

### Swagger Documentation

For detailed API specifications and examples, please refer to the Swagger documentation associated with this script. The Swagger documentation provides comprehensive details on the API endpoints, request/response formats, and usage examples.

## Conclusion

This script provides a robust solution for managing template deletions in a serverless environment, ensuring efficient communication with clients and maintaining data integrity through schema validation. By leveraging AWS services, it offers a scalable and reliable approach to template management.

### 📌 Documentation for `disconnect\handler.py`

# Disconnect Function Documentation

## Overview

The `disconnect` function is a serverless event handler designed to manage client disconnections in a WebSocket or similar connection environment. It is typically deployed in a serverless architecture, such as AWS Lambda, and is triggered when a client disconnects from the server.

## Purpose

The primary purpose of this function is to handle disconnection events efficiently and provide a standardized response indicating the success of the disconnection process. This is crucial in maintaining the integrity and performance of applications that rely on real-time communication channels.

## Main Functionalities

- **Event Handling**: The function is triggered by a disconnection event, which includes details such as the connection ID and other relevant metadata.
- **Context Awareness**: It utilizes the context parameter to access runtime information about the Lambda function execution, such as function name, memory limit, and request ID.
- **Response Generation**: The function returns a response object with a status code and a message body. A status code of 200 indicates a successful HTTP response, and the message body confirms the disconnection.

## How to Use

### Deployment

1. **Environment**: Ensure that your environment supports serverless functions, such as AWS Lambda.
2. **Configuration**: Configure your serverless setup to trigger this function upon a client disconnection event. This typically involves setting up a WebSocket API or similar service that can detect and forward disconnection events to the function.

### Execution

- **Event Parameter**: The function receives an `event` parameter, which is a dictionary containing information about the disconnection event. This may include:
  - Connection ID
  - Metadata related to the disconnection

- **Context Parameter**: The `context` parameter provides runtime information about the function execution. This includes:
  - Function name
  - Memory limit
  - Request ID

### Response

Upon execution, the function returns a dictionary with the following structure:

- **statusCode**: An integer representing the HTTP status code. A value of 200 indicates a successful disconnection.
- **body**: A string message confirming the disconnection, typically "Disconnected".

## Additional Information

For detailed examples and further configuration options, please refer to the Swagger documentation associated with your serverless setup. This documentation will provide specific examples and use cases tailored to your deployment environment.

### 📌 Documentation for `get\handler.py`

# Template Retrieval Service

## Overview

This script is designed to handle the retrieval of template items from an AWS DynamoDB table via WebSocket events. It processes incoming requests, validates the data, interacts with DynamoDB to fetch the requested item, and communicates the results back to the client through a WebSocket connection.

## Main Functionalities

- **WebSocket Event Handling**: Listens for incoming WebSocket events and processes them.
- **Data Validation**: Validates incoming request data against a predefined schema to ensure correctness.
- **DynamoDB Interaction**: Retrieves items from a specified DynamoDB table using the provided ID.
- **Response Construction**: Constructs appropriate responses based on the outcome of the operation.
- **WebSocket Communication**: Sends responses back to the client over the WebSocket connection.

## How to Use

### Prerequisites

- **AWS Credentials**: Ensure that your environment is configured with the necessary AWS credentials to access DynamoDB.
- **Environment Variables**: Set the following environment variables:
  - `TABLE`: The name of the DynamoDB table.
  - `LOG_LEVEL`: The logging level (e.g., `INFO`, `DEBUG`).

### Execution Flow

1. **Event Reception**: The script begins by receiving an event from a WebSocket connection. This event contains the request details.

2. **Logging**: The event is logged for debugging purposes, and an entry log is created to indicate the start of the `get` function.

3. **DynamoDB Resource Initialization**: A DynamoDB resource is initialized, and the table specified in the environment variables is accessed.

4. **Event Information Extraction**: The script extracts necessary information from the event, such as the URL and connection ID.

5. **Request Body Parsing**: The script retrieves and parses the request body to extract the `id` parameter.

6. **ID Validation**: If the `id` parameter is missing, an error response is sent to the client, and the function exits.

7. **Schema Validation**: The request data is validated against a predefined schema. If validation fails, an error response is sent to the client.

8. **DynamoDB Query**: The script attempts to retrieve the item from DynamoDB using the provided ID. It handles any client errors that may occur during this process.

9. **Response Construction**: Based on whether the item is found or not, the script constructs an appropriate response.

10. **WebSocket Response**: The final response is sent back to the client over the WebSocket connection.

11. **Completion**: The function returns a status code and a message indicating the result of the operation.

### Error Handling

- **Client Errors**: Errors related to DynamoDB client operations are logged and handled gracefully.
- **BotoCore Errors**: General errors from the BotoCore library are logged and managed to ensure the script continues to function.

### Logging

The script uses Python's logging module to log messages at various levels (e.g., DEBUG, INFO, ERROR) to aid in monitoring and debugging.

## Additional Information

For detailed request and response examples, please refer to the Swagger documentation associated with this service.

### 📌 Documentation for `handler_websocket\handler.py`

# WebSocket Connection Management Script

## Overview

This script is designed to manage WebSocket connections using AWS services. It handles client connections, disconnections, and message processing through AWS API Gateway and DynamoDB. The script also validates JWT access tokens using AWS Cognito to ensure secure communication.

## Main Functionalities

1. **JWT Validation**: Validates JWT access tokens using AWS Cognito's JSON Web Key Set (JWKS).
2. **Connection Management**: Handles new WebSocket connections and stores connection details in DynamoDB.
3. **Disconnection Handling**: Manages client disconnections and removes connection details from DynamoDB.
4. **Message Processing**: Receives and processes messages from WebSocket clients, echoing them back to the sender.
5. **Message Sending**: Sends messages to specific WebSocket connections using the API Gateway Management API.

## Environment Configuration

Before using the script, ensure the following environment variables are set:

- `TABLE_NAME`: The name of the DynamoDB table for storing WebSocket connection details.
- `COGNITO_POOL_ID`: The Cognito User Pool ID for JWT validation.
- `REGION`: The AWS region for service endpoints.
- `WEBSOCKET_ENDPOINT_URL`: The WebSocket endpoint URL for sending messages.

## Usage

### 1. Validate Access Token

The `validate_access_token` function checks the validity of a JWT access token using the Cognito User Pool's JWKS. It returns the token's scope if valid.

### 2. Connect

The `connect` function handles new WebSocket connections. It:

- Extracts the access token from query parameters.
- Validates the token and retrieves its scope.
- Stores the connection ID and scope in DynamoDB.

### 3. Disconnect

The `disconnect` function manages client disconnections by:

- Removing the connection details from DynamoDB using the connection ID.

### 4. Default Message

The `defaultMessage` function processes incoming messages by:

- Parsing the message body.
- Echoing the message back to the client.

### 5. Send to Client

The `send_to_client` function sends messages to a specific WebSocket connection using the API Gateway Management API.

## Logging

The script uses Python's logging module to log debug and error messages, aiding in monitoring and troubleshooting.

## Error Handling

The script includes error handling for:

- Invalid or missing JWT tokens.
- DynamoDB operations.
- WebSocket message sending failures.

For detailed API usage and examples, refer to the Swagger documentation.

### 📌 Documentation for `helpers\api_responses.py`

# Responses Utility Class

## Overview

The `Responses` class is a utility designed to facilitate the creation of standardized HTTP response objects in a JSON format. This class is particularly useful for web applications and APIs where consistent response structures are crucial for client-server communication.

## Purpose

The primary purpose of the `Responses` class is to provide a simple and efficient way to generate HTTP responses with customizable status codes, success indicators, messages, and data payloads. This ensures that all responses from your application are uniform and easy to interpret by clients.

## Main Functionalities

The `Responses` class offers two main static methods:

1. **_define_response**: 
   - Constructs a basic HTTP response structure.
   - Allows specification of the HTTP status code and the data payload.
   - Returns a dictionary representing the HTTP response with headers, status code, and JSON body.

2. **result_response**:
   - Builds upon `_define_response` to include additional details such as success status and a message.
   - Provides a more detailed response structure, including a success flag and a message for better client understanding.
   - Returns a dictionary representing the HTTP response with headers, status code, and JSON body.

## How to Use

### _define_response Method

- **Purpose**: To create a basic HTTP response.
- **Parameters**:
  - `status_code` (int): The HTTP status code for the response. Defaults to 502.
  - `data` (dict): The payload to be included in the response body. Defaults to an empty dictionary.
- **Returns**: A dictionary with the response structure including headers, status code, and JSON body.

### result_response Method

- **Purpose**: To create a detailed HTTP response with success status and message.
- **Parameters**:
  - `status_code` (int): The HTTP status code for the response. Defaults to 502.
  - `success` (bool): Indicates whether the operation was successful. Defaults to False.
  - `message` (str): A message providing additional information about the response. Defaults to an empty string.
  - `data` (dict): The payload to be included in the response body. Defaults to an empty dictionary.
- **Returns**: A dictionary with the response structure including headers, status code, and JSON body.

## Usage

To use the `Responses` class, simply call the static methods with the desired parameters to generate the appropriate HTTP response. The methods are designed to be flexible, allowing you to specify only the parameters you need, with sensible defaults provided for all parameters.

For detailed examples and further usage instructions, please refer to the Swagger documentation associated with this utility class.

### 📌 Documentation for `helpers\asyncapi.js`

# AsyncAPI Document Generator

## Overview

This script is designed to generate an AsyncAPI document from Python source files. It scans through a specified directory, extracts AsyncAPI annotations from Python files, and compiles them into a structured AsyncAPI document. The generated document is then saved as a JSON file, which can be used for API documentation and integration purposes.

## Main Functionalities

1. **Directory Scanning**: The script recursively scans a specified directory for Python files (`.py`).

2. **Annotation Extraction**: It extracts AsyncAPI annotations from block comments within the Python files.

3. **YAML Parsing**: The extracted annotations, written in YAML format, are parsed into JavaScript objects.

4. **Document Compilation**: The script compiles the extracted data into a complete AsyncAPI document, including channels and components.

5. **File Output**: The final AsyncAPI document is written to a JSON file for further use.

## How to Use

### Prerequisites

- Ensure Node.js is installed on your system.
- The script requires the following Node.js modules:
  - `fs` for file system operations.
  - `path` for handling file paths.
  - `js-yaml` for parsing YAML content.

### Steps to Execute

1. **Setup**: Ensure your project directory contains the necessary Python files with AsyncAPI annotations.

2. **Run the Script**: Execute the script using Node.js. The script will start scanning from the default directory `./src` unless specified otherwise.

   ```bash
   node path/to/your/script.js
   ```

3. **Output**: Upon successful execution, the script generates an `asyncapi.json` file in the `../api/` directory relative to the script's location.

### Customization

- **Base Directory**: You can specify a different base directory by passing it as an argument to the `generateAsyncAPIDocument` function.

- **AsyncAPI Definition**: Modify the `asyncapiDefinition` object to customize the base structure of your AsyncAPI document, such as version, title, and contact information.

### Error Handling

- The script includes error handling for file reading and writing operations. Errors are logged to the console for troubleshooting.

## Contact

For support or inquiries, please contact API Support at [support.dps.fr.api.contact@soprasteria.com](mailto:support.dps.fr.api.contact@soprasteria.com).

## License

This project is licensed under the terms of your chosen license. Please include the license details here.

### 📌 Documentation for `helpers\check_authorization.py`

# Authorization Token Validator

## Overview

This script is designed to validate authorization tokens from incoming events, extract user information, and verify the user's AWS account using AWS Cognito if necessary. It is particularly useful in serverless environments where authentication and authorization are managed through tokens.

## Main Functionalities

- **Token Validation**: The script checks for the presence of an authorization token in the event headers and decodes it to extract user information.
- **User Identification**: It retrieves the user ID from the token payload, prioritizing the email field. If the email is not available, it attempts to use the client ID.
- **AWS Cognito Verification**: If necessary, the script interacts with AWS Cognito to verify the user's identity using the client ID and retrieves the client name as the user ID.

## Usage

### Prerequisites

- Ensure that the environment variable `COGNITO_POOL_ID` is set with your AWS Cognito User Pool ID.
- AWS credentials must be configured to allow access to AWS Cognito services.

### Steps

1. **Event Input**: The script expects an event dictionary containing headers with an authorization token. The token should be in the format `Bearer <token>`.

2. **Authorization Header Retrieval**: The script retrieves the authorization header from the event. If the header is missing, it raises a `BadRequest` error with a 401 status code.

3. **Token Decoding**: The script decodes the token without verifying the signature to extract the payload. If the token is invalid, a `BadRequest` error is raised.

4. **User ID Extraction**:
   - The script first attempts to extract the user email from the token payload.
   - If the email is not present, it looks for the `client_id`.
   - If both are missing, a `BadRequest` error is raised with a 400 status code.

5. **AWS Cognito Interaction**:
   - If the `client_id` is used, the script retrieves the Cognito User Pool ID from the environment variables.
   - It initializes a Cognito Identity Provider client and describes the user pool client to get the client name.
   - The client name is then used as the user ID.

6. **Return User ID**: The script returns the determined user ID, which can be used for further processing or authorization checks.

## Error Handling

- **Missing Authorization Token**: Raises a `BadRequest` error with a 401 status code.
- **Invalid Token**: Raises a `BadRequest` error with a 401 status code.
- **Missing Email and Client ID**: Raises a `BadRequest` error with a 400 status code.

## Additional Information

For detailed examples and further documentation, please refer to the Swagger documentation associated with this script. This will provide specific use cases and example payloads for testing and integration.

### 📌 Documentation for `helpers\construct_response.py`

# Construct Response Script

## Overview

The `construct_response` script is a utility function written in Python designed to standardize the format of HTTP responses. It is particularly useful in web applications or APIs where consistent response structures are crucial for client-server communication. This script ensures that the response includes a status code, a body, and appropriate headers, specifically setting the `Content-Type` to `application/json`.

## Main Functionalities

- **Response Standardization**: The script takes a result dictionary as input and constructs a well-defined HTTP response.
- **JSON Content-Type Header**: Automatically sets the `Content-Type` header to `application/json`, ensuring that the response body is interpreted correctly by clients expecting JSON data.

## How to Use

### Input

The function `construct_response` expects a single argument:

- `result`: A dictionary containing the following keys:
  - `status_code`: An integer representing the HTTP status code of the response.
  - `body`: The content of the response, typically a JSON-serializable object.

### Output

The function returns a dictionary with the following structure:

- `status_code`: Mirrors the status code provided in the input.
- `body`: Contains the response body as provided in the input.
- `headers`: A dictionary with a single key-value pair:
  - `Content-Type`: Set to `application/json`.

### Usage

To use the `construct_response` function, ensure that you have a dictionary with the required keys (`status_code` and `body`). Pass this dictionary to the function, and it will return a standardized response dictionary.

### Example

For detailed examples and usage scenarios, please refer to the Swagger documentation associated with this script.

## Conclusion

The `construct_response` script is a simple yet effective tool for creating consistent HTTP responses in Python applications. By ensuring that all responses include a status code, body, and JSON content-type header, it helps maintain a uniform communication protocol between servers and clients.

### 📌 Documentation for `helpers\event_utils.py`

# Extract Event Info Script

## Overview

This script is designed to interact with AWS services, specifically AWS API Gateway and DynamoDB, to extract and manage connection information. It is implemented in Python using the Boto3 library, which is the Amazon Web Services (AWS) SDK for Python. The primary function of this script is to extract essential information from an AWS API Gateway event and retrieve an access token associated with a connection ID from a DynamoDB table.

## Main Functionalities

1. **Initialize AWS Resources**: 
   - The script initializes a DynamoDB resource using Boto3, allowing it to interact with DynamoDB tables.

2. **Extract Event Information**:
   - The script defines a function `extract_event_info(event)` that processes an event from AWS API Gateway.
   - It extracts the domain name, stage, and connection ID from the event's request context.
   - Constructs a URL using the domain name and stage if both are available.

3. **Retrieve Access Token**:
   - If a connection ID is present, the script attempts to retrieve an associated access token from a DynamoDB table.
   - It queries the DynamoDB table specified by the environment variable `TABLE_NAME` to fetch the access token.

4. **Error Handling**:
   - The script includes error handling to manage exceptions that may occur during the retrieval of the access token from DynamoDB.

## How to Use

### Prerequisites

- **AWS Credentials**: Ensure that your AWS credentials are configured properly to allow access to DynamoDB and API Gateway.
- **Environment Variable**: Set the environment variable `TABLE_NAME` to the name of your DynamoDB table that stores connection information.

### Steps

1. **Setup Environment**:
   - Ensure that Python and Boto3 are installed in your environment.
   - Set the `TABLE_NAME` environment variable to point to your DynamoDB table.

2. **Invoke the Function**:
   - The function `extract_event_info(event)` should be called with an event dictionary that contains the request context from AWS API Gateway.
   - The function will return a dictionary containing:
     - `url`: The constructed URL using the domain name and stage.
     - `connectionId`: The connection ID extracted from the event.
     - `access_token`: The access token retrieved from DynamoDB, if available.

3. **Handle Output**:
   - Use the returned dictionary to access the URL, connection ID, and access token for further processing in your application.

### Error Handling

- The script logs an error message if there is an issue retrieving the access token from DynamoDB. Ensure that your DynamoDB table is correctly configured and accessible.

## Additional Information

For detailed examples and further documentation, please refer to the Swagger documentation associated with this script. This will provide comprehensive examples of how to structure the event input and interpret the output effectively.

### 📌 Documentation for `helpers\get_secret.py`

# AWS Secrets Manager Retrieval Script

## Overview

This script is designed to interact with AWS Secrets Manager to securely retrieve secret values. It is implemented in Python and utilizes the `boto3` library to communicate with AWS services. The script is particularly useful for applications that require access to sensitive information, such as API keys or database credentials, stored in AWS Secrets Manager.

## Main Functionalities

- **Environment Configuration**: The script reads the AWS region and secret name from environment variables, ensuring flexibility and ease of deployment across different environments.
- **Secret Retrieval**: It fetches secrets from AWS Secrets Manager, handling both string and binary formats.
- **Error Handling**: The script includes basic error handling to manage exceptions that may occur during the retrieval process.

## How to Use

### Prerequisites

- **AWS Credentials**: Ensure that your environment is configured with the necessary AWS credentials to access Secrets Manager. This can be done via AWS CLI configuration or environment variables.
- **Environment Variables**: Set the following environment variables:
  - `REGION`: The AWS region where your secrets are stored.
  - `SECRET_NAME`: The default name of the secret to retrieve if no specific name is provided to the function.

### Steps

1. **Set Up Environment**: Configure your environment with the required AWS credentials and environment variables (`REGION` and `SECRET_NAME`).

2. **Initialize the Script**: The script automatically initializes a `boto3` client for AWS Secrets Manager using the specified region from the environment variable.

3. **Retrieve a Secret**:
   - Call the `get_secret` function with an optional `secret_name` argument.
   - If `secret_name` is not provided, the function will use the `SECRET_NAME` environment variable.
   - The function will attempt to retrieve the secret value from AWS Secrets Manager.

4. **Handle the Output**:
   - If the secret is stored as a JSON string, the function returns it as a Python dictionary.
   - If the secret is stored in binary format, it is decoded and returned as a string.
   - In case of an error during retrieval, the function returns the exception object.

### Function Details

- **`get_secret(secret_name=None)`**:
  - **Purpose**: Fetches a secret from AWS Secrets Manager.
  - **Parameters**: 
    - `secret_name` (optional): The name of the secret to retrieve. Defaults to the `SECRET_NAME` environment variable if not provided.
  - **Returns**: 
    - A dictionary if the secret is a JSON string.
    - A decoded string if the secret is binary.
    - An exception object if an error occurs.

## Additional Information

For detailed examples and further documentation, please refer to the Swagger documentation associated with this script. This will provide comprehensive usage scenarios and additional configuration options.

### 📌 Documentation for `helpers\schema_validation.py`

# README

## Overview

This script is designed to validate request data structures and content based on specified actions such as `POST`, `PUT`, `DELETE`, and `GET`. It ensures that the data adheres to a predefined JSON schema, which includes checks for UUID and date-time formats. This validation is crucial for maintaining data integrity and consistency in applications that handle structured data.

## Main Functionalities

- **Action-Based Validation**: The script validates data based on the action type (`POST`, `PUT`, `DELETE`, `GET`).
- **Schema Definition**: A JSON schema is defined to specify the expected structure and data types for the request data.
- **Custom Format Checking**: Custom checks for UUID and date-time formats are implemented to ensure data validity.
- **Data Normalization**: String data is normalized by converting to uppercase and removing accents.
- **Error Reporting**: Provides detailed error messages when validation fails.

## How to Use

### Prerequisites

Ensure that you have the following Python libraries installed:

- `uuid`
- `dateutil`
- `jsonschema`
- `unidecode`

You can install these libraries using pip:

```bash
pip install python-dateutil jsonschema unidecode
```

### Usage

1. **Import the Function**: Import the `validate_request_datas_schema` function into your Python script.

2. **Prepare Your Data**: Structure your data as a dictionary. Ensure that the keys and values align with the expected schema.

3. **Call the Function**: Use the function by passing the action type and the data dictionary as arguments.

   ```python
   result = validate_request_datas_schema('POST', your_data_dictionary)
   ```

4. **Handle the Result**: The function returns a dictionary indicating the success of the validation. If validation fails, it includes error messages.

### Action-Specific Details

- **POST/PUT**: Requires `templateCompany` and `templateAgent` fields. Converts string booleans to actual booleans and normalizes string data.
- **DELETE**: Requires an `id` field. Validates the presence and format of the `id`.
- **GET**: Validates the data against the schema without additional processing.

### Error Handling

- The function returns a `success` key with a boolean value indicating the validation result.
- If validation fails, a `message` key provides detailed error information.

## Conclusion

This script is a robust solution for validating structured data in applications that require strict adherence to data formats. By using this script, developers can ensure that their applications handle data consistently and reliably. For detailed examples and further documentation, please refer to the Swagger documentation associated with this script.

### 📌 Documentation for `list\handler.py`

# Template List Retrieval Script

## Overview

This script is designed to handle the retrieval of template data from an AWS DynamoDB table. It processes incoming events, validates requests, constructs query parameters, and formats responses to be sent back to clients via WebSocket. The script is particularly useful for applications that require dynamic querying and filtering of template data based on various criteria.

## Main Functionalities

- **Event Handling**: Processes incoming events to extract necessary information and query parameters.
- **Request Validation**: Validates the incoming request data against predefined schemas to ensure data integrity.
- **DynamoDB Interaction**: Constructs and executes scan operations on a DynamoDB table to retrieve template data.
- **Response Construction**: Formats and constructs responses based on the retrieved data and sends them back to the client.
- **Logging**: Provides detailed logging for debugging and monitoring purposes.

## How to Use

### Prerequisites

- **AWS Credentials**: Ensure that your environment is configured with the necessary AWS credentials to access DynamoDB.
- **Environment Variables**: Set the following environment variables:
  - `TABLE`: The name of the DynamoDB table.
  - `LOG_LEVEL`: The desired log level (e.g., `INFO`, `DEBUG`).

### Event Structure

The script expects an event structure that includes:

- `body`: Contains the `datas` and `action` fields.
  - `datas`: Query parameters for filtering the templates.
  - `action`: The action to be performed, used for validation.

### Functions

1. **list(event, context)**
   - Main function to handle the listing of templates.
   - Extracts event information, validates requests, constructs query parameters, and formats the response.
   - Sends the response back to the client via WebSocket.

2. **construct_params(datas)**
   - Constructs parameters for the DynamoDB scan operation based on the provided query parameters.
   - Builds filter expressions and attribute mappings for querying the table.

3. **format_results(items, datas)**
   - Formats the results from the DynamoDB scan based on offset and limit for pagination.
   - Returns a dictionary containing the formatted list of items and their count.

4. **remove_accents(input_str)**
   - Removes accents from the input string using the `unidecode` library.
   - Returns the unaccented version of the input string.

### Logging

The script uses Python's `logging` module to log events and errors. The log level can be configured via the `LOG_LEVEL` environment variable.

### Error Handling

The script includes error handling to manage exceptions that may occur during processing. It returns appropriate HTTP status codes and error messages in the response.

### Swagger Documentation

For detailed examples and further API documentation, please refer to the Swagger documentation associated with this script. The Swagger documentation provides comprehensive details on the API endpoints, request/response structures, and example payloads.

### 📌 Documentation for `post\handler.py`

# README

## Overview

This script is designed to handle the creation of new items in a DynamoDB table through an AWS Lambda function. It processes incoming events, validates request data, checks authorization, constructs the item, and inserts it into the database. Additionally, it manages error handling and sends responses back to the client via WebSocket.

## Main Functionalities

- **Event Processing**: The script listens for incoming events that trigger the creation of new items.
- **Data Validation**: It validates the request data against a predefined schema to ensure data integrity.
- **Authorization**: The script checks if the request is authorized before proceeding with item creation.
- **Item Construction**: It constructs a new item with a unique identifier and necessary metadata.
- **Database Interaction**: The script inserts the constructed item into a DynamoDB table.
- **Error Handling**: It manages errors during data validation, authorization, and database operations.
- **WebSocket Communication**: The script sends responses back to the client using WebSocket.

## Usage

### Prerequisites

- **AWS Account**: Ensure you have an AWS account with permissions to access DynamoDB and Lambda.
- **Environment Variables**: Set the necessary environment variables, such as `TABLE` for the DynamoDB table name and `LOG_LEVEL` for logging configuration.

### Steps to Use

1. **Event Trigger**: The script is triggered by an event, typically from an API Gateway or another AWS service.
   
2. **Extract Event Information**: The `extract_event_info` function extracts necessary information from the event, such as the URL and connection ID.

3. **Parse Event Body**: The script parses the body of the event to retrieve the action and data payload.

4. **Validate Data**: The `validate_request_datas_schema` function checks the data against a predefined schema. If validation fails, an error response is sent to the client.

5. **Check Authorization**: The `check_authorization` function verifies if the request is authorized. It also adds metadata such as `createdBy` and `updatedBy` to the data.

6. **Construct New Item**: The `construct_new_item` function creates a new item with a unique ID and prepares it for database insertion.

7. **Insert into DynamoDB**: The script attempts to insert the new item into the specified DynamoDB table. If successful, a success response is sent to the client.

8. **Error Handling**: If any errors occur during the process, appropriate error messages are logged, and an error response is sent to the client.

9. **Send Response**: The `send_to_client` function sends the constructed response back to the client via WebSocket.

### Logging

- The script uses Python's `logging` module to log information at various levels (DEBUG, INFO, ERROR). The log level can be configured using the `LOG_LEVEL` environment variable.

### Swagger Documentation

For detailed API specifications, including request and response examples, refer to the Swagger documentation provided with the project.

## Conclusion

This script provides a robust solution for handling item creation in a DynamoDB table, with built-in validation, authorization, and error handling mechanisms. It is designed to be used in an AWS Lambda environment, leveraging AWS services for seamless integration and scalability.

### 📌 Documentation for `put\handler.py`

# Template Update WebSocket Handler

## Overview

This script is designed to handle WebSocket requests for updating templates stored in a DynamoDB table. It processes incoming WebSocket events, validates the request data, checks authorization, and updates the specified template. The script also sends a response back to the client via WebSocket.

## Main Functionalities

- **WebSocket Event Handling**: Listens for WebSocket events to update templates.
- **Data Validation**: Validates incoming request data against a predefined schema.
- **Authorization Check**: Verifies if the request is authorized.
- **DynamoDB Update**: Updates the template in the DynamoDB table.
- **Response Construction**: Constructs and sends a response back to the client.

## How to Use

### Prerequisites

- Ensure you have AWS credentials configured for accessing DynamoDB.
- Set the environment variable `TABLE` to the name of your DynamoDB table.
- Set the environment variable `LOG_LEVEL` to control logging verbosity (e.g., `INFO`, `DEBUG`).

### Steps

1. **Initialize Logger**: The script initializes a logger to capture logs at the level specified by the `LOG_LEVEL` environment variable.

2. **Handle WebSocket Event**: The `edit` function is the main entry point for handling WebSocket events. It takes `event` and `context` as parameters.

3. **Extract Event Information**: The script extracts necessary information such as `url` and `connectionId` from the event using the `extract_event_info` helper.

4. **Parse and Validate Request**: 
   - Parses the JSON payload from the WebSocket message.
   - Validates the request data using `validate_request_datas_schema`.

5. **Check Authorization**: Uses the `check_authorization` helper to verify the user's authorization and retrieve their email.

6. **Generate Update Expression**: Constructs a DynamoDB update expression using the `generate_update_query` function, ensuring the `updatedAt` field is set to the current timestamp.

7. **Update DynamoDB**: 
   - Checks if the item exists in the DynamoDB table.
   - Updates the item if it exists, or returns a not found response if it doesn't.

8. **Send Response**: Constructs a response using `construct_response` and sends it back to the client via WebSocket using `send_to_client`.

### Error Handling

- Logs errors and constructs an error response if any exceptions occur during the update process.

## Swagger Documentation

For detailed API specifications, including request and response examples, refer to the Swagger documentation provided with the project.

## Conclusion

This script provides a robust solution for handling WebSocket requests to update templates in a DynamoDB table, ensuring data validation, authorization, and efficient response handling.

### 📌 Documentation for `send_message\handler.py`

# Send Message Function

## Overview

The `send_message` function is a serverless function designed to handle the sending of messages triggered by various events. It is typically used in cloud environments where functions are invoked in response to specific triggers, such as HTTP requests or messages from a queue. The primary purpose of this function is to process incoming event data and return a response indicating the success of the message sending operation.

## Main Functionalities

- **Event Handling**: The function is triggered by an event, which could be an HTTP request or a message from a queue. It processes the event data to perform its operations.
- **Response Generation**: After processing the event, the function returns a response with an HTTP status code and a message body. The status code indicates the success of the operation, and the body provides a confirmation message.

## How to Use

### Parameters

- **event (dict)**: This parameter is a dictionary containing the event data. It may include various details such as the message content, sender information, or other relevant metadata required for processing the event.
  
- **context (object)**: This parameter provides runtime information about the function execution. It includes details such as the execution environment, request ID, or timeout settings, which can be useful for debugging or logging purposes.

### Return Value

The function returns a dictionary with the following structure:

- **statusCode (int)**: An HTTP status code indicating the result of the operation. A status code of `200` signifies that the message was successfully sent.
  
- **body (str)**: A confirmation message for the client, typically stating "Message sent" to indicate successful processing.

### Execution Flow

1. **Trigger**: The function is invoked by an event, such as an HTTP request or a message from a queue.
2. **Processing**: The function processes the event data. This step involves interpreting the event details and preparing a response.
3. **Response**: The function returns a response with a status code of `200` and a body message confirming the successful sending of the message.

## Additional Information

For detailed examples and further documentation, please refer to the Swagger documentation associated with this function. The Swagger documentation provides comprehensive examples and additional context for using this function in various scenarios.


## Deployment DEVSECOPS

This project uses a comprehensive CI/CD pipeline configured with GitLab CI for automated testing, building, and deployment to both development and production environments.

### Pipeline Overview
The pipeline consists of the following stages:
- **`analysis`**: Code analysis (PR review using AI agent)
- **`prepare`**: Environment preparation
- **`test`**: Testing
- **`set_variables`**: Environment-specific variable configuration
- **`build`** *(optional)*: Docker image building (used only if the global Serverless project exceeds 250 MB)
- **`deploy`**: Deployment to AWS and Azure environments
- **`dependency_scanning`**: Scanning for vulnerabilities in project dependencies

### AI-Powered Code Reviews
Our pipeline integrates an artificial intelligence system that performs automated code reviews on pull requests. This AI agent analyzes the code based on Secure Software Development Guidelines (SSG) standards, ensuring that all code changes adhere to industry best practices for security, performance, and maintainability.

#### The AI review system:
- Identifies potential security vulnerabilities
- Checks for code quality and adherence to established patterns
- Validates compliance with architectural standards
- Suggests optimizations based on known best practices
- Provides feedback directly in the merge request

### Key Components

#### PR Analysis
The pipeline includes an AI-powered code review agent for merge requests that helps identify potential issues before merging.

#### Testing
All code changes undergo automated testing to ensure quality and stability:
- Dependencies installation
- Automated tests execution

#### Environment Configuration
The pipeline automatically configures the appropriate environment variables based on the target environment (development or production):
- AWS credentials and configuration
- Cognito authentication settings
- API Gateway parameters
- Terraform variables
- Azure API Management credentials

#### Docker Image Building
Docker images are built using Kaniko and pushed to AWS ECR:
- Images are tagged as `appimage`
- Common package dependencies are included during the build process
- Build process scales according to the overall project size, with larger projects potentially requiring additional optimization and parallel build processes
- *Note: This step is optional and used only if the global Serverless project exceeds 250 MB*

#### Infrastructure as Code
The deployment process leverages:
- Serverless Framework for AWS resource provisioning
- Terraform for additional infrastructure management
- Automated Swagger API documentation generation and import into Azure API Management

### Deployment Environments

#### Development Environment
- Triggered automatically for:
  - `develop` branch
  - Merge requests
- Deploys to AWS development account
- Configures API in Azure API Management development instance

#### Production Environment
- Triggered for `main` or `master` branches
- Requires manual approval for deployment
- Deploys to AWS production account
- Configures API in Azure API Management production instance

### Security Considerations

- All sensitive information is stored as GitLab CI/CD variables
- Different credentials are used for development and production environments
- Service principals with appropriate permissions for Azure resources
- AWS IAM credentials with least privilege access

### Prerequisites

To use this pipeline, ensure the following environment variables are configured in GitLab CI/CD settings:
- AWS credentials for both environments
- Azure service principal credentials
- Cognito configuration parameters
- Common package version variables
- Terraform configuration values