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

from aws_cdk import Duration, Stack
from aws_cdk import aws_apigateway as api_gateway
from aws_cdk import aws_cognito as cognito
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_iam as iam
from aws_cdk import aws_secretsmanager as secrets_manager
from constructs import Construct

from medialake_constructs.api_gateway.api_gateway_utils import add_cors_options_method
from medialake_constructs.shared_constructs.dynamodb import DynamoDB, DynamoDBProps
from medialake_constructs.shared_constructs.lambda_base import Lambda, LambdaConfig


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

        from config import config

        # Get the current account ID
        Stack.of(self).account

        self._users_table = DynamoDB(
            self,
            "UsersTable",
            props=DynamoDBProps(
                name=f"{config.resource_prefix}_users_table_{config.environment}",
                partition_key_name="id",
                partition_key_type=dynamodb.AttributeType.STRING,
            ),
        )

        # Create connectors resource
        users_resource = props.api_resource.add_resource("users")

        # Add connector_id path parameter resource
        users_user_resource = users_resource.add_resource("user")

        users_user_id_resources = users_user_resource.add_resource("{user_id}")

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

        users_user_id_resources.add_cors_preflight(
            allow_origins=["http://localhost:5173"],
            allow_methods=["GET", "PUT", "OPTIONS", "DELETE", "POST"],
            allow_headers=[
                "Content-Type",
                "Authorization",
                "X-Amz-Date",
                "X-Api-Key",
                "X-Amz-Security-Token",
            ],
            allow_credentials=True,
            max_age=Duration.seconds(300),
        )

        users_user_id_resources.add_method(
            "GET",
            api_gateway_get_user_id_integration,
            authorization_type=api_gateway.AuthorizationType.COGNITO,
            authorizer=props.cognito_authorizer,
        )

        users_user_id_put_lambda = Lambda(
            self,
            "UsersUserIdPutLambda",
            config=LambdaConfig(
                name="users_user_id_put",
                entry="lambdas/api/users/user/rp_userid/put_userid",
                environment_variables={
                    "X_ORIGIN_VERIFY_SECRET_ARN": (
                        props.x_origin_verify_secret.secret_arn
                    ),
                    "MEDIALAKE_USER_TABLE": self._users_table.table_arn,
                    "COGNITO_USER_POOL_ID": props.cognito_user_pool.user_pool_id,
                },
            ),
        )

        api_gateway_put_users_user_id_integration = api_gateway.LambdaIntegration(
            users_user_id_put_lambda.function,
            request_templates={
                "application/json": '{ "user_id": "$input.params(\'user_id\')" }'
            },
        )

        self._users_table.table.grant_read_data(users_user_id_put_lambda.function)
        users_user_id_put_lambda.function.add_to_role_policy(
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
                    "cognito-idp:AdminCreateUser",
                    "cognito-idp:AdminAddUserToGroup",
                    "cognito-idp:AdminUpdateUserAttributes",
                    "cognito-idp:AdminSetUserPassword",
                    "cognito-idp:AdminInitiateAuth",
                    "cognito-idp:AdminRespondToAuthChallenge",
                    "cognito-idp:AdminDeleteUser",
                    "cognito-idp:AdminDisableUser",
                    "cognito-idp:AdminEnableUser",
                    "cognito-idp:AdminRemoveUserFromGroup",
                    "cognito-idp:AdminResetUserPassword",
                    "cognito-idp:AdminUserGlobalSignOut",
                ],
                resources=[
                    props.cognito_user_pool.user_pool_arn,
                ],
            )
        )

        users_user_id_resources.add_method(
            "PUT",
            api_gateway_put_users_user_id_integration,
            authorization_type=api_gateway.AuthorizationType.COGNITO,
            authorizer=props.cognito_authorizer,
        )

        users_user_post_lambda = Lambda(
            self,
            "UsersUserPostLambda",
            config=LambdaConfig(
                name="users_user_post",
                entry="lambdas/api/users/user/post_user",
                environment_variables={
                    "X_ORIGIN_VERIFY_SECRET_ARN": (
                        props.x_origin_verify_secret.secret_arn
                    ),
                    "MEDIALAKE_USER_TABLE": self._users_table.table_arn,
                    "COGNITO_USER_POOL_ID": props.cognito_user_pool.user_pool_id,
                },
            ),
        )

        # Add CORS preflight for POST method
        users_user_resource.add_cors_preflight(
            allow_origins=["http://localhost:5173"],
            allow_methods=["GET", "PUT", "OPTIONS", "DELETE", "POST"],
            allow_headers=[
                "Content-Type",
                "Authorization",
                "X-Amz-Date",
                "X-Api-Key",
                "X-Amz-Security-Token",
            ],
            allow_credentials=True,
            max_age=Duration.seconds(300),
        )

        users_user_resource.add_method(
            "POST",
            api_gateway.LambdaIntegration(users_user_post_lambda.function),
            authorization_type=api_gateway.AuthorizationType.COGNITO,
            authorizer=props.cognito_authorizer,
        )

        self._users_table.table.grant_read_data(users_user_post_lambda.function)
        users_user_post_lambda.function.add_to_role_policy(
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
                    "cognito-idp:AdminCreateUser",
                    "cognito-idp:AdminAddUserToGroup",
                    "cognito-idp:AdminUpdateUserAttributes",
                    "cognito-idp:AdminSetUserPassword",
                    "cognito-idp:AdminInitiateAuth",
                    "cognito-idp:AdminRespondToAuthChallenge",
                ],
                resources=[
                    props.cognito_user_pool.user_pool_arn,
                ],
            )
        )

        users_user_id_disableuser_resource = users_user_id_resources.add_resource(
            "disableuser"
        )

        users_user_id_disableuser_post_lambda = Lambda(
            self,
            "UsersUserDisableUserPostLambda",
            config=LambdaConfig(
                name="users_user_id_disableuser_post",
                entry="lambdas/api/users/user/rp_userid/disableuser/post_disableuser",
                environment_variables={
                    "X_ORIGIN_VERIFY_SECRET_ARN": (
                        props.x_origin_verify_secret.secret_arn
                    ),
                    "MEDIALAKE_USER_TABLE": self._users_table.table_arn,
                    "COGNITO_USER_POOL_ID": props.cognito_user_pool.user_pool_id,
                },
            ),
        )

        self._users_table.table.grant_read_data(
            users_user_id_disableuser_post_lambda.function
        )
        users_user_id_disableuser_post_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    # Read-only actions
                    "cognito-idp:AdminGetUser",
                    "cognito-idp:GetUser",
                    "cognito-idp:ListUsers",
                    "cognito-idp:AdminListGroupsForUser",
                    "cognito-idp:ListUserPoolClients",
                    "cognito-idp:ListUserPools",
                    # Disable user action
                    "cognito-idp:AdminDisableUser",
                ],
                resources=[
                    props.cognito_user_pool.user_pool_arn,
                ],
            )
        )

        api_post_users_user_id_disableuser_integration = api_gateway.LambdaIntegration(
            users_user_id_disableuser_post_lambda.function,
            request_templates={
                "application/json": '{ "user_id": "$input.params(\'user_id\')" }'
            },
        )

        users_user_id_disableuser_resource.add_method(
            "POST",
            api_post_users_user_id_disableuser_integration,
            authorization_type=api_gateway.AuthorizationType.COGNITO,
            authorizer=props.cognito_authorizer,
        )

        users_user_id_enableuser_resource = users_user_id_resources.add_resource(
            "enableuser"
        )

        users_user_id_enableuser_post_lambda = Lambda(
            self,
            "UsersUserEnableUserPostLambda",
            config=LambdaConfig(
                name="users_user_id_enableuser_post",
                entry="lambdas/api/users/user/rp_userid/enableuser/post_enableuser",
                environment_variables={
                    "X_ORIGIN_VERIFY_SECRET_ARN": (
                        props.x_origin_verify_secret.secret_arn
                    ),
                    "MEDIALAKE_USER_TABLE": self._users_table.table_arn,
                    "COGNITO_USER_POOL_ID": props.cognito_user_pool.user_pool_id,
                },
            ),
        )

        self._users_table.table.grant_read_data(
            users_user_id_enableuser_post_lambda.function
        )
        users_user_id_enableuser_post_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    # Read-only actions
                    "cognito-idp:AdminGetUser",
                    "cognito-idp:GetUser",
                    "cognito-idp:ListUsers",
                    "cognito-idp:ListUsersInGroup",
                    "cognito-idp:ListGroups",
                    "cognito-idp:AdminListGroupsForUser",
                    "cognito-idp:ListUserPoolClients",
                    "cognito-idp:ListUserPools",
                    # Enable user action
                    "cognito-idp:AdminEnableUser",
                ],
                resources=[
                    props.cognito_user_pool.user_pool_arn,
                ],
            )
        )

        api_post_users_user_id_enableuser_integration = api_gateway.LambdaIntegration(
            users_user_id_enableuser_post_lambda.function,
            request_templates={
                "application/json": '{ "user_id": "$input.params(\'user_id\')" }'
            },
        )

        users_user_id_enableuser_resource.add_method(
            "POST",
            api_post_users_user_id_enableuser_integration,
            authorization_type=api_gateway.AuthorizationType.COGNITO,
            authorizer=props.cognito_authorizer,
        )

        # Add CORS support
        add_cors_options_method(users_resource)
        # users_user_resource already has CORS configuration through add_cors_preflight
        # add_cors_options_method(users_user_resource)
        # users_user_id_resources already has CORS configuration through add_cors_preflight
        # add_cors_options_method(users_user_id_resources)
        add_cors_options_method(users_user_id_disableuser_resource)
        add_cors_options_method(users_user_id_enableuser_resource)
