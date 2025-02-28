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
    aws_dynamodb as dynamodb,
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
        
        # Create system settings resource and DynamoDB table
        system_resource = settings_resource.add_resource("system")
        
        # Create DynamoDB table for system settings
        self.system_settings_table = DynamoDB(
            self,
            "SystemSettingsTable",
            props=DynamoDBProps(
                name=f"medialake-system-settings",
                partition_key_name="PK",
                partition_key_type=dynamodb.AttributeType.STRING,
                sort_key_name="SK",
                sort_key_type=dynamodb.AttributeType.STRING,
                stream=dynamodb.StreamViewType.NEW_AND_OLD_IMAGES,
                point_in_time_recovery=True,
            ),
        )
        
        # GET /settings/system
        self._get_system_settings_handler = Lambda(
            self,
            "GetSystemSettingsHandler",
            config=LambdaConfig(
                name="get_system_settings",
                entry="lambdas/api/settings/system/get_system_settings",
                environment_variables={
                    "X_ORIGIN_VERIFY_SECRET_ARN": props.x_origin_verify_secret.secret_arn,
                    "SYSTEM_SETTINGS_TABLE": self.system_settings_table.table_name,
                    "METRICS_NAMESPACE": "MediaLake",
                },
            ),
        )

        self.system_settings_table.table.grant_read_data(
            self._get_system_settings_handler.function
        )

        system_resource.add_method(
            "GET",
            api_gateway.LambdaIntegration(self._get_system_settings_handler.function),
            authorization_type=api_gateway.AuthorizationType.COGNITO,
            authorizer=props.cognito_authorizer,
        )
        
        # Create search provider resource
        search_resource = system_resource.add_resource("search")

        # GET /settings/system/search
        self._get_search_provider_handler = Lambda(
            self,
            "GetSearchProviderHandler",
            config=LambdaConfig(
                name="get_search_provider",
                entry="lambdas/api/settings/system/search/get_search",
                environment_variables={
                    "X_ORIGIN_VERIFY_SECRET_ARN": props.x_origin_verify_secret.secret_arn,
                    "SYSTEM_SETTINGS_TABLE": self.system_settings_table.table_name,
                    "METRICS_NAMESPACE": "MediaLake",
                },
            ),
        )

        self.system_settings_table.table.grant_read_data(
            self._get_search_provider_handler.function
        )

        search_resource.add_method(
            "GET",
            api_gateway.LambdaIntegration(self._get_search_provider_handler.function),
            authorization_type=api_gateway.AuthorizationType.COGNITO,
            authorizer=props.cognito_authorizer,
        )

        # POST /settings/system/search
        self._post_search_provider_handler = Lambda(
            self,
            "PostSearchProviderHandler",
            config=LambdaConfig(
                name="post_search_provider",
                entry="lambdas/api/settings/system/search/post_search",
                environment_variables={
                    "X_ORIGIN_VERIFY_SECRET_ARN": props.x_origin_verify_secret.secret_arn,
                    "SYSTEM_SETTINGS_TABLE": self.system_settings_table.table_name,
                    "METRICS_NAMESPACE": "MediaLake",
                },
            ),
        )

        self.system_settings_table.table.grant_write_data(
            self._post_search_provider_handler.function
        )
        
        # Add permissions to access Secrets Manager
        self._post_search_provider_handler.function.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "secretsmanager:CreateSecret",
                    "secretsmanager:PutSecretValue",
                    "secretsmanager:UpdateSecret",
                    "secretsmanager:DeleteSecret",
                    "secretsmanager:TagResource",
                ],
                resources=["*"],  # You might want to restrict this to specific secrets
            )
        )

        search_resource.add_method(
            "POST",
            api_gateway.LambdaIntegration(self._post_search_provider_handler.function),
            authorization_type=api_gateway.AuthorizationType.COGNITO,
            authorizer=props.cognito_authorizer,
        )

        # PUT /settings/system/search
        self._put_search_provider_handler = Lambda(
            self,
            "PutSearchProviderHandler",
            config=LambdaConfig(
                name="put_search_provider",
                entry="lambdas/api/settings/system/search/put_search",
                environment_variables={
                    "X_ORIGIN_VERIFY_SECRET_ARN": props.x_origin_verify_secret.secret_arn,
                    "SYSTEM_SETTINGS_TABLE": self.system_settings_table.table_name,
                    "METRICS_NAMESPACE": "MediaLake",
                },
            ),
        )

        self.system_settings_table.table.grant_write_data(
            self._put_search_provider_handler.function
        )
        
        # Add permissions to access Secrets Manager
        self._put_search_provider_handler.function.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "secretsmanager:GetSecretValue",
                    "secretsmanager:UpdateSecret",
                    "secretsmanager:PutSecretValue",
                    "secretsmanager:CreateSecret",
                ],
                resources=["*"],  # You might want to restrict this to specific secrets
            )
        )

        search_resource.add_method(
            "PUT",
            api_gateway.LambdaIntegration(self._put_search_provider_handler.function),
            authorization_type=api_gateway.AuthorizationType.COGNITO,
            authorizer=props.cognito_authorizer,
        )
        
        # Create users resource
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

        settings_users_user_userid_get_lambda = Lambda(
            self,
            "SettingsUsersUserUseridGetLambda",
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

        settings_users_user_userid_get_lambda.function.add_to_role_policy(
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
            api_gateway.LambdaIntegration(
                settings_users_user_userid_get_lambda.function
            ),
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
        
    @property
    def system_settings_table_name(self) -> str:
        return self.system_settings_table.table_name

    @property
    def system_settings_table_arn(self) -> str:
        return self.system_settings_table.table_arn

    @property
    def get_system_settings_handler(self) -> Lambda:
        return self._get_system_settings_handler

    @property
    def get_search_provider_handler(self) -> Lambda:
        return self._get_search_provider_handler

    @property
    def post_search_provider_handler(self) -> Lambda:
        return self._post_search_provider_handler

    @property
    def put_search_provider_handler(self) -> Lambda:
        return self._put_search_provider_handler
