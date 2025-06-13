from aws_cdk import (
    Stack,
    aws_lambda as _lambda,
    aws_apigatewayv2 as apigwv2,
    aws_cognito as cognito,
    aws_iam as iam,
    Duration,
    CfnOutput,
    aws_ecr as ecr
)
from constructs import Construct
import boto3
import os

def get_cognito_client_ids(user_pool_id):
    client = boto3.client('cognito-idp')
    paginator = client.get_paginator('list_user_pool_clients')
    client_ids = []
    for page in paginator.paginate(UserPoolId=user_pool_id):
        for user_pool_client in page['UserPoolClients']:
            client_ids.append(user_pool_client['ClientId'])
    return client_ids


class LambdasStack(Stack):
    def __init__(
        self,
        scope: Construct,
        id: str,
        *,
        table_name: str,
        user_pool_id: str,
        api_name: str,
        **kwargs
    ):
        super().__init__(scope, id, **kwargs)

        lambda_env = {
            "TABLE": table_name,
            "REGION": self.region,
            "COGNITO_POOL_ID": user_pool_id,
        }

        repo = ecr.Repository.from_repository_name(self, "LambdaRepo", os.environ["AWS_ECR_FOLDER"])

        handlers = {
            "list_template_python": "src.list.handler.list",
            "post_template_python": "src.post.handler.create",
            "put_template_python": "src.put.handler.edit",
            "get_template_python": "src.get.handler.get",
            "delete_template_python": "src.delete.handler.delete",
        }

        lambdas = {}
        for name, handler in handlers.items():
            lambdas[name] = _lambda.DockerImageFunction(
                self, name,
                code=_lambda.DockerImageCode.from_ecr(
                    repository=repo,
                    tag_or_digest="latest",
                    cmd=[handler],
                ),
                environment=lambda_env,
                timeout=Duration.seconds(30),
                # Add more memory if needed for dependencies
                memory_size=512,
            )

            # More specific IAM permissions
            lambdas[name].add_to_role_policy(iam.PolicyStatement(
                actions=[
                    "dynamodb:GetItem",
                    "dynamodb:PutItem", 
                    "dynamodb:UpdateItem",
                    "dynamodb:DeleteItem",
                    "dynamodb:Query",
                    "dynamodb:Scan"
                ],
                resources=[f"arn:aws:dynamodb:{self.region}:{self.account}:table/{table_name}"]
            ))
            
            lambdas[name].add_to_role_policy(iam.PolicyStatement(
                actions=["cognito-idp:GetUser"],
                resources=[f"arn:aws:cognito-idp:{self.region}:{self.account}:userpool/{user_pool_id}"]
            ))

        user_pool_client_ids = get_cognito_client_ids(user_pool_id)

        http_api = apigwv2.HttpApi(
            self, "HttpApi",
            api_name=api_name,
            cors_preflight=apigwv2.CorsPreflightOptions(
                allow_origins=["*"],  # Configure appropriately for production
                allow_methods=[apigwv2.CorsHttpMethod.ANY],
                allow_headers=["*"]
            )
        )

        cfn_authorizer = apigwv2.CfnAuthorizer(
            self, "CognitoAuthorizer",
            api_id=http_api.http_api_id,
            authorizer_type="JWT",
            identity_source=["$request.header.Authorization"],
            name="CognitoAuthorizer",
            jwt_configuration=apigwv2.CfnAuthorizer.JWTConfigurationProperty(
                audience=user_pool_client_ids,
                issuer=f"https://cognito-idp.{self.region}.amazonaws.com/{user_pool_id}"
            )
        )

        integrations_map = {}
        for key, lambda_fn in lambdas.items():
            lambda_fn.grant_invoke(iam.ServicePrincipal("apigateway.amazonaws.com"))
            integration = apigwv2.CfnIntegration(
                self, f"{key}Integration",
                api_id=http_api.http_api_id,
                integration_type="AWS_PROXY",
                integration_uri=f"arn:aws:apigateway:{self.region}:lambda:path/2015-03-31/functions/{lambda_fn.function_arn}/invocations",
                integration_method="POST",
                payload_format_version="2.0"
            )
            integrations_map[key] = integration

        def create_route(id: str, method: str, path: str, integration_key: str, scopes=None):
            apigwv2.CfnRoute(
                self, f"{id}Route",
                api_id=http_api.http_api_id,
                route_key=f"{method} {path}",
                target=f"integrations/{integrations_map[integration_key].ref}",
                authorization_type="JWT",
                authorizer_id=cfn_authorizer.ref,
                authorization_scopes=scopes
            )

        create_route("List", "GET", "/", "list_template_python", scopes=["DEMO/PYTHONTEMPLATECDK.READ"])
        create_route("Post", "POST", "/", "post_template_python", scopes=["DEMO/PYTHONTEMPLATECDK.CREATE"])
        create_route("Get", "GET", "/{id}", "get_template_python", scopes=["DEMO/PYTHONTEMPLATECDK.READ"])
        create_route("Put", "PUT", "/{id}", "put_template_python", scopes=["DEMO/PYTHONTEMPLATECDK.UPDATE"])
        create_route("Delete", "DELETE", "/{id}", "delete_template_python", scopes=["DEMO/PYTHONTEMPLATECDK.DELETE"])

        CfnOutput(
            self, "HttpApiEndpoint",
            value=http_api.url or "unknown",
            export_name=f"{api_name}-HttpApiEndpoint"
        )
        
        CfnOutput(
            self, "HttpApiId",
            value=http_api.http_api_id,
            export_name=f"{api_name}-HttpApiId"
        )