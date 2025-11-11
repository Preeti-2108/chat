from aws_cdk import App
from lambdas_stack import LambdasStack
import os

app = App()

def get_env_var(var_name):
    value = os.getenv(var_name)
    if not value:
        raise ValueError(f"{var_name} is not defined in the environment variables")
    return value

api_name = get_env_var("API_NAME")
version = get_env_var("API_VERSION")
table_name = get_env_var("TABLE")
user_pool_id = get_env_var("COGNITO_POOL_ID")
service_name = get_env_var("SERVICE_NAME")
aws_account_id = get_env_var("AWS_ACCOUNT_ID")
sqs_queue_name = os.getenv("SQS_QUEUE_NAME", "AUDIT_QUEUE")
dead_letter_queue_name = os.getenv("DEAD_LETTER_QUEUE_NAME", "AUDIT_DLQ")
KNOWLEDGE_BASE_ID = get_env_var("KNOWLEDGE_BASE_ID")
AZURE_OPENAI_API_ENDPOINT = get_env_var("AZURE_OPENAI_API_ENDPOINT")
AZURE_OPENAI_MODEL = os.getenv("AZURE_OPENAI_MODEL")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION")
AZURE_OPENAI_API_KEY = get_env_var("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_TEMPERATURE = os.getenv("AZURE_OPENAI_TEMPERATURE")
AZURE_OPENAI_MAX_TOKENS = os.getenv("AZURE_OPENAI_MAX_TOKENS")
BASE_URL = get_env_var("BASE_URL")


# Construct connections table name
connections_table_name = f"{table_name}-CONNECTIONS"

lambdas_stack = LambdasStack(
    app,
    f"{api_name}-lambdas-{version}",
    table_name=table_name,
    user_pool_id=user_pool_id,
    api_name=api_name,
    service_name=service_name,
    aws_account_id=aws_account_id,
    sqs_queue_name=sqs_queue_name,
    dead_letter_queue_name=dead_letter_queue_name,
    connections_table_name=connections_table_name,
    knowledge_base_id=KNOWLEDGE_BASE_ID,
    azure_openai_api_endpoint=AZURE_OPENAI_API_ENDPOINT,
    azure_openai_model=AZURE_OPENAI_MODEL,
    azure_openai_api_version=AZURE_OPENAI_API_VERSION,
    azure_openai_api_key=AZURE_OPENAI_API_KEY,
    azure_openai_temperature=AZURE_OPENAI_TEMPERATURE,
    azure_openai_max_tokens=AZURE_OPENAI_MAX_TOKENS,
    base_url=BASE_URL
)

app.synth()