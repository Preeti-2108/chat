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
table_name = get_env_var("TABLE_NAME")
user_pool_id = get_env_var("COGNITO_POOL_ID")

lambdas_stack = LambdasStack(
    app,
    f"{api_name}-lambdas-{version}",
    table_name=table_name,
    user_pool_id=user_pool_id,
    api_name=api_name,
)

app.synth()