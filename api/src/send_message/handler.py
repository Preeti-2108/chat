def send_message(event, context):
    """
    Handles the sending of a message triggered by an event.
    
    This function is typically invoked in response to an event, such as an HTTP request
    or a message from a queue. It processes the event and returns a response indicating
    the status of the message sending operation.
    
    Parameters:
    event (dict): A dictionary containing event data. This could include details such as
                  the message content, sender information, or any other relevant metadata.
    context (object): An object providing runtime information about the function execution.
                      This may include details such as the function's execution environment,
                      request ID, or timeout settings.
    
    Returns:
    dict: A dictionary containing the HTTP status code and a message body. The status code
          indicates the success of the operation (200 for success), and the body contains
          a confirmation message ("Message sent").
    """
    
    # Return a response with a status code of 200, indicating success,
    # and a body message confirming that the message has been sent.
    return {
        "statusCode": 200,  # HTTP status code for successful request
        "body": "Message sent"  # Confirmation message for the client
    }