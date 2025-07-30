# Import necessary libraries for UUID handling, date parsing, JSON schema validation, and string manipulation
import uuid
import dateutil.parser
import jsonschema
from jsonschema import validate, FormatChecker
from jsonschema.exceptions import ValidationError
from jsonschema.validators import Draft7Validator
from text_unidecode import unidecode
from datetime import datetime

def validate_request_datas_schema(action, datas):
    """
    Validates the structure and content of request data based on the specified action.
    
    Parameters:
    - action (str): The type of action being performed (e.g., 'create', 'update', 'delete', 'get', 'list' for WebSocket or 'POST', 'PUT', 'DELETE', 'GET' for HTTP).
    - datas (dict): The data to be validated, structured as a dictionary.
    
    Returns:
    - dict: A dictionary indicating the success of the validation and any relevant messages or validated data.
    """
    
    # Map WebSocket actions to HTTP methods for validation
    action_mapping = {
        'create': 'POST',
        'update': 'PUT', 
        'delete': 'DELETE',
        'get': 'GET',
        'list': 'GET'
    }
    
    # Convert action to uppercase and map if needed
    original_action = action
    if isinstance(action, str):
        # If it's a WebSocket action, map it to HTTP method
        if action.lower() in action_mapping:
            action = action_mapping[action.lower()]
        else:
            action = action.upper()  # Convert to uppercase for HTTP methods
    
    # Check if action is a string and datas is a dictionary
    if not isinstance(action, str):
        return {'success': False, 'message': 'Action should be a string'}
    if not isinstance(datas, dict):
        return {'success': False, 'message': 'Datas should be a dictionary'}

    def is_uuid_format(instance):
        """Check if the given instance is a valid UUID format."""
        try:
            uuid.UUID(instance)
            return True
        except:
            return False

    def is_date_time_format(instance):
        """Check if the given instance is a valid date-time format."""
        try:
            dateutil.parser.parse(instance)
            return True
        except:
            return False

    # Initialize a format checker with custom UUID and date-time format checks
    format_checker = FormatChecker()
    format_checker.checks("uuid", raises=ValueError)(is_uuid_format)
    format_checker.checks("date-time", raises=ValueError)(is_date_time_format)

    # Define the JSON schema for validating the request data
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
        # Require certain fields based on the action type
        "required": ["templateCompany", "templateAgent"] if action == 'POST' else []
    }
    
    verifiedDatas = {}  # Initialize a dictionary to store verified data
    
    # Handle validation for POST and PUT actions
    if action == 'POST' or action == 'PUT':
        for i in datas:
            # Convert string booleans to actual boolean values
            if datas[i] == 'true':
                datas[i] = True
            elif datas[i] == 'false':
                datas[i] = False
            # Normalize string data to uppercase and remove accents
            if isinstance(datas[i], str):
                verifiedDatas[i] = unidecode(datas[i].upper())
            else:
                verifiedDatas[i] = datas[i]

        # Validate the verified data against the schema
        validator = Draft7Validator(schema, format_checker=format_checker)
        errors = sorted(validator.iter_errors(verifiedDatas), key=lambda e: e.path)
        if errors:
            # Return validation errors if any
            return {'success': False, 'message': ', '.join(error.message for error in errors)}

        return {'success': True, 'message': '', 'datas': verifiedDatas}
    
    # Handle validation for DELETE action
    elif action == 'DELETE':
        if 'id' not in datas:
            return {'success': False, 'message': 'ID not provided in the request datas'}
        try:
            # Validate the presence and format of 'id' in the data
            validate(instance={'id': datas['id']}, schema=schema, format_checker=format_checker)
        except ValidationError as e:
            return {'success': False, 'message': str(e)}
    
        return {'success': True}

    # Handle validation for GET action
    elif action == 'GET':
        for i in datas:
            verifiedDatas[i] = datas[i]

        # Validate the verified data against the schema
        validator = Draft7Validator(schema, format_checker=format_checker)
        errors = sorted(validator.iter_errors(verifiedDatas), key=lambda e: e.path)
        if errors:
            # Return validation errors if any
            return {'success': False, 'message': ', '.join(error.message for error in errors)}

        return {'success': True}
    
    else:
        # Return an error message for unsupported actions
        return {'success': False, 'message': f'Invalid action: {original_action}. Valid actions are: create, update, delete, get, list'}