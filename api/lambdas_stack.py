from aws_cdk import (
    Stack,
    aws_lambda as _lambda,
    aws_apigatewayv2 as apigwv2,
    aws_apigatewayv2_alpha as apigwv2_alpha,
    aws_apigatewayv2_integrations_alpha as integrations_alpha,
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

        image_tag = os.environ.get("IMAGE_TAG", "latest")

        repo = ecr.Repository.from_repository_name(self, "LambdaRepo", os.environ["AWS_ECR_FOLDER"])

        # WebSocket handlers: connect, disconnect, default, and a custom route
        handlers = {
            "connect": "src.connect.handler.connect",
            "disconnect": "src.disconnect.handler.disconnect",
            "default": "src.default.handler.default",
            "send_message": "src.send_message.handler.send_message",
            "create": "src.post.handler.create",
            "update": "src.put.handler.edit",
            "delete": "src.delete.handler.delete",
            "get": "src.get.handler.get",
            "list": "src.get.handler.list"
        }

        lambdas = {}
        for name, handler in handlers.items():
            lambdas[name] = _lambda.DockerImageFunction(
                self, name,
                code=_lambda.DockerImageCode.from_ecr(
                    repository=repo,
                    tag_or_digest=image_tag,
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

        # WebSocket API
        ws_api = apigwv2_alpha.WebSocketApi(
            self, "WebSocketApi",
            api_name=f"{api_name}-ws",
            connect_route_options=apigwv2_alpha.WebSocketRouteOptions(
                integration=integrations_alpha.WebSocketLambdaIntegration(
                    "ConnectIntegration", lambdas["connect"]
                )
            ),
            disconnect_route_options=apigwv2_alpha.WebSocketRouteOptions(
                integration=integrations_alpha.WebSocketLambdaIntegration(
                    "DisconnectIntegration", lambdas["disconnect"]
                )
            ),
            default_route_options=apigwv2_alpha.WebSocketRouteOptions(
                integration=integrations_alpha.WebSocketLambdaIntegration(
                    "DefaultIntegration", lambdas["default"]
                )
            ),
        )

        # Custom WebSocket routes for each handler
        apigwv2_alpha.WebSocketRoute(
            self, "SendMessageRoute",
            web_socket_api=ws_api,
            route_key="sendMessage",
            integration=integrations_alpha.WebSocketLambdaIntegration(
                "SendMessageIntegration", lambdas["send_message"]
            )
        )
        apigwv2_alpha.WebSocketRoute(
            self, "CreateRoute",
            web_socket_api=ws_api,
            route_key="create",
            integration=integrations_alpha.WebSocketLambdaIntegration(
                "CreateIntegration", lambdas["create"]
            )
        )
        apigwv2_alpha.WebSocketRoute(
            self, "UpdateRoute",
            web_socket_api=ws_api,
            route_key="update",
            integration=integrations_alpha.WebSocketLambdaIntegration(
                "UpdateIntegration", lambdas["update"]
            )
        )
        apigwv2_alpha.WebSocketRoute(
            self, "DeleteRoute",
            web_socket_api=ws_api,
            route_key="delete",
            integration=integrations_alpha.WebSocketLambdaIntegration(
                "DeleteIntegration", lambdas["delete"]
            )
        )
        apigwv2_alpha.WebSocketRoute(
            self, "GetRoute",
            web_socket_api=ws_api,
            route_key="get",
            integration=integrations_alpha.WebSocketLambdaIntegration(
                "GetIntegration", lambdas["get"]
            )
        )
        apigwv2_alpha.WebSocketRoute(
            self, "ListRoute",
            web_socket_api=ws_api,
            route_key="list",
            integration=integrations_alpha.WebSocketLambdaIntegration(
                "ListIntegration", lambdas["list"]
            )
        )

        ws_stage = apigwv2_alpha.WebSocketStage(
            self, "WebSocketStage",
            web_socket_api=ws_api,
            stage_name="prod",
            auto_deploy=True
        )

        CfnOutput(
            self, "WebSocketApiEndpoint",
            value=ws_stage.url,
            export_name=f"{api_name}-WebSocketApiEndpoint"
        )
