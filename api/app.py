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
# var_example = get_env_var("VAR_EXAMPLE")


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
    # var_example=var_example
)

app.synth()