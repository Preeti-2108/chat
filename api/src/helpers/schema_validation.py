# Import necessary libraries for UUID handling, date parsing, JSON schema validation, and string manipulation
import uuid
import dateutil.parser
from jsonschema import validate, FormatChecker
from jsonschema.exceptions import ValidationError
from jsonschema.validators import Draft7Validator
from text_unidecode import unidecode

def validate_request_body_schema(method, body):
    """
    Validates the request body against a predefined JSON schema based on the HTTP method.
    
    Parameters:
    - method (str): The HTTP method (e.g., 'POST', 'PUT', 'DELETE', 'GET').
    - body (dict): The request body to be validated.
    
    Returns:
    - dict: A dictionary containing the validation result with keys 'success' (bool) and 'message' (str).
            For 'POST' and 'PUT', it may also include 'data' (dict) with processed request data.
    """
    
    # Ensure 'method' is a string and 'body' is a dictionary
    if not isinstance(method, str):
        return {'success': False, 'message': 'Method should be a string'}
    if not isinstance(body, dict):
        return {'success': False, 'message': 'Body should be a dictionary'}

    # Define a custom format checker for UUID validation
    def is_uuid_format(instance):
        try:
            uuid.UUID(instance)  # Attempt to create a UUID object
            return True
        except:
            return False

    # Define a custom format checker for date-time validation
    def is_date_time_format(instance):
        try:
            dateutil.parser.parse(instance)  # Attempt to parse the string as a date-time
            return True
        except:
            return False

    # Initialize a format checker and register custom format checks
    format_checker = FormatChecker()
    format_checker.checks("uuid", raises=ValueError)(is_uuid_format)
    format_checker.checks("date-time", raises=ValueError)(is_date_time_format)

    # Define the JSON schema for validating the request body
    schema = {
        "type": "object",
        "properties": {
            "id": {"type": "string", "format": "uuid"},
            "templateCompany": {"type": "string"},
            "templateAgent": {"type": "string"},
            "templateRootCause": {"type": "string"},
            "templateStatus": {"type": "string"},
            "templateAgentValidation": {"type": "boolean", "default": False},
            "templateIntentFailed": {"type": "boolean", "default": False},
            "isActive": {"type": "boolean", "default": True},
            "templateActions": {"type": "array", "default": []},
            "createdBy": {"type": "string"},
            "updatedBy": {"type": "string"},
            "createdAt": {"type": "string", "format": "date-time"},
            "updatedAt": {"type": "string", "format": "date-time"},
            "createdStart": {"type": "string", "format": "date-time"},
            "createdEnd": {"type": "string", "format": "date-time"},
            "updatedStart": {"type": "string", "format": "date-time"},
            "updatedEnd": {"type": "string", "format": "date-time"},
            "limit": {"type": "integer"},
            "offset": {"type": "integer"}
        },
        # Require certain fields based on the HTTP method
        "required": ["templateCompany", "templateAgent"] if method == 'POST' else []
    }
    
    datas = {}  # Initialize a dictionary to store processed request data
    
    # Handle validation for 'POST' and 'PUT' methods
    if method == 'POST' or method == 'PUT':
        for i in body:
            # Convert string booleans to actual boolean values
            if body[i] == 'true':
                body[i] = True
            elif body[i] == 'false':
                body[i] = False
            # Convert strings to uppercase and remove accents
            if isinstance(body[i], str):
                datas[i] = unidecode(body[i].upper())
            else:
                datas[i] = body[i]

        # Validate the processed data against the schema
        validator = Draft7Validator(schema, format_checker=format_checker)
        errors = sorted(validator.iter_errors(datas), key=lambda e: e.path)
        if errors:
            # Return validation errors if any
            return {'success': False, 'message': ', '.join(error.message for error in errors)}

        # Return success with processed data if validation passes
        return {'success': True, 'message': '', 'data': datas}
    
    # Handle validation for 'DELETE' method
    elif method == 'DELETE':
        if 'id' not in body:
            return {'success': False, 'message': 'ID not provided in the request body'}
        try:
            # Validate only the 'id' field against the schema
            validate(instance={'id': body['id']}, schema=schema, format_checker=format_checker)
        except ValidationError as e:
            # Return validation error if any
            return {'success': False, 'message': str(e)}
    
        # Return success if validation passes
        return {'success': True}

    # Handle validation for 'GET' method
    elif method == 'GET':
        for i in body:
            datas[i] = body[i]  # Directly copy body data to datas

        # Validate the data against the schema
        validator = Draft7Validator(schema, format_checker=format_checker)
        errors = sorted(validator.iter_errors(datas), key=lambda e: e.path)
        if errors:
            # Return validation errors if any
            return {'success': False, 'message': ', '.join(error.message for error in errors)}

        # Return success if validation passes
        return {'success': True}
    
    else:
        # Return error for unsupported HTTP methods
        return {'success': False, 'message': 'Invalid method'}