"""
API Gateway settings module for MediaLake.

This module defines the settingsConstruct class which sets up API Gateway endpoints
and associated Lambda functions for managing media settings. It handles:
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
    aws_iam as iam,
    aws_secretsmanager as secretsmanager,
    aws_cognito as cognito,
    Stack,
)
from medialake_constructs.shared_constructs.lam_deployment import LambdaDeployment

from medialake_constructs.shared_constructs.lambda_base import (
    Lambda,
    LambdaConfig,
)

from medialake_constructs.shared_constructs.dynamodb import (
    DynamoDB,
    DynamoDBProps,
)


@dataclass
class SettingsConstructProps:
    """Configuration for Lambda function creation."""

    x_origin_verify_secret: secretsmanager.Secret
    api_resource: api_gateway.IResource
    cognito_authorizer: api_gateway.IAuthorizer
    cognito_user_pool: cognito.UserPool
    cognito_app_client: str


class SettingsConstruct(Construct):
    """
    AWS CDK Construct for managing MediaLake settings users infrastructure.
    This construct creates and configures:
    - API Gateway endpoints for connector management
    - Lambda functions for handling connector operations
    - DynamoDB tables for storing connector metadata
    - IAM roles and policies for secure access
    - S3 bucket notifications and event handling
    - Integration with EventBridge for event processing

    Attributes:
        lambda_deployment (LambdaDeployment): Handles deployment of Lambda functions

    Args:
        scope (Construct): The scope in which to define this construct
        constructor_id (str): The scoped construct ID
        api_resource (apigateway.IResource): The API Gateway resource to attach to
        cognito_authorizer (apigateway.IAuthorizer): Cognito authorizer for API endpoints
        x_origin_verify_secret (secretsmanager.Secret): Secret for origin verification
        ingest_event_bus (events.EventBus): EventBus for ingestion events
        iac_assets_bucket (s3.Bucket): S3 bucket for infrastructure assets
        props (settingsProps): Configuration properties for the construct
    """

    def __init__(
        self,
        scope: Construct,
        constructor_id: str,
        props: SettingsConstructProps,
    ) -> None:
        super().__init__(scope, constructor_id)

        # Get the current account ID
        account_id = Stack.of(self).account

        # Create settings resource
        settings_resource = props.api_resource.root.add_resource("settings")
        settings_users_resource = settings_resource.add_resource("users")
        settings_users_userid_resource = settings_users_resource.add_resource("{id}")
        settings_users_user_resource = settings_users_resource.add_resource("user")
        settings_users_user_userid_resource = settings_users_user_resource.add_resource(
            "{id}"
        )

        settings_roles_resource = settings_resource.add_resource("roles")
        settings_roles_role_resource = settings_roles_resource.add_resource("role")

        settings_users_get_lambda = Lambda(
            self,
            "SettingsUsersGetLambda",
            config=LambdaConfig(
                name="settings_users_get_lambda",
                entry="lambdas/api/settings/users/get_users",
                environment_variables={
                    "X_ORIGIN_VERIFY_SECRET_ARN": (
                        props.x_origin_verify_secret.secret_arn
                    ),
                    "USER_POOL_ID": (props.cognito_user_pool.user_pool_id),
                },
            ),
        )

        settings_users_get_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["cognito-idp:ListUsers", "cognito-idp:AdminGetUser"],
                resources=[props.cognito_user_pool.user_pool_arn],
            )
        )

        settings_users_resource.add_method(
            "GET",
            api_gateway.LambdaIntegration(settings_users_get_lambda.function),
            authorization_type=api_gateway.AuthorizationType.COGNITO,
            authorizer=props.cognito_authorizer,
        )

        settings_roles_get_lambda = Lambda(
            self,
            "SettingsRolesGetLambda",
            config=LambdaConfig(
                name="settings_roles_get_lambda",
                entry="lambdas/api/settings/roles/get_roles",
                environment_variables={
                    "X_ORIGIN_VERIFY_SECRET_ARN": (
                        props.x_origin_verify_secret.secret_arn
                    ),
                    "USER_POOL_ID": (props.cognito_user_pool.user_pool_id),
                },
            ),
        )

        settings_roles_get_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "cognito-idp:ListUsers",
                    "cognito-idp:AdminGetUser",
                    "cognito-idp:ListGroups",
                    "cognito-idp:GetGroup",
                ],
                resources=[props.cognito_user_pool.user_pool_arn],
            )
        )

        settings_roles_resource.add_method(
            "GET",
            api_gateway.LambdaIntegration(settings_roles_get_lambda.function),
            authorization_type=api_gateway.AuthorizationType.COGNITO,
            authorizer=props.cognito_authorizer,
        )

        settings_user_del_lambda = Lambda(
            self,
            "SettingsUsersUserDelLambda",
            config=LambdaConfig(
                name="settings_users_user_del_lambda",
                iam_role_name="settings_users_user_del_lambda_role",
                entry="lambdas/api/settings/users/rp_userid/del_user",
                environment_variables={
                    "X_ORIGIN_VERIFY_SECRET_ARN": (
                        props.x_origin_verify_secret.secret_arn
                    ),
                    "USER_POOL_ID": (props.cognito_user_pool.user_pool_id),
                },
            ),
        )

        settings_user_del_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "cognito-idp:AdminDeleteUser",
                ],
                resources=[props.cognito_user_pool.user_pool_arn],
            )
        )

        settings_users_userid_resource.add_method(
            "DELETE",
            api_gateway.LambdaIntegration(settings_user_del_lambda.function),
            authorization_type=api_gateway.AuthorizationType.COGNITO,
            authorizer=props.cognito_authorizer,
        )

        settings_user_put_lambda = Lambda(
            self,
            "SettingsUserPutLambda",
            config=LambdaConfig(
                name="settings_users_user_put_lambda",
                iam_role_name="settings_users_user_put_lambda_role",
                entry="lambdas/api/settings/users/rp_userid/put_user",
                environment_variables={
                    "X_ORIGIN_VERIFY_SECRET_ARN": (
                        props.x_origin_verify_secret.secret_arn
                    ),
                    "USER_POOL_ID": (props.cognito_user_pool.user_pool_id),
                },
            ),
        )

        settings_user_put_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "cognito-idp:AdminUpdateUserAttributes",
                    "cognito-idp:AdminGetUser",
                    "cognito-idp:AdminAddUserToGroup",
                    "cognito-idp:AdminRemoveUserFromGroup",
                    "cognito-idp:AdminListGroupsForUser",
                ],
                resources=[props.cognito_user_pool.user_pool_arn],
            )
        )

        settings_users_userid_resource.add_method(
            "PUT",
            api_gateway.LambdaIntegration(settings_user_put_lambda.function),
            authorization_type=api_gateway.AuthorizationType.COGNITO,
            authorizer=props.cognito_authorizer,
        )

        settings_users_user_userid_put_lambda = Lambda(
            self,
            "SettingsUsersUserUseridPutLambda",
            config=LambdaConfig(
                name="user_put",
                iam_role_name="user_put",
                entry="lambdas/api/settings/users/user/rp_userid/get_userid",
                environment_variables={
                    "X_ORIGIN_VERIFY_SECRET_ARN": (
                        props.x_origin_verify_secret.secret_arn
                    ),
                    "USER_POOL_ID": (props.cognito_user_pool.user_pool_id),
                },
            ),
        )

        settings_users_user_userid_put_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "cognito-idp:AdminUpdateUserAttributes",
                    "cognito-idp:AdminGetUser",
                    "cognito-idp:AdminAddUserToGroup",
                    "cognito-idp:AdminRemoveUserFromGroup",
                    "cognito-idp:AdminListGroupsForUser",
                ],
                resources=[props.cognito_user_pool.user_pool_arn],
            )
        )

        settings_users_user_userid_resource.add_method(
            "GET",
            api_gateway.LambdaIntegration(settings_user_put_lambda.function),
            authorization_type=api_gateway.AuthorizationType.COGNITO,
            authorizer=props.cognito_authorizer,
        )

        settings_users_user_post_lambda = Lambda(
            self,
            "SettingsUsersUserPostLambda",
            config=LambdaConfig(
                name="settings_users_user_post_lambda",
                entry="lambdas/api/settings/users/user/post_user",
                environment_variables={
                    "X_ORIGIN_VERIFY_SECRET_ARN": (
                        props.x_origin_verify_secret.secret_arn
                    ),
                    "USER_POOL_ID": (props.cognito_user_pool.user_pool_id),
                    "APP_CLIENT_ID": (props.cognito_app_client),
                },
            ),
        )

        settings_users_user_post_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "cognito-idp:AdminCreateUser",
                    "cognito-idp:AdminUpdateUserAttributes",
                    "cognito-idp:AdminGetUser",
                    "cognito-idp:AdminAddUserToGroup",
                    "cognito-idp:AdminListGroupsForUser",
                    "cognito-idp:ListGroups",
                    "cognito-idp:AdminSetUserPassword",
                    "cognito-idp:AdminInitiateAuth",
                ],
                resources=[props.cognito_user_pool.user_pool_arn],
            )
        )

        settings_users_user_resource.add_method(
            "POST",
            api_gateway.LambdaIntegration(settings_users_user_post_lambda.function),
            authorization_type=api_gateway.AuthorizationType.COGNITO,
            authorizer=props.cognito_authorizer,
        )
