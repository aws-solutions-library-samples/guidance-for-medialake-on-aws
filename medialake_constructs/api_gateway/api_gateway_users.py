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
from constructs import Construct
from aws_cdk import (
    aws_apigateway as api_gateway,
    aws_dynamodb as dynamodb,
    aws_iam as iam,
    aws_cognito as cognito,
    aws_secretsmanager as secrets_manager,
    Stack,
)

from medialake_constructs.shared_constructs.lambda_base import (
    Lambda,
    LambdaConfig,
)
from medialake_constructs.shared_constructs.dynamodb import (
    DynamoDB,
    DynamoDBProps,
)


@dataclass
class UsersApiProps:
    x_origin_verify_secret: secrets_manager.Secret
    api_resource: api_gateway.IResource
    cognito_authorizer: api_gateway.IAuthorizer
    cognito_user_pool: cognito.UserPool


class UsersApi(Construct):
    """
    Users API API Gateway deployment
    """

    def __init__(
        self,
        scope: Construct,
        constructor_id: str,
        props: UsersApiProps,
    ) -> None:
        super().__init__(scope, constructor_id)

        # Get the current account ID
        account_id = Stack.of(self).account

        self._users_table = DynamoDB(
            self,
            "UsersTable",
            props=DynamoDBProps(
                name=f"medialake_users_table",
                partition_key_name="id",
                partition_key_type=dynamodb.AttributeType.STRING,
            ),
        )

        # Create connectors resource
        users_resource = props.api_resource.root.add_resource("users")

        # Add connector_id path parameter resource
        user = users_resource.add_resource("user")

        user_id_resource = user.add_resource("{user_id}")

        user_id_get_lambda = Lambda(
            self,
            "UsersUserGetLambda",
            config=LambdaConfig(
                name="userid_get_lambda",
                entry="lambdas/api/users/user/rp_userid/get_userid",
                environment_variables={
                    "X_ORIGIN_VERIFY_SECRET_ARN": (
                        props.x_origin_verify_secret.secret_arn
                    ),
                    "MEDIALAKE_USER_TABLE": self._users_table.table_arn,
                    "COGNITO_USER_POOL_ID": props.cognito_user_pool.user_pool_id,
                },
            ),
        )

        self._users_table.table.grant_read_data(user_id_get_lambda.function)
        user_id_get_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "cognito-idp:AdminGetUser",
                    "cognito-idp:GetUser",
                    "cognito-idp:ListUsers",
                    "cognito-idp:ListUsersInGroup",
                    "cognito-idp:ListGroups",
                    "cognito-idp:AdminListGroupsForUser",
                    "cognito-idp:ListUserPoolClients",
                    "cognito-idp:ListUserPools",
                ],
                resources=[
                    props.cognito_user_pool.user_pool_arn,
                ],
            )
        )

        api_gateway_get_user_id_integration = api_gateway.LambdaIntegration(
            user_id_get_lambda.function,
            request_templates={
                "application/json": '{ "user_id": "$input.params(\'user_id\')" }'
            },
        )

        user_id_resource.add_method(
            "GET",
            api_gateway_get_user_id_integration,
            authorization_type=api_gateway.AuthorizationType.COGNITO,
            authorizer=props.cognito_authorizer,
        )
