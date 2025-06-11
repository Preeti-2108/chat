# AWS Microservice Python Template CDK

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
  - app.py
  - cdk.json
  - lambdas_stack.py
  - package.json
  - requirements.txt
  src/:
    api/:
      - policies.xml
      - swagger.json
    delete/:
      - handler.py
    get/:
      - handler.py
    helpers/:
      - api_responses.py
      - check_authorization.py
      - construct_response.py
      - get_secret.py
      - model.py
      - schema_validation.py
      - swagger.js
    list/:
      - handler.py
    post/:
      - handler.py
    put/:
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

### 📌 Documentation for `delete\handler.py`

# Template Deletion API - README

## Overview

This script provides a serverless function designed to handle the deletion of templates stored in an AWS DynamoDB table. The function is triggered via an HTTP DELETE request to a specified API endpoint, which is documented using Swagger (OpenAPI). The primary purpose of this script is to facilitate the removal of a template identified by a unique ID, ensuring secure and efficient data management.

## Main Functionalities

- **Delete Template by ID**: The script processes HTTP DELETE requests to remove a template from the DynamoDB table using its unique identifier.
- **Error Handling**: Implements comprehensive error handling to manage various scenarios, including validation errors, item not found, and unexpected exceptions.
- **Logging**: Utilizes Python's logging module to provide detailed logs for debugging and monitoring purposes.

## How to Use

### Prerequisites

- **AWS Credentials**: Ensure that your environment is configured with the necessary AWS credentials to access DynamoDB.
- **Environment Variables**: Set the following environment variables:
  - `TABLE`: The name of the DynamoDB table.
  - `LOG_LEVEL`: The desired logging level (e.g., INFO, DEBUG).

### API Endpoint

- **Endpoint**: `/{id}`
- **Method**: DELETE
- **Parameters**:
  - `id` (path parameter): The unique identifier of the template to be deleted.
  - `Authorization` (header): Access token required for authentication.

### Response Codes

- **200 OK**: Template successfully deleted.
- **404 Not Found**: Template with the specified ID does not exist.
- **422 Unprocessable Entity**: Validation errors occurred.
- **500 Internal Server Error**: An unexpected error occurred during execution.

### Execution Flow

1. **Logging Configuration**: The script initializes a logger to capture debug and informational messages.
2. **Event Handling**: The `delete` function is triggered by an HTTP DELETE request, receiving `event` and `context` as parameters.
3. **Parameter Extraction**: Extracts the template ID from the path parameters.
4. **Schema Validation**: Validates the request body schema based on the HTTP method and parameters.
5. **DynamoDB Interaction**:
   - Attempts to retrieve the item from the DynamoDB table using the provided ID.
   - If the item exists, it proceeds to delete it.
6. **Response Construction**: Constructs a structured HTTP response based on the operation's outcome, using helper functions for consistency.

### Error Handling

- **ClientError**: Catches and logs errors related to AWS service interactions.
- **General Exceptions**: Catches any unexpected exceptions, ensuring the function returns a 500 status code with an error message.

### Logging

- Logs the incoming event and key steps within the function to aid in debugging and operational monitoring.

For detailed API usage and examples, please refer to the Swagger documentation associated with this script.

### 📌 Documentation for `get\handler.py`

# Template Retrieval Service

## Overview

This script is designed to handle HTTP GET requests to retrieve a single template by its ID from an AWS DynamoDB table. It is part of a larger API service that provides access to template data. The script ensures secure access through authentication and validates incoming requests to maintain data integrity.

## Main Functionalities

- **Logging**: Utilizes Python's `logging` module to log events and errors for debugging and monitoring purposes.
- **DynamoDB Integration**: Connects to AWS DynamoDB to fetch template data using the provided template ID.
- **Request Validation**: Validates incoming requests to ensure they meet the required schema and parameters.
- **Error Handling**: Manages various error scenarios, including validation errors, missing templates, and execution errors, returning appropriate HTTP status codes and messages.

## How to Use

### Prerequisites

- **AWS Credentials**: Ensure that your environment is configured with the necessary AWS credentials to access DynamoDB.
- **Environment Variables**:
  - `LOG_LEVEL`: Set the desired logging level (e.g., `INFO`, `DEBUG`).
  - `TABLE`: Specify the name of the DynamoDB table containing the templates.

