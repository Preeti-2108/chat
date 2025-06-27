# Import necessary modules for accessing environment variables, interacting with AWS Secrets Manager,
# encoding/decoding binary data, and handling JSON data.
import os
import boto3
import base64
import json

# Retrieve the AWS region from environment variables to configure the Secrets Manager client.
region = os.getenv('REGION')

# Initialize a boto3 client for AWS Secrets Manager using the specified region.
client = boto3.client('secretsmanager', region_name=region)

def get_secret(secret_name=None):
    """
    Retrieve a secret from AWS Secrets Manager.

    This function fetches a secret value from AWS Secrets Manager. If no secret name is provided,
    it defaults to using the secret name specified in the environment variable 'SECRET_NAME'.
    The function handles both string and binary secrets, decoding them appropriately.

    Args:
        secret_name (str, optional): The name of the secret to retrieve. Defaults to None.

    Returns:
        dict or str: The secret value as a dictionary if it's a JSON string, or as a decoded string
        if it's stored in binary format. Returns an exception object if an error occurs during retrieval.
    """
    # Use the provided secret name or default to the environment variable 'SECRET_NAME' if none is given.
    if secret_name is None:
        secret_name = os.getenv('SECRET_NAME')

    try:
        # Attempt to retrieve the secret value from AWS Secrets Manager using the secret name.
        response = client.get_secret_value(SecretId=secret_name)
    except Exception as e:
        # Return the exception object if an error occurs during the secret retrieval process.
        return e

    # Check if the secret is stored as a string in the response.
    if 'SecretString' in response:
        # Parse the JSON string into a Python dictionary.
        secret = json.loads(response['SecretString'])
    else:
        # Decode the binary secret using base64 and convert it to an ASCII string.
        decoded_binary_secret = base64.b64decode(response['SecretBinary']).decode('ascii')

    # Return the secret as a dictionary if it's a JSON string, or as a decoded string if it's binary.
    return secret if 'SecretString' in response else decoded_binary_secret