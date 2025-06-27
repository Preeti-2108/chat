def disconnect(event, context):
    """
    Handles the disconnection event for a client in a serverless environment.

    This function is typically triggered when a client disconnects from a WebSocket
    or similar connection. It is designed to be used in a serverless architecture,
    such as AWS Lambda, where it receives an event and context as parameters.

    Parameters:
    event (dict): Contains information about the disconnection event. This may include
                  details such as the connection ID and any other relevant metadata.
    context (object): Provides runtime information about the Lambda function execution.
                      This includes details such as the function name, memory limit, 
                      and request ID.

    Returns:
    dict: A response object with a status code and a message body indicating the 
          disconnection was successful. The status code 200 signifies a successful 
          HTTP response.
    """
    # Return a response indicating successful disconnection
    return {
        "statusCode": 200,  # HTTP status code for successful request
        "body": "Disconnected"  # Message body confirming disconnection
    }