from src.helpers.api_responses import Responses
from src.helpers.construct_response import construct_response

def default(event, context):
    """
    Handles the default route for WebSocket messages.

    This function is used as a fallback route when no other specific 
    route matches the incoming WebSocket message. It processes the message
    and routes it to the appropriate handler based on the 'action' field.

    Parameters:
    event (dict): Contains information about the WebSocket event, 
                  including the message body and connection info.
    context (object): Provides runtime information to the handler, 
                      such as function name, memory limit, etc.

    Returns:
    dict: A dictionary representing a WebSocket response.
    """
    from src.helpers.event_utils import extract_event_info
    from src.handler_websocket.handler import send_to_client
    import json
    
    # Extract connection information
    event_info = extract_event_info(event)
    connection_id = event_info.get('connectionId')
    url = event_info.get('url')
    
    try:
        # Parse the message body
        body = json.loads(event.get('body', '{}'))
        action = body.get('action')
        
        # Add debug logging to see what we received
        print(f"DEBUG - Received body: {json.dumps(body, indent=2)}")
        print(f"DEBUG - Action: {action}")
        
        if not action:
            # Return an error response for missing action field
            result = Responses.result_response(
                status_code=422,
                success=False,
                message="Missing action field",
                data={}
            )
            
            # Send response to WebSocket client
            if connection_id:
                send_to_client(connection_id, json.dumps(construct_response(result)), url)
            
            return {
                'statusCode': 422,
                'body': json.dumps('Missing action field')
            }
        
        # If action is provided but no specific route matches, return error
        result = Responses.result_response(
            status_code=400,
            success=False,
            message=f"Unsupported action: {action}",
            data={}
        )
        
        # Send response to WebSocket client
        if connection_id:
            send_to_client(connection_id, json.dumps(construct_response(result)), url)
        
        return {
            'statusCode': 200,
            'body': json.dumps('Message processed')
        }
        
    except json.JSONDecodeError:
        result = Responses.result_response(
            status_code=400,
            success=False,
            message="Invalid JSON format",
            data={}
        )
        
        if connection_id:
            send_to_client(connection_id, json.dumps(construct_response(result)), url)
        
        return {
            'statusCode': 400,
            'body': json.dumps('Invalid JSON format')
        }
    except Exception as e:
        result = Responses.result_response(
            status_code=500,
            success=False,
            message=f"Internal error: {str(e)}",
            data={}
        )
        
        if connection_id:
            send_to_client(connection_id, json.dumps(construct_response(result)), url)
        
        return {
            'statusCode': 500,
            'body': json.dumps('Internal server error')
        }