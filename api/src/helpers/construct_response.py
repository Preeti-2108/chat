def construct_response(result):
    """
    Constructs a standardized HTTP response dictionary.

    This function takes a result dictionary, typically from a backend process or 
    service, and formats it into a structured HTTP response. The response includes 
    a status code, a body, and headers, which are essential components for HTTP 
    communication.

    Parameters:
    result (dict): A dictionary containing the keys 'statusCode' and 'body', 
                   representing the HTTP status code and the response body 
                   respectively.

    Returns:
    dict: A dictionary formatted as an HTTP response, including:
          - 'statusCode': The HTTP status code extracted from the result.
          - 'body': The response body extracted from the result.
          - 'headers': A dictionary containing HTTP headers, specifically 
                       setting 'Content-Type' to 'application/json' to indicate 
                       the response body is in JSON format.
    """
    return {
        'statusCode': result['statusCode'],  # Extract and set the HTTP status code from the result
        'body': result['body'],  # Extract and set the response body from the result
        'headers': {
            'Content-Type': 'application/json'  # Set the content type header to JSON
        }
    }