import json

class Responses:
    """
    A utility class for generating standardized HTTP response objects.
    
    This class provides static methods to create JSON-formatted HTTP responses
    with customizable status codes, success flags, messages, and data payloads.
    """

    @staticmethod
    def _define_response(status_code=502, data={}):
        """
        Constructs a basic HTTP response structure.

        Args:
            status_code (int): The HTTP status code for the response. Defaults to 502.
            data (dict): The payload to be included in the response body. Defaults to an empty dictionary.

        Returns:
            dict: A dictionary representing the HTTP response with headers, status code, and JSON body.
        """
        # Create a response dictionary with JSON content type and specified status code
        return {
            'headers': {
                'Content-Type': 'application/json'  # Specify that the response content is JSON
            },
            'status_code': status_code,  # Set the HTTP status code
            'body': json.dumps(data)  # Convert the data dictionary to a JSON string for the response body
        }

    @staticmethod
    def result_response(status_code=502, success=False, message='', data={}):
        """
        Constructs a detailed HTTP response with success status and message.

        Args:
            status_code (int): The HTTP status code for the response. Defaults to 502.
            success (bool): Indicates whether the operation was successful. Defaults to False.
            message (str): A message providing additional information about the response. Defaults to an empty string.
            data (dict): The payload to be included in the response body. Defaults to an empty dictionary.

        Returns:
            dict: A dictionary representing the HTTP response with headers, status code, and JSON body.
        """
        # Create a data response dictionary with success status, message, and data payload
        data_response = {
            'success': success,  # Boolean flag indicating success or failure of the operation
            'message': message,  # Additional information or message about the response
            'data': data  # The actual data payload to be included in the response
        }
        # Use the _define_response method to construct the final response structure
        return Responses._define_response(status_code, data_response)