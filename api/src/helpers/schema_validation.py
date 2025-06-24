import uuid
import dateutil.parser
from jsonschema import validate, FormatChecker
from jsonschema.exceptions import ValidationError
from jsonschema.validators import Draft7Validator
from text_unidecode import unidecode
from datetime import datetime

def validate_request_body_schema(method, body):
    
    # Check if method and body are of correct type
    if not isinstance(method, str):
        return {'success': False, 'message': 'Method should be a string'}
    if not isinstance(body, dict):
        return {'success': False, 'message': 'Body should be a dictionary'}

    def is_uuid_format(instance):
        try:
            uuid.UUID(instance)
            return True
        except:
            return False

    def is_date_time_format(instance):
        try:
            dateutil.parser.parse(instance)
            return True
        except:
            return False

    format_checker = FormatChecker()
    format_checker.checks("uuid", raises=ValueError)(is_uuid_format)
    format_checker.checks("date-time", raises=ValueError)(is_date_time_format)

    # Define the main validation schema for various properties of the request body
    schema = {
        "type": "object",
        "properties": {
            "id": {"type": "string", "format" : "uuid"},
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
        "required": ["templateCompany", "templateAgent"] if method == 'POST' else []
    }
    
    datas = {}

    # Validate request body for a POST or PUT method
    if method == 'POST' or method == 'PUT':
        for i in body:
            value = body[i]
            if value == 'true':
                value = True
            elif value == 'false':
                value = False
            datas[i] = value
        validator = Draft7Validator(schema, format_checker=format_checker)
        errors = sorted(validator.iter_errors(datas), key=lambda e: e.path)
        if errors:
            return {'success': False, 'message': ', '.join(error.message for error in errors)}
        for i in datas:
            if isinstance(datas[i], str):
                datas[i] = unidecode(datas[i].upper())
        return {'success': True, 'message': '', 'data': datas}
    
    # Validate request body for a DELETE method
    elif method == 'DELETE':
        if 'id' not in body:
            return {'success': False, 'message': 'ID not provided in the request body'}
        try:
            validate(instance={'id': body['id']}, schema=schema, format_checker=format_checker)
        except ValidationError as e:
            return {'success': False, 'message': str(e)}
    
        return {'success': True}

    # Validate request body for a GET method
    elif method == 'GET':
        for i in body:
            datas[i] = body[i]

        validator = Draft7Validator(schema, format_checker=format_checker)
        errors = sorted(validator.iter_errors(datas), key=lambda e: e.path)
        if errors:
            return {'success': False, 'message': ', '.join(error.message for error in errors)}

        return {'success': True}
    
    else:
        return {'success': False, 'message': 'Invalid method'}