### Endpoint

- **GET /{id}**: Retrieve a single template by its ID.

### Parameters

- **Path Parameter**:
  - `id` (string): The unique identifier of the template to be retrieved.
  
- **Header**:
  - `Authorization` (string): Access token required for authentication.

### Responses

- **200 OK**: Template successfully retrieved. Returns the template data in JSON format.
- **404 Not Found**: Template with the specified ID does not exist.
- **422 Unprocessable Entity**: Validation errors occurred in the request.
- **500 Internal Server Error**: An error occurred during the execution of the request.

### Execution Flow

1. **Logging Initialization**: Sets up logging based on the specified log level.
2. **DynamoDB Resource Initialization**: Connects to the DynamoDB service and specifies the table using environment variables.
3. **Request Handling**:
   - Extracts the template ID from the path parameters.
   - Validates the request schema.
   - Attempts to retrieve the template from DynamoDB.
4. **Error Handling**:
   - Returns a 422 status for validation errors.
   - Returns a 404 status if the template is not found.
   - Returns a 500 status for any execution errors.
5. **Response Construction**: Constructs and returns the HTTP response with the appropriate status and message.

For detailed API specifications and examples, please refer to the Swagger documentation.

### 📌 Documentation for `helpers\api_responses.py`

# Responses Utility Class

## Overview

The `Responses` class is a utility designed to facilitate the creation of standardized HTTP response objects in a JSON format. This class is particularly useful for web applications and APIs where consistent response structures are crucial for client-server communication.

## Purpose

The primary purpose of the `Responses` class is to provide a simple and efficient way to generate HTTP responses with customizable status codes, success indicators, messages, and data payloads. This ensures that all responses from your application are uniform and easy to interpret by clients.

## Main Functionalities

The `Responses` class offers two main methods:

1. **_define_response**: 
   - Constructs a basic HTTP response dictionary.
   - Allows specification of the HTTP status code and the data payload.
   - Returns a dictionary with headers, status code, and a JSON-formatted body.

2. **result_response**:
   - Builds a detailed HTTP response that includes a success flag and a message.
   - Accepts parameters for status code, success status, message, and data payload.
   - Utilizes the `_define_response` method to create the final response object.

## How to Use

### _define_response Method

- **Purpose**: To create a basic HTTP response with a specified status code and data payload.
- **Parameters**:
  - `status_code` (int): The HTTP status code for the response. Default is 502.
  - `data` (dict): The payload to be included in the response body. Default is an empty dictionary.
- **Returns**: A dictionary representing the HTTP response, including headers, status code, and body.

### result_response Method

- **Purpose**: To generate a detailed HTTP response with success status and a message.
- **Parameters**:
  - `status_code` (int): The HTTP status code for the response. Default is 502.
  - `success` (bool): Indicates whether the operation was successful. Default is False.
  - `message` (str): A message providing additional information about the response. Default is an empty string.
  - `data` (dict): The payload to be included in the response body. Default is an empty dictionary.
- **Returns**: A dictionary representing the HTTP response, including headers, status code, and a body with success status, message, and data.

## Usage Instructions

To use the `Responses` class, simply import it into your project and call the desired method with the appropriate parameters. The methods will return a dictionary that can be directly used as an HTTP response in your web application or API.

For detailed examples and further documentation, please refer to the Swagger documentation associated with this project.

### 📌 Documentation for `helpers\check_authorization.py`

# Authorization Token Validator

## Overview

This script is designed to validate authorization tokens from incoming events, extract user information, and verify the user's AWS account using AWS Cognito if necessary. It is particularly useful in serverless applications where user authentication and authorization are required.

## Main Functionalities

- **Authorization Token Validation**: The script checks for the presence of an authorization token in the event headers and decodes it to extract user information.
- **User Information Extraction**: It extracts the user ID from the token payload, prioritizing the user's email. If the email is not available, it attempts to retrieve the client ID.
- **AWS Cognito Verification**: If necessary, the script verifies the user's AWS account using AWS Cognito by describing the user pool client to obtain the client name.

## Usage

### Prerequisites

- Ensure that you have the necessary AWS credentials configured to access AWS Cognito.
- Set the environment variable `COGNITO_POOL_ID` with your AWS Cognito User Pool ID.

