import uuid
import dateutil.parser
import jsonschema
from jsonschema import validate, FormatChecker
from jsonschema.exceptions import ValidationError
from jsonschema.validators import Draft7Validator
from unidecode import unidecode
from datetime import datetime

def validate_request_datas_schema(action, datas):
    action = action.upper()
    # Check if action and datas are of correct type
    if not isinstance(action, str):
        return {'success': False, 'message': 'Action should be a string'}
    if not isinstance(datas, dict):
        return {'success': False, 'message': 'Datas should be a dictionary'}

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

    # Define the main validation schema for various properties of the request datas
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
        "required": ["templateCompany", "templateAgent"] if action == 'POST' else []
    }
    
    verifiedDatas = {}
    
    # Validate request datas for a POST or PUT action
    if action == 'POST' or action == 'PUT':
        for i in datas:
            if datas[i] == 'true':
                datas[i] = True
            elif datas[i] == 'false':
                datas[i] = False
            if isinstance(datas[i], str):
                verifiedDatas[i] = unidecode(datas[i].upper())
            else:
                verifiedDatas[i] = datas[i]

        validator = Draft7Validator(schema, format_checker=format_checker)
        errors = sorted(validator.iter_errors(verifiedDatas), key=lambda e: e.path)
        if errors:
            return {'success': False, 'message': ', '.join(error.message for error in errors)}

        return {'success': True, 'message': '', 'datas': verifiedDatas}
    
    # Validate request datas for a DELETE action
    elif action == 'DELETE':
        if 'id' not in datas:
            return {'success': False, 'message': 'ID not provided in the request datas'}
        try:
            validate(instance={'id': datas['id']}, schema=schema, format_checker=format_checker)
        except ValidationError as e:
            return {'success': False, 'message': str(e)}
    
        return {'success': True}

    # Validate request datas for a GET action
    elif action == 'GET':
        for i in datas:
            verifiedDatas[i] = datas[i]

        validator = Draft7Validator(schema, format_checker=format_checker)
        errors = sorted(validator.iter_errors(verifiedDatas), key=lambda e: e.path)
        if errors:
            return {'success': False, 'message': ', '.join(error.message for error in errors)}

        return {'success': True}
    
    else:
        return {'success': False, 'message': 'Invalid action'}