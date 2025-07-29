"""
API Gateway Connectors module for MediaLake.

This module defines the ConnectorsConstruct class which sets up API Gateway endpoints
and associated Lambda functions for managing media connectors. It handles:
- S3 bucket connections
- DynamoDB table management
- IAM roles and permissions
- API Gateway integration
- Lambda function configuration
"""

from dataclasses import dataclass

from aws_cdk import Stack
from aws_cdk import aws_apigateway as api_gateway
from aws_cdk import aws_cognito as cognito
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_secretsmanager as secrets_manager
from constructs import Construct

from medialake_constructs.api_gateway.api_gateway_utils import add_cors_options_method
from medialake_constructs.shared_constructs.dynamodb import DynamoDB, DynamoDBProps
from medialake_constructs.shared_constructs.lambda_base import Lambda, LambdaConfig


@dataclass
class RolesApiProps:
    x_origin_verify_secret: secrets_manager.Secret
    api_resource: api_gateway.IResource
    cognito_authorizer: api_gateway.IAuthorizer
    cognito_user_pool: cognito.UserPool


class RolesApi(Construct):
    """
    Roles API API Gateway deployment
    """

    def __init__(
        self,
        scope: Construct,
        constructor_id: str,
        props: RolesApiProps,
    ) -> None:
        super().__init__(scope, constructor_id)
        from config import config

        # Get the current account ID
        Stack.of(self).account

        self._roles_table = DynamoDB(
            self,
            "RolesTable",
            props=DynamoDBProps(
                name=f"{config.resource_prefix}-roles-table-{config.environment}",
                partition_key_name="id",
                partition_key_type=dynamodb.AttributeType.STRING,
            ),
        )

        # Create connectors resource
        roles_resource = props.api_resource.add_resource("roles")

        # Add role_id path parameter resource
        roles_role_resource = roles_resource.add_resource("role")

        roles_role_id_resources = roles_role_resource.add_resource("{role_id}")

        roles_get_lambda = Lambda(
            self,
            "RolesGetLambda",
            config=LambdaConfig(
                name="get_roles",
                entry="lambdas/api/roles/get_roles",
                environment_variables={
                    "X_ORIGIN_VERIFY_SECRET_ARN": (
                        props.x_origin_verify_secret.secret_arn
                    ),
                    "MEDIALAKE_ROLES_TABLE": self._roles_table.table_arn,
                    "COGNITO_USER_POOL_ID": props.cognito_user_pool.user_pool_id,
                },
            ),
        )

        # Add CORS support
        add_cors_options_method(roles_resource)
        add_cors_options_method(roles_role_resource)
        add_cors_options_method(roles_role_id_resources)
