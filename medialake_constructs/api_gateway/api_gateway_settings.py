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

from aws_cdk import Stack
from aws_cdk import aws_apigateway as api_gateway
from aws_cdk import aws_cognito as cognito
from aws_cdk import aws_iam as iam
from aws_cdk import aws_secretsmanager as secretsmanager
from constructs import Construct

from medialake_constructs.shared_constructs.lambda_base import Lambda, LambdaConfig

from .api_gateway_utils import add_cors_options_method


def apply_custom_authorization(method: api_gateway.Method, authorizer: str) -> None:
    """
    Apply custom authorization to an API Gateway method.

    Args:
        method: The API Gateway method to apply authorization to
        authorizer: The custom authorizer to use
    """
    # authorizer_id = Fn.ref(authorizer.node.default_child.logical_id)

    cfn_method = method.node.default_child
    cfn_method.authorization_type = "CUSTOM"
    cfn_method.authorizer_id = authorizer


@dataclass
class SettingsConstructProps:
    """Configuration for Lambda function creation."""

    x_origin_verify_secret: secretsmanager.Secret
    api_resource: api_gateway.RestApi
    authorizer: str
    cognito_user_pool: cognito.UserPool
    cognito_app_client: str
    system_settings_table_name: str
    system_settings_table_arn: str
    api_keys_table_name: str
    api_keys_table_arn: str


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
        authorizer (apigateway.IAuthorizer): Custom authorizer for API endpoints
        x_origin_verify_secret (secretsmanager.Secret): Secret for origin verification
        pipelines_event_bus (events.EventBus): EventBus for pipeline events
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
        Stack.of(self).account

        # Create settings resource
        settings_resource = props.api_resource.root.add_resource("settings")
        # Add OPTIONS method to support CORS
        add_cors_options_method(settings_resource)

        # Create system settings resource and DynamoDB table
        system_resource = settings_resource.add_resource("system")
        # Add OPTIONS method to support CORS
        add_cors_options_method(system_resource)

        # Get the existing system settings table by ARN
        self._system_settings_table_name = props.system_settings_table_name
        self._system_settings_table_arn = props.system_settings_table_arn

        # GET /settings/system
        self._get_system_settings_handler = Lambda(
            self,
            "GetSystemSettingsHandler",
            config=LambdaConfig(
                name="get_system_settings",
                entry="lambdas/api/settings/system/get_system_settings",
                environment_variables={
                    "X_ORIGIN_VERIFY_SECRET_ARN": props.x_origin_verify_secret.secret_arn,
                    "SYSTEM_SETTINGS_TABLE": self._system_settings_table_name,
                    "METRICS_NAMESPACE": "MediaLake",
                },
            ),
        )

        # Grant access to the existing system settings table
        self._get_system_settings_handler.function.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "dynamodb:GetItem",
                    "dynamodb:Query",
                    "dynamodb:Scan",
                ],
                resources=[self._system_settings_table_arn],
            )
        )

        system_settings_get = system_resource.add_method(
            "GET",
            api_gateway.LambdaIntegration(self._get_system_settings_handler.function),
        )
        apply_custom_authorization(system_settings_get, props.authorizer)

        # Create search provider resource
        search_resource = system_resource.add_resource("search")
        # Add OPTIONS method to support CORS
        add_cors_options_method(search_resource)

        # GET /settings/system/search
        self._get_search_provider_handler = Lambda(
            self,
            "GetSearchProviderHandler",
            config=LambdaConfig(
                name="get_search_provider",
                entry="lambdas/api/settings/system/search/get_search",
                environment_variables={
                    "X_ORIGIN_VERIFY_SECRET_ARN": props.x_origin_verify_secret.secret_arn,
                    "SYSTEM_SETTINGS_TABLE": self._system_settings_table_name,
                    "METRICS_NAMESPACE": "MediaLake",
                },
            ),
        )

        self._get_search_provider_handler.function.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "dynamodb:GetItem",
                    "dynamodb:Query",
                    "dynamodb:Scan",
                ],
                resources=[self._system_settings_table_arn],
            )
        )

        search_provider_get = search_resource.add_method(
            "GET",
            api_gateway.LambdaIntegration(self._get_search_provider_handler.function),
            # authorization_type=api_gateway.AuthorizationType.CUSTOM,
            # authorizer=props.authorizer,
        )
        apply_custom_authorization(search_provider_get, props.authorizer)

        # POST /settings/system/search
        self._post_search_provider_handler = Lambda(
            self,
            "PostSearchProviderHandler",
            config=LambdaConfig(
                name="post_search_provider",
                entry="lambdas/api/settings/system/search/post_search",
                environment_variables={
                    "X_ORIGIN_VERIFY_SECRET_ARN": props.x_origin_verify_secret.secret_arn,
                    "SYSTEM_SETTINGS_TABLE": self._system_settings_table_name,
                    "METRICS_NAMESPACE": "MediaLake",
                },
            ),
        )

        self._post_search_provider_handler.function.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "dynamodb:PutItem",
                    "dynamodb:GetItem",
                    "dynamodb:Query",
                    "dynamodb:Scan",
                ],
                resources=[self._system_settings_table_arn],
            )
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
                resources=["*"],
            )
        )

        search_provider_post = search_resource.add_method(
            "POST",
            api_gateway.LambdaIntegration(self._post_search_provider_handler.function),
            # authorization_type=api_gateway.AuthorizationType.CUSTOM,
            # authorizer=props.authorizer,
        )
        apply_custom_authorization(search_provider_post, props.authorizer)

        # PUT /settings/system/search
        self._put_search_provider_handler = Lambda(
            self,
            "PutSearchProviderHandler",
            config=LambdaConfig(
                name="put_search_provider",
                entry="lambdas/api/settings/system/search/put_search",
                environment_variables={
                    "X_ORIGIN_VERIFY_SECRET_ARN": props.x_origin_verify_secret.secret_arn,
                    "SYSTEM_SETTINGS_TABLE": self._system_settings_table_name,
                    "METRICS_NAMESPACE": "MediaLake",
                },
            ),
        )

        self._put_search_provider_handler.function.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "dynamodb:PutItem",
                    "dynamodb:GetItem",
                    "dynamodb:UpdateItem",
                ],
                resources=[self._system_settings_table_arn],
            )
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
                resources=["*"],
            )
        )

        search_provider_put = search_resource.add_method(
            "PUT",
            api_gateway.LambdaIntegration(self._put_search_provider_handler.function),
        )
        apply_custom_authorization(search_provider_put, props.authorizer)

        # DELETE /settings/system/search
        self._delete_search_provider_handler = Lambda(
            self,
            "DeleteSearchProviderHandler",
            config=LambdaConfig(
                name="delete_search_provider",
                entry="lambdas/api/settings/system/search/delete_search",
                environment_variables={
                    "X_ORIGIN_VERIFY_SECRET_ARN": props.x_origin_verify_secret.secret_arn,
                    "SYSTEM_SETTINGS_TABLE": self._system_settings_table_name,
                    "METRICS_NAMESPACE": "MediaLake",
                },
            ),
        )

        self._delete_search_provider_handler.function.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "dynamodb:DeleteItem",
                    "dynamodb:GetItem",
                    "dynamodb:PutItem",
                ],
                resources=[self._system_settings_table_arn],
            )
        )

        # Add permissions to access Secrets Manager
        self._delete_search_provider_handler.function.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "secretsmanager:DeleteSecret",
                ],
                resources=["*"],
            )
        )

        search_provider_delete = search_resource.add_method(
            "DELETE",
            api_gateway.LambdaIntegration(
                self._delete_search_provider_handler.function
            ),
        )
        apply_custom_authorization(search_provider_delete, props.authorizer)

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
                actions=[
                    "cognito-idp:ListUsers",
                    "cognito-idp:AdminGetUser",
                    "cognito-idp:AdminListGroupsForUser",
                ],
                resources=[props.cognito_user_pool.user_pool_arn],
            )
        )

        settings_users_get = settings_users_resource.add_method(
            "GET",
            api_gateway.LambdaIntegration(settings_users_get_lambda.function),
            # authorization_type=api_gateway.AuthorizationType.CUSTOM,
            # authorizer=props.authorizer,
        )
        apply_custom_authorization(settings_users_get, props.authorizer)

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

        settings_roles_get = settings_roles_resource.add_method(
            "GET",
            api_gateway.LambdaIntegration(settings_roles_get_lambda.function),
            # authorization_type=api_gateway.AuthorizationType.CUSTOM,
            # authorizer=props.authorizer,
        )
        apply_custom_authorization(settings_roles_get, props.authorizer)

        settings_user_del_lambda = Lambda(
            self,
            "SettingsUsersUserDelLambda",
            config=LambdaConfig(
                name="settings_users_user_del_lambda",
                # iam_role_name="settings_users_user_del_lambda_role",
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

        settings_user_delete = settings_users_userid_resource.add_method(
            "DELETE",
            api_gateway.LambdaIntegration(settings_user_del_lambda.function),
            # authorization_type=api_gateway.AuthorizationType.CUSTOM,
            # authorizer=props.authorizer,
        )
        apply_custom_authorization(settings_user_delete, props.authorizer)

        settings_user_put_lambda = Lambda(
            self,
            "SettingsUserPutLambda",
            config=LambdaConfig(
                name="settings_users_user_put_lambda",
                # iam_role_name="settings_users_user_put_lambda_role",
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

        settings_user_put = settings_users_userid_resource.add_method(
            "PUT",
            api_gateway.LambdaIntegration(settings_user_put_lambda.function),
            # authorization_type=api_gateway.AuthorizationType.CUSTOM,
            # authorizer=props.authorizer,
        )
        apply_custom_authorization(settings_user_put, props.authorizer)

        settings_users_user_userid_get_lambda = Lambda(
            self,
            "SettingsUsersUserUseridGetLambda",
            config=LambdaConfig(
                name="user_put",
                # iam_role_name="user_put",
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

        settings_user_userid_get = settings_users_user_userid_resource.add_method(
            "GET",
            api_gateway.LambdaIntegration(
                settings_users_user_userid_get_lambda.function
            ),
            # authorization_type=api_gateway.AuthorizationType.CUSTOM,
            # authorizer=props.authorizer,
        )
        apply_custom_authorization(settings_user_userid_get, props.authorizer)

        # settings_users_user_post_lambda = Lambda(
        #     self,
        #     "SettingsUsersUserPostLambda",
        #     config=LambdaConfig(
        #         name="settings_users_user_post_lambda",
        #         entry="lambdas/api/settings/users/user/post_user",
        #         environment_variables={
        #             "X_ORIGIN_VERIFY_SECRET_ARN": (
        #                 props.x_origin_verify_secret.secret_arn
        #             ),
        #             "USER_POOL_ID": (props.cognito_user_pool.user_pool_id),
        #             "APP_CLIENT_ID": (props.cognito_app_client),
        #         },
        #     ),
        # )

        # settings_users_user_post_lambda.function.add_to_role_policy(
        #     iam.PolicyStatement(
        #         effect=iam.Effect.ALLOW,
        #         actions=[
        #             "cognito-idp:AdminCreateUser",
        #             "cognito-idp:AdminUpdateUserAttributes",
        #             "cognito-idp:AdminGetUser",
        #             "cognito-idp:AdminAddUserToGroup",
        #             "cognito-idp:AdminListGroupsForUser",
        #             "cognito-idp:ListGroups",
        #             "cognito-idp:AdminSetUserPassword",
        #             "cognito-idp:AdminInitiateAuth",
        #         ],
        #         resources=[props.cognito_user_pool.user_pool_arn],
        #     )
        # )

        # settings_users_user_resource.add_method(
        #     "POST",
        #     api_gateway.LambdaIntegration(settings_users_user_post_lambda.function),
        #     authorization_type=api_gateway.AuthorizationType.CUSTOM,
        #     authorizer=props.authorizer,
        # )

        # Add CORS support to additional resources
        add_cors_options_method(settings_users_resource)
        add_cors_options_method(settings_users_userid_resource)
        # add_cors_options_method(settings_users_user_resource)
        add_cors_options_method(settings_users_user_userid_resource)
        add_cors_options_method(settings_roles_resource)
        add_cors_options_method(settings_roles_role_resource)

        # Create API keys resource
        api_keys_resource = settings_resource.add_resource("api-keys")
        api_key_id_resource = api_keys_resource.add_resource("{id}")

        # Add OPTIONS method to support CORS
        add_cors_options_method(api_keys_resource)
        add_cors_options_method(api_key_id_resource)

        # GET /settings/api-keys - List all API keys
        self._get_api_keys_handler = Lambda(
            self,
            "GetApiKeysHandler",
            config=LambdaConfig(
                name="get_api_keys",
                entry="lambdas/api/settings/api_keys/get_api_keys",
                environment_variables={
                    "X_ORIGIN_VERIFY_SECRET_ARN": props.x_origin_verify_secret.secret_arn,
                    "API_KEYS_TABLE": props.api_keys_table_name,
                    "METRICS_NAMESPACE": "MediaLake",
                },
            ),
        )

        self._get_api_keys_handler.function.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "dynamodb:Scan",
                    "dynamodb:Query",
                ],
                resources=[props.api_keys_table_arn],
            )
        )

        api_keys_get = api_keys_resource.add_method(
            "GET",
            api_gateway.LambdaIntegration(self._get_api_keys_handler.function),
            # authorization_type=api_gateway.AuthorizationType.CUSTOM,
            # authorizer=props.authorizer,
        )
        # apply_custom_authorization(api_keys_get, props.authorizer)

        # POST /settings/api-keys - Create new API key
        self._post_api_keys_handler = Lambda(
            self,
            "PostApiKeysHandler",
            config=LambdaConfig(
                name="post_api_keys",
                entry="lambdas/api/settings/api_keys/post_api_keys",
                environment_variables={
                    "X_ORIGIN_VERIFY_SECRET_ARN": props.x_origin_verify_secret.secret_arn,
                    "API_KEYS_TABLE": props.api_keys_table_name,
                    "METRICS_NAMESPACE": "MediaLake",
                },
            ),
        )

        self._post_api_keys_handler.function.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "dynamodb:PutItem",
                    "dynamodb:GetItem",
                ],
                resources=[props.api_keys_table_arn],
            )
        )

        # Add Secrets Manager permissions for creating API keys
        self._post_api_keys_handler.function.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "secretsmanager:CreateSecret",
                    "secretsmanager:TagResource",
                ],
                resources=["*"],
            )
        )

        api_keys_post = api_keys_resource.add_method(
            "POST",
            api_gateway.LambdaIntegration(self._post_api_keys_handler.function),
            # authorization_type=api_gateway.AuthorizationType.CUSTOM,
            # authorizer=props.authorizer,
        )
        # apply_custom_authorization(api_keys_post, props.authorizer)

        # GET /settings/api-keys/{id} - Get single API key
        self._get_api_key_handler = Lambda(
            self,
            "GetApiKeyHandler",
            config=LambdaConfig(
                name="get_api_key",
                entry="lambdas/api/settings/api_keys/get_api_key",
                environment_variables={
                    "X_ORIGIN_VERIFY_SECRET_ARN": props.x_origin_verify_secret.secret_arn,
                    "API_KEYS_TABLE": props.api_keys_table_name,
                    "METRICS_NAMESPACE": "MediaLake",
                },
            ),
        )

        self._get_api_key_handler.function.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "dynamodb:GetItem",
                ],
                resources=[props.api_keys_table_arn],
            )
        )

        api_key_get = api_key_id_resource.add_method(
            "GET",
            api_gateway.LambdaIntegration(self._get_api_key_handler.function),
            # authorization_type=api_gateway.AuthorizationType.CUSTOM,
            # authorizer=props.authorizer,
        )
        # apply_custom_authorization(api_key_get, props.authorizer)

        # PUT /settings/api-keys/{id} - Update API key
        self._put_api_key_handler = Lambda(
            self,
            "PutApiKeyHandler",
            config=LambdaConfig(
                name="put_api_key",
                entry="lambdas/api/settings/api_keys/put_api_key",
                environment_variables={
                    "X_ORIGIN_VERIFY_SECRET_ARN": props.x_origin_verify_secret.secret_arn,
                    "API_KEYS_TABLE": props.api_keys_table_name,
                    "METRICS_NAMESPACE": "MediaLake",
                },
            ),
        )

        self._put_api_key_handler.function.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "dynamodb:GetItem",
                    "dynamodb:UpdateItem",
                ],
                resources=[props.api_keys_table_arn],
            )
        )

        # Add Secrets Manager permissions for updating API keys
        self._put_api_key_handler.function.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "secretsmanager:GetSecretValue",
                    "secretsmanager:UpdateSecret",
                    "secretsmanager:PutSecretValue",
                ],
                resources=["*"],
            )
        )

        api_key_put = api_key_id_resource.add_method(
            "PUT",
            api_gateway.LambdaIntegration(self._put_api_key_handler.function),
            # authorization_type=api_gateway.AuthorizationType.CUSTOM,
            # authorizer=props.authorizer,
        )
        apply_custom_authorization(api_key_put, props.authorizer)

        # DELETE /settings/api-keys/{id} - Delete API key
        self._delete_api_key_handler = Lambda(
            self,
            "DeleteApiKeyHandler",
            config=LambdaConfig(
                name="delete_api_key",
                entry="lambdas/api/settings/api_keys/delete_api_key",
                environment_variables={
                    "X_ORIGIN_VERIFY_SECRET_ARN": props.x_origin_verify_secret.secret_arn,
                    "API_KEYS_TABLE": props.api_keys_table_name,
                    "METRICS_NAMESPACE": "MediaLake",
                },
            ),
        )

        self._delete_api_key_handler.function.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "dynamodb:GetItem",
                    "dynamodb:DeleteItem",
                ],
                resources=[props.api_keys_table_arn],
            )
        )

        # Add Secrets Manager permissions for deleting API keys
        self._delete_api_key_handler.function.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "secretsmanager:DeleteSecret",
                    "secretsmanager:GetSecretValue",
                ],
                resources=["*"],
            )
        )

        api_key_delete = api_key_id_resource.add_method(
            "DELETE",
            api_gateway.LambdaIntegration(self._delete_api_key_handler.function),
            # authorization_type=api_gateway.AuthorizationType.CUSTOM,
            # authorizer=props.authorizer,
        )
        apply_custom_authorization(api_key_delete, props.authorizer)

    @property
    def system_settings_table_name(self) -> str:
        return self._system_settings_table_name

    @property
    def system_settings_table_arn(self) -> str:
        return self._system_settings_table_arn

    @property
    def get_system_settings_handler(self) -> Lambda:
        return self._get_system_settings_handler

    @property
    def get_search_provider_handler(self) -> Lambda:
        return self._get_search_provider_handler

    @property
    def post_search_provider_handler(self) -> Lambda:
        return self._post_search_provider_handler.function

    @property
    def put_search_provider_handler(self) -> Lambda:
        return self._put_search_provider_handler
