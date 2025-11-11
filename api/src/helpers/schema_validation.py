import json
from pydantic import BaseModel, ValidationError, UUID4
from typing import Dict, Any
from text_unidecode import unidecode

class PostRequestModel(BaseModel):
    query: str
    modelName: str
    assistantId: str

class PutRequestModel(BaseModel):
    id: str
    query: str

class DeleteRequestModel(BaseModel):
    id: str

class GetChatRequestModel(BaseModel):
    id: str

class GetCHATINTERNALRequestModel(BaseModel):
    id: str

class GetAllRequestModel(BaseModel):
    pass

def validate_and_load_request(event, logger):
    """
    Legacy function for backward compatibility.
    Validates and loads request data from event.

    Returns:
        tuple: (status_code, message, query, model, assistant_id)
    """
    try:
        body = event.get('body', '{}')
        if isinstance(body, str):
            body = json.loads(body)

        datas = body.get('datas', {})
        action = body.get('action', 'create')

        # Use the main validation function
        validation_result = validate_request_datas_schema_pydantic(action, datas, logger)

        if not validation_result['success']:
            return 400, validation_result['message'], None, None, None

        validated_data = validation_result['datas']
        query = validated_data.get('query', '')
        model = validated_data.get('modelName', '')
        assistant_id = validated_data.get('assistantId', '')

        return 200, 'Validation successful', query, model, assistant_id

    except Exception as e:
        logger.error(f"Error in validate_and_load_request: {str(e)}")
        return 500, str(e), None, None, None

def validate_request_datas_schema_pydantic(action: str, datas: Dict[str, Any], logger):
    """
    Validate incoming payload based on action and return a normalized dict.

    Returns a dict with shape:
    {
        'success': bool,
        'message': str,
        'datas': dict  # validated & normalized fields (may be empty on GET list)
    }
    """
        
    action_mapping = {
        'create': 'POST',
        'update': 'PUT',
        'delete': 'DELETE',
        'get': 'GET',      # Get specific chat by ID
        'getassistant': 'GETASSISTANT',      # Get specific chat assistant by ID
        'list': 'LIST',    # Get all chats for user
    }
    original_action = action
    if isinstance(action, str):
        action = action_mapping.get(action.lower(), action.upper())

    if not isinstance(action, str):
        logger.error('Action should be a string')
        return {'success': False, 'message': 'Action should be a string', 'datas': {}}
    if not isinstance(datas, dict):
        logger.error('Datas should be a dictionary')
        return {'success': False, 'message': 'Datas should be a dictionary', 'datas': {}}

    # Normalize string values
    normalized_datas = {}
    for k, v in datas.items():
        if isinstance(v, str):
            sv = v.strip()
            if sv.lower() == 'true':
                normalized_datas[k] = True
            elif sv.lower() == 'false':
                normalized_datas[k] = False
            else:
                normalized_datas[k] = unidecode(sv.lower())
        else:
            normalized_datas[k] = v

    try:
        if action == 'POST':
            model = PostRequestModel(**normalized_datas)
            return {'success': True, 'message': 'Validation successful', 'datas': model.dict()}
        elif action == 'PUT':
            model = PutRequestModel(**normalized_datas)
            return {'success': True, 'message': 'Validation successful', 'datas': model.dict()}
        elif action == 'DELETE':
            model = DeleteRequestModel(**normalized_datas)
            return {'success': True, 'message': 'Validation successful', 'datas': model.dict()}
        elif action == 'GET':
            model = GetChatRequestModel(**normalized_datas)
            return {'success': True, 'message': 'Validation successful', 'datas': model.dict()}
        elif action == 'GETASSISTANT':
            model = GetCHATINTERNALRequestModel(**normalized_datas)
            return {'success': True, 'message': 'Validation successful', 'datas': model.dict()}
        elif action == 'LIST':
            model = GetAllRequestModel()
            return {'success': True, 'message': 'Validation successful', 'datas': {}}
        else:
            logger.error(f'Invalid action: {original_action}. Valid actions are: create, update, delete, get, list')
            return {
                'success': False,
                'message': f'Invalid action: {original_action}. Valid actions are: create, update, delete, get, list',
                'datas': {}
            }
    except ValidationError as e:
        logger.error(f'Validation error: {e.errors()}')
        return {'success': False, 'message': e.errors(), 'datas': {}}
    except Exception as e:
        logger.error(f'Unexpected error: {str(e)}')
        return {'success': False, 'message': 'Unexpected error occurred', 'datas': {}}