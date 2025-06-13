from aws_cdk import (
    Stack,
    aws_dynamodb as dynamodb,
    aws_secretsmanager as secretsmanager,
    aws_cognito as cognito,
    CfnOutput,
    RemovalPolicy,
    SecretValue,
)
from constructs import Construct

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
        secret_value: str = "",  # ✅ Ajout ici
        **kwargs
    ):
        super().__init__(scope, id, **kwargs)

        # DynamoDB Table
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

        # Secret Manager
        if create_secret:
            if not secret_value:
                raise ValueError("secret_value is required when create_secret is True")
            self.secret = secretsmanager.Secret(
                self, "Secret",
                secret_name=secret_name,
                description="Secret about microservice",
                secret_string_value=SecretValue.unsafe_plain_text(secret_value)
            )
        else:
            self.secret = secretsmanager.Secret.from_secret_name_v2(
                self, "ImportedSecret", secret_name
            )

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
