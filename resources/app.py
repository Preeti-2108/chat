from aws_cdk import App
from resources_stack import ResourcesStack
import os
import boto3

app = App()

def get_env_var(var_name):
    value = os.getenv(var_name)
    if not value:
        raise ValueError(f"{var_name} is not defined in the environment variables")
    return value

api_name = get_env_var("API_NAME")
version = get_env_var("API_VERSION")
table_name = get_env_var("TABLE")
secret_name = get_env_var("SECRET_NAME")
secret_value = get_env_var("SECRET_VALUE")
user_pool_id = get_env_var("COGNITO_POOL_ID")
environment = os.getenv("TF_VAR_ENV", "dev")
sqs_queue_name = "AUDIT_QUEUE"
dead_letter_queue_name = "AUDIT_DLQ"


def does_dynamodb_table_exist(name):
    client = boto3.client("dynamodb")
    try:
        client.describe_table(TableName=name)
        return True
    except client.exceptions.ResourceNotFoundException:
        return False

def does_secret_exist(name):
    client = boto3.client("secretsmanager")
    try:
        client.describe_secret(SecretId=name)
        return True
    except client.exceptions.ResourceNotFoundException:
        return False

def does_sqs_queue_exist(name):
    client = boto3.client("sqs")
    try:
        account_id = boto3.client("sts").get_caller_identity()["Account"]
        region = boto3.Session().region_name
        queue_url = f"https://sqs.{region}.amazonaws.com/{account_id}/{name}"
        client.get_queue_attributes(QueueUrl=queue_url)
        return True
    except client.exceptions.QueueDoesNotExist:
        return False
    except Exception:
        return False

create_table = not does_dynamodb_table_exist(table_name)
create_secret = not does_secret_exist(secret_name)
create_sqs_queues = not (does_sqs_queue_exist(sqs_queue_name) and does_sqs_queue_exist(dead_letter_queue_name))
# Check if connections table exists
connections_table_name = f"{table_name}-CONNECTIONS"
create_connections_table = True  # Force creation of connections table

resources_stack = ResourcesStack(
    app,
    f"{api_name}-resources-{version}",
    table_name=table_name,
    secret_name=secret_name,
    secret_value=secret_value,
    user_pool_id=user_pool_id,
    sqs_queue_name=sqs_queue_name,
    dead_letter_queue_name=dead_letter_queue_name,
    environment=environment,
    create_table=create_table,
    create_secret=create_secret,
    create_sqs_queues=create_sqs_queues,
    create_connections_table=create_connections_table,
)

app.synth()