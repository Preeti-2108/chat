from aws_cdk import App
from resources_stack import ResourcesStack
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
secret_name = get_env_var("SECRET_NAME")
secret_value = get_env_var("SECRET_VALUE")
user_pool_id = get_env_var("COGNITO_POOL_ID")

resources_stack = ResourcesStack(
    app,
    f"{api_name}-resources-{version}",
    table_name=table_name,
    secret_name=secret_name,
    secret_value=secret_value,
    user_pool_id=user_pool_id,
)

app.synth()