import json

class Responses:
    """
    A utility class for generating standardized HTTP response objects.
    This class provides methods to create JSON-formatted responses with
    customizable status codes, success flags, messages, and data payloads.
    """

    def _define_response(status_code=502, data={}):
        """
        Constructs a basic HTTP response dictionary.

        Args:
            status_code (int): The HTTP status code for the response. Defaults to 502.
            data (dict): The payload to be included in the response body. Defaults to an empty dictionary.

        Returns:
            dict: A dictionary representing the HTTP response, including headers, status code, and body.
        """
        return {
            'headers': {
                'Content-Type': 'application/json'  # Specifies that the response content is JSON
            },
            'statusCode': status_code,  # Sets the HTTP status code for the response
            'body': json.dumps(data)  # Serializes the data dictionary to a JSON-formatted string
        }

    def result_response(status_code=502, success=False, message='', data={}):
        """
        Constructs a detailed HTTP response with success status and message.

        Args:
            status_code (int): The HTTP status code for the response. Defaults to 502.
            success (bool): Indicates whether the operation was successful. Defaults to False.
            message (str): A message providing additional information about the response. Defaults to an empty string.
            data (dict): The payload to be included in the response body. Defaults to an empty dictionary.

        Returns:
            dict: A dictionary representing the HTTP response, including headers, status code, and a body with success status, message, and data.
        """
        # Create a response payload with success status, message, and data
        data_response = {
            'success': success,  # Indicates the success status of the operation
            'message': message,  # Provides additional information about the response
            'data': data  # Contains the data payload for the response
        }

        # Use the _define_response method to construct the final response object
        return Responses._define_response(status_code, data_response)