### Steps

1. **Event Input**: The script expects an event dictionary containing headers with an authorization token. The token should be in the format `Bearer <token>`.

2. **Token Extraction and Decoding**:
   - The script retrieves the authorization token from the event headers.
   - It decodes the token without verifying the signature to extract the payload.

3. **User ID Retrieval**:
   - The script first attempts to extract the user's email from the token payload.
   - If the email is not present, it retrieves the client ID and uses AWS Cognito to describe the user pool client, using the client name as the user ID.

4. **Error Handling**:
   - If the authorization token is missing, invalid, or lacks necessary information (both email and client ID), the script raises a `BadRequest` error with an appropriate status code.

### Environment Variables

- `COGNITO_POOL_ID`: The ID of the AWS Cognito User Pool used for verifying the client ID.

## Error Handling

The script raises a `BadRequest` exception in the following scenarios:

- Missing authorization token.
- Invalid token.
- Missing both email and client ID in the token payload.

## Conclusion

This script provides a robust mechanism for validating authorization tokens and extracting user information in serverless applications. By leveraging AWS Cognito, it ensures that user verification is secure and reliable. For detailed API usage and examples, please refer to the Swagger documentation.

### 📌 Documentation for `helpers\construct_response.py`

# README

## Overview

This documentation provides an overview of the `construct_response` function, a utility designed to format backend process results into standardized HTTP responses. This function is particularly useful in web applications and services where consistent HTTP communication is required.

## Purpose

The primary purpose of the `construct_response` function is to transform a result dictionary, typically obtained from backend operations, into a structured HTTP response. This ensures that the response adheres to HTTP standards, facilitating seamless communication between the server and client.

## Main Functionalities

- **HTTP Status Code Extraction**: The function extracts the HTTP status code from the provided result dictionary, ensuring that the response accurately reflects the outcome of the backend process.
  
- **Response Body Formatting**: It formats the response body, extracted from the result dictionary, to be included in the HTTP response. This body is typically in JSON format, containing the data or message intended for the client.

- **Header Configuration**: The function sets the HTTP headers, specifically configuring the 'Content-Type' to 'application/json'. This indicates that the response body is formatted in JSON, which is a widely used data interchange format.

## Usage

To utilize the `construct_response` function, follow these steps:

1. **Prepare the Result Dictionary**: Ensure that you have a dictionary containing at least two keys: `statusCode` and `body`. The `statusCode` should be an integer representing the HTTP status code, and the `body` should be a JSON-compatible object or string representing the response content.

2. **Call the Function**: Pass the prepared result dictionary to the `construct_response` function. This will return a new dictionary formatted as an HTTP response.

3. **Integrate with HTTP Communication**: Use the returned dictionary in your HTTP communication logic, such as sending responses in a web server or API endpoint.

## Example

While specific examples are provided in the Swagger documentation, the general usage pattern involves preparing a result dictionary and passing it to the function as shown below:

```python
result = {
    'statusCode': 200,
    'body': {'message': 'Success'}
}

http_response = construct_response(result)
```

In this example, the `http_response` will be a dictionary structured for HTTP communication, ready to be sent to the client.

## Conclusion

The `construct_response` function is a simple yet powerful tool for standardizing HTTP responses in web applications. By ensuring consistent formatting and header configuration, it aids in maintaining reliable communication between server and client components. For detailed examples and further integration guidance, refer to the Swagger documentation accompanying this function.

### 📌 Documentation for `helpers\get_secret.py`

# AWS Secrets Manager Retrieval Script

## Overview

This script is designed to interact with AWS Secrets Manager to securely retrieve secret values. It is implemented in Python and leverages the `boto3` library to communicate with AWS services. The script is particularly useful for applications that need to access sensitive information, such as API keys or database credentials, stored in AWS Secrets Manager.

## Main Functionalities

- **Environment Configuration**: The script uses environment variables to configure the AWS region and the default secret name.
- **Secret Retrieval**: It fetches secrets from AWS Secrets Manager, handling both string and binary formats.
- **Error Handling**: The script includes basic error handling to manage exceptions during the secret retrieval process.

## How to Use

### Prerequisites

