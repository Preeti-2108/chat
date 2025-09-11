from aws_cdk import (
    Stack,
    aws_dynamodb as dynamodb,
    aws_secretsmanager as secretsmanager,
    aws_cognito as cognito,
    CfnOutput,
    RemovalPolicy,
    SecretValue,
    Duration,
)
from constructs import Construct
import os
import boto3

class ResourcesStack(Stack):
    def __init__(
        self,
        scope: Construct,
        id: str,
        *,
        table_name: str,
        secret_name: str,
        user_pool_id: str,
        create_table: bool = False,
        create_secret: bool = False,
        secret_value: str = "",
        create_connections_table: bool = False,
        **kwargs
    ):
        super().__init__(scope, id, **kwargs)

        # DynamoDB Table for main data
        if create_table:
            self.table = dynamodb.Table(
                self, "Table",
                table_name=table_name,
                partition_key=dynamodb.Attribute(name="id", type=dynamodb.AttributeType.STRING),
                removal_policy=RemovalPolicy.RETAIN,
                billing_mode=dynamodb.BillingMode.PROVISIONED,
                read_capacity=1,
                write_capacity=1
            )
        else:
            self.table = dynamodb.Table.from_table_name(
                self, "ImportedTable", table_name
            )

        # DynamoDB Table for WebSocket connections
        if create_connections_table:
            self.connections_table = dynamodb.Table(
                self, "ConnectionsTable",
                table_name=f"{table_name}-CONNECTIONS",
                partition_key=dynamodb.Attribute(name="connectionId", type=dynamodb.AttributeType.STRING),
                removal_policy=RemovalPolicy.DESTROY,  # Can be destroyed as it's temporary data
                billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
                time_to_live_attribute="ttl",  # Enable TTL for automatic cleanup
                stream=dynamodb.StreamViewType.NEW_AND_OLD_IMAGES  # Optional: for monitoring connections
            )
            
            # Add GSI for querying by userId
            self.connections_table.add_global_secondary_index(
                index_name="UserIdIndex",
                partition_key=dynamodb.Attribute(name="userId", type=dynamodb.AttributeType.STRING),
                projection_type=dynamodb.ProjectionType.ALL
            )
        else:
            self.connections_table = None

        # Always import the secret if it exists, create it if it doesn't
        # This avoids CDK conflicts between create vs import
        if not secret_value and create_secret:
            raise ValueError("secret_value is required when create_secret is True")
            
        if create_secret:
            # Create new secret
            self.secret = secretsmanager.Secret(
                self, "Secret",
                secret_name=secret_name,
                description="Secret about microservice",
                secret_string_value=SecretValue.unsafe_plain_text(secret_value),
                removal_policy=RemovalPolicy.RETAIN  # Prevent accidental deletion
            )
            print(f"🆕 Creating new secret: {secret_name}")
        else:
            # Import existing secret
            self.secret = secretsmanager.Secret.from_secret_name_v2(
                self, "ImportedSecret", secret_name
            )
            print(f"📥 Importing existing secret: {secret_name}")
            
        # Always update the secret value if provided (outside CDK construct creation)
        if secret_value and not create_secret:
            try:
                secrets_client = boto3.client('secretsmanager')
                secrets_client.update_secret(
                    SecretId=secret_name,
                    SecretString=secret_value
                )
                print(f"✅ Secret {secret_name} value updated successfully")
            except Exception as e:
                print(f"⚠️ Warning: Could not update secret {secret_name}: {e}")
                # Don't fail the deployment, just warn

        # Cognito User Pool (toujours importé)
        self.user_pool = cognito.UserPool.from_user_pool_id(
            self, "ImportedUserPool", user_pool_id
        )

        # Outputs
        CfnOutput(self, "TableArn", value=self.table.table_arn)
        CfnOutput(self, "TableName", value=self.table.table_name)
        CfnOutput(self, "SecretId", value=self.secret.secret_arn)
        CfnOutput(self, "SecretName", value=self.secret.secret_name)
        CfnOutput(self, "UserPoolId", value=self.user_pool.user_pool_id)
        
        # Connections table outputs (only if created)
        if self.connections_table:
            CfnOutput(self, "ConnectionsTableArn", value=self.connections_table.table_arn)
            CfnOutput(self, "ConnectionsTableName", value=self.connections_table.table_name)
        else:
            # Output placeholder values when table is not created
            CfnOutput(self, "ConnectionsTableArn", value="Table not created")
            CfnOutput(self, "ConnectionsTableName", value="Table not created")