- **AWS Credentials**: Ensure that your environment is configured with the necessary AWS credentials to access Secrets Manager. This can be done via AWS CLI configuration or environment variables.
- **Environment Variables**: Set the following environment variables:
  - `REGION`: The AWS region where your Secrets Manager is hosted.
  - `SECRET_NAME`: (Optional) The default name of the secret to retrieve if not specified in the function call.

### Steps

1. **Set Up Environment**: Configure your environment with the necessary AWS credentials and set the required environment variables (`REGION` and optionally `SECRET_NAME`).

2. **Initialize the Script**: The script initializes a `boto3` client for AWS Secrets Manager using the specified region from the environment variables.

3. **Retrieve Secret**: Call the `get_secret` function with the desired secret name. If no name is provided, it defaults to the `SECRET_NAME` environment variable.

   - **Function Signature**: `get_secret(secret_name=None)`
     - `secret_name`: (Optional) The name of the secret to retrieve.

4. **Handle Response**: The function returns the secret value. If the secret is a JSON string, it is returned as a dictionary. If it is stored in binary format, it is decoded and returned as a string.

5. **Error Management**: If an error occurs during the retrieval process, the function returns the exception object for further handling.

### Example Usage

For detailed examples and API documentation, please refer to the Swagger documentation associated with this script.

## Conclusion

This script provides a straightforward method to securely access secrets stored in AWS Secrets Manager, supporting both JSON and binary formats. By leveraging environment variables and AWS's robust security features, it ensures that sensitive information is handled securely and efficiently.

### 📌 Documentation for `helpers\schema_validation.py`

# Request Body Validation Script

## Overview

This script is designed to validate HTTP request bodies against a predefined JSON schema. It supports various HTTP methods, including `POST`, `PUT`, `DELETE`, and `GET`, ensuring that the request data adheres to the expected format and constraints. The script also processes certain fields to standardize data before validation.

## Main Functionalities

- **Schema Validation**: Validates request bodies against a JSON schema tailored to the HTTP method.
- **Data Processing**: Converts string representations of booleans to actual boolean values and standardizes string fields by converting them to uppercase and removing accents.
- **Custom Format Checking**: Implements custom format checkers for UUID and date-time fields to ensure data integrity.
- **Error Reporting**: Provides detailed error messages when validation fails, aiding in debugging and data correction.

## How to Use

### Prerequisites

Ensure you have the following Python libraries installed:

- `uuid`
- `dateutil`
- `jsonschema`
- `unidecode`

You can install these libraries using pip:

```bash
pip install python-dateutil jsonschema unidecode
```

### Function: `validate_request_body_schema`

#### Parameters

- `method` (str): The HTTP method for the request. Supported methods are `POST`, `PUT`, `DELETE`, and `GET`.
- `body` (dict): The request body to be validated, structured as a dictionary.

#### Returns

- A dictionary with the following keys:
  - `success` (bool): Indicates whether the validation was successful.
  - `message` (str): Provides details on validation errors, if any.
  - `data` (dict, optional): Contains processed request data for `POST` and `PUT` methods if validation is successful.

### Validation Process

1. **Method and Body Type Check**: Ensures that the `method` is a string and `body` is a dictionary.
2. **Custom Format Checkers**: Registers custom format checkers for UUID and date-time fields.
3. **Schema Definition**: Defines a JSON schema with required fields and formats based on the HTTP method.
4. **Data Processing**:
   - Converts string booleans (`'true'`, `'false'`) to actual boolean values.
   - Standardizes string fields by converting them to uppercase and removing accents.
5. **Validation Execution**:
   - For `POST` and `PUT`: Validates the processed data against the schema.
   - For `DELETE`: Validates the presence and format of the `id` field.
   - For `GET`: Validates the data directly against the schema.
6. **Error Handling**: Returns detailed error messages if validation fails, or success with processed data if it passes.

### Supported HTTP Methods

- **POST**: Requires `templateCompany` and `templateAgent` fields. Processes and validates the entire request body.
- **PUT**: Similar to `POST`, processes and validates the entire request body.
- **DELETE**: Requires an `id` field. Validates only the `id` field.
- **GET**: Validates the request body without additional processing.

### Error Handling

- Returns a structured error message if the method is unsupported or if validation fails due to schema mismatches or format errors.

For detailed examples and further usage instructions, please refer to the Swagger documentation associated with this script.

### 📌 Documentation for `list\handler.py`

# Template Retrieval Service

## Overview

This script is designed to handle HTTP GET requests for retrieving a list of templates from an AWS DynamoDB table. It allows filtering based on various query parameters, such as company name, agent name, root cause, and more. The script is implemented in Python and leverages AWS SDK (boto3) for database interactions, along with custom helper modules for response construction and schema validation.

## Main Functionalities

- **Query Parameter Filtering**: Supports multiple query parameters to filter templates, including company name, agent name, root cause, validation status, and more.
- **DynamoDB Integration**: Utilizes AWS DynamoDB to store and retrieve template data.
- **Response Construction**: Constructs HTTP responses with appropriate status codes and messages.
- **Schema Validation**: Validates request parameters to ensure they meet expected formats and types.
- **Logging**: Provides logging capabilities for debugging and monitoring.

## How to Use

### Prerequisites

- Ensure you have AWS credentials configured for accessing DynamoDB.
- Set the environment variable `TABLE` to the name of your DynamoDB table.
- Set the environment variable `LOG_LEVEL` to control logging verbosity (e.g., `INFO`, `DEBUG`).

### API Endpoint

The script exposes a single endpoint:

- **GET /**: Retrieves a list of templates based on the provided query parameters.

### Query Parameters

The following query parameters can be used to filter the templates:

- `templateCompany`: Filter by company name (string).
- `templateAgent`: Filter by agent name (string).
- `templateRootCause`: Filter by root cause (string).
- `templateAgentValidation`: Filter by agent validation status (boolean).
- `templateIntentFailed`: Filter by intent failure status (boolean).
- `isActive`: Filter by active status (boolean).
- `templateStatus`: Filter by completion status (string).
- `createdBy`: Filter by creator's name (string).
- `updatedBy`: Filter by modifier's name (string).
- `createdAt`: Filter by creation date (date-time).
- `updatedAt`: Filter by modification date (date-time).
- `createdStart`: Filter by start creation date (date-time).
- `createdEnd`: Filter by end creation date (date-time).
- `updatedStart`: Filter by start update date (date-time).
- `updatedEnd`: Filter by end update date (date-time).
- `offset`: Number of initial results to skip (integer).
- `limit`: Maximum number of results to return (integer).

### Headers

- `Authorization`: Access token required for authentication (string).

### Responses

- **200 OK**: Successful retrieval of templates.
- **404 Not Found**: No templates found matching the criteria.
- **422 Unprocessable Entity**: Validation errors in the request.
- **500 Internal Server Error**: Error during execution.

### Logging

The script logs events and errors using Python's `logging` module. The log level can be adjusted via the `LOG_LEVEL` environment variable.

### Error Handling

The script includes error handling to manage exceptions during execution, returning appropriate HTTP status codes and error messages.

## Additional Information

For detailed API documentation and examples, please refer to the Swagger documentation associated with this service.

### 📌 Documentation for `post\handler.py`

# Template Creation API - README

## Overview

This script is designed to handle the creation of new templates through a RESTful API endpoint. It leverages AWS services, specifically DynamoDB, to store template data. The script is implemented in Python and is intended to be deployed in a serverless environment, such as AWS Lambda.

## Main Functionalities

- **Template Creation**: The primary function of this script is to create a new template based on the data provided in the API request.
- **Authorization**: Ensures that the request is authorized by checking the provided access token.
- **Data Validation**: Validates the incoming request data against a predefined schema to ensure data integrity.
- **Logging**: Provides detailed logging for debugging and monitoring purposes.
- **Error Handling**: Handles various error scenarios and returns appropriate HTTP status codes and messages.

## How to Use

### Prerequisites

- **AWS Account**: Ensure you have access to AWS services, particularly DynamoDB.
- **Environment Variables**: Set the following environment variables:
  - `TABLE`: The name of the DynamoDB table where templates will be stored.
  - `LOG_LEVEL`: The desired logging level (e.g., `INFO`, `DEBUG`).

### API Endpoint

The script exposes a POST endpoint for creating templates. The endpoint is documented using Swagger/OpenAPI, which provides detailed information about the request and response formats.

### Request Structure

- **Headers**:
  - `Authorization`: A valid access token is required for authentication.

- **Body**: The request body must be a JSON object containing the following fields:
  - `templateCompany` (string, required): The name of the company.
  - `templateAgent` (string, required): The name of the agent.
  - `templateActionsTag` (string, required): The tag for the action.
  - `templateActionsTimeStamp` (string, required): The timestamp for the action.
  - Additional optional fields include `templateRootCause`, `templateAgentValidation`, `templateIntentFailed`, `isActive`, `templateActions`, and `templateStatus`.

### Response Structure

- **Success (201)**: Returns a JSON object indicating successful template creation, including the newly created template data.
- **Error (422)**: Returns a JSON object with validation error details if the request data is invalid.
- **Error (500)**: Returns a JSON object with error details if an internal server error occurs.

### Deployment

Deploy the script as an AWS Lambda function and configure it to be triggered by an API Gateway endpoint. Ensure that the Lambda function has the necessary permissions to access DynamoDB and other AWS resources.

## Logging

The script uses Python's built-in logging module to log events at various levels. The log level can be configured via the `LOG_LEVEL` environment variable.

## Error Handling

The script includes comprehensive error handling to manage validation errors, authorization failures, and unexpected exceptions. It returns appropriate HTTP status codes and error messages to the client.

## Conclusion

This script provides a robust solution for creating templates via a RESTful API. It ensures data integrity through validation, secures access with authorization checks, and offers detailed logging for operational insights. For detailed API usage and examples, refer to the Swagger documentation.

### 📌 Documentation for `put\handler.py`

# Template Update Script

## Overview

This script is designed to handle the update of a template stored in an AWS DynamoDB table. It is implemented as an AWS Lambda function and is triggered via an HTTP PUT request. The script ensures that the template is updated based on the provided ID and request body, with proper validation and authorization checks.

## Main Functionalities

- **Authorization Check**: Verifies if the request is authorized and retrieves the email of the user making the request.
- **Request Validation**: Validates the request body against a predefined schema to ensure data integrity.
- **DynamoDB Interaction**: Updates the specified template in the DynamoDB table if it exists.
- **Logging**: Provides detailed logging for debugging and monitoring purposes.
- **Error Handling**: Returns appropriate HTTP responses for different scenarios, including validation errors, authorization failures, and server errors.

## How to Use

### Prerequisites

- **AWS Environment**: Ensure that AWS credentials are configured to allow access to DynamoDB and Lambda.
- **Environment Variables**: Set the following environment variables:
  - `TABLE`: The name of the DynamoDB table.
  - `LOG_LEVEL`: The desired logging level (e.g., `INFO`, `DEBUG`).

### Execution Flow

1. **Event and Context**: The function receives an `event` and `context` object. The `event` contains request data, including headers, path parameters, and body, while the `context` provides runtime information about the Lambda function execution.

2. **Logging**: The function logs the incoming event and entry into the function for debugging purposes.

3. **DynamoDB Initialization**: A DynamoDB resource is initialized, and the specified table is accessed.

4. **Request Parsing**: The request body is parsed, and boolean values are formatted correctly. The HTTP method and path parameter ID are extracted from the event.

5. **Schema Validation**: The request body is validated against the expected schema. If validation fails, a 422 response is returned with error details.

6. **Authorization Check**: The function checks if the request is authorized and retrieves the email of the user making the request.

7. **Update Query Generation**: An update query is generated for DynamoDB using the validated data.

8. **DynamoDB Update**: The function checks if the item with the given ID exists in DynamoDB. If it exists, the item is updated with new data. If not, a 404 response is returned.

9. **Response Construction**: A response is constructed and returned to the client, indicating the success or failure of the update operation.

### Error Handling

- **Validation Errors**: If the request body does not conform to the expected schema, a 422 response is returned.
- **Item Not Found**: If the specified template ID does not exist in the DynamoDB table, a 404 response is returned.
- **Server Errors**: Any exceptions during execution result in a 500 response with error details.

### Logging

The script uses Python's `logging` module to log events at various levels (e.g., DEBUG, INFO). The log level can be configured via the `LOG_LEVEL` environment variable.

## Swagger Documentation

For detailed API specifications, including path parameters, headers, request body schema, and possible responses, please refer to the Swagger documentation.


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