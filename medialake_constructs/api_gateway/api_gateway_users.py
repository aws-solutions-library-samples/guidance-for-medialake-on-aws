"""
API Gateway Users module for MediaLake.

This module defines the UsersApi class which sets up API Gateway endpoints
and associated Lambda function for managing users. It consolidates all user-related
endpoints (CRUD, profile, settings, favorites) into a single Lambda with AWS Powertools routing.
"""

from dataclasses import dataclass

from aws_cdk import Stack
from aws_cdk import aws_apigateway as api_gateway
from aws_cdk import aws_cognito as cognito
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_iam as iam
from aws_cdk import aws_secretsmanager as secrets_manager
from constructs import Construct

from medialake_constructs.api_gateway.api_gateway_utils import add_cors_options_method
from medialake_constructs.shared_constructs.lambda_base import Lambda, LambdaConfig


@dataclass
class UsersApiProps:
    x_origin_verify_secret: secrets_manager.Secret
    api_resource: api_gateway.RestApi
    authorizer: api_gateway.IAuthorizer
    cognito_user_pool: cognito.UserPool
    user_table: dynamodb.Table


class UsersApi(Construct):
    """
    Users API Gateway deployment with unified Lambda for all user endpoints
    """

    def __init__(
        self,
        scope: Construct,
        constructor_id: str,
        props: UsersApiProps,
    ) -> None:
        super().__init__(scope, constructor_id)

        # Get the current account ID
        Stack.of(self).account

        # Create unified users Lambda function
        users_lambda = Lambda(
            self,
            "UsersLambda",
            config=LambdaConfig(
                name="users",
                entry="lambdas/api/users",
                lambda_handler="index.lambda_handler",
                environment_variables={
                    "X_ORIGIN_VERIFY_SECRET_ARN": (
                        props.x_origin_verify_secret.secret_arn
                    ),
                    "COGNITO_USER_POOL_ID": props.cognito_user_pool.user_pool_id,
                    "USER_TABLE_NAME": props.user_table.table_name,
                },
            ),
        )

        # Grant permissions to the unified Lambda
        props.user_table.grant_read_write_data(users_lambda.function)
        props.x_origin_verify_secret.grant_read(users_lambda.function)

        # Grant Cognito permissions
        users_lambda.function.add_to_role_policy(
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
                    # Write actions
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

        # Create API Gateway resources with simplified RESTful paths
        users_resource = props.api_resource.root.add_resource("users")

        # /users/{user_id} resource
        user_id_resource = users_resource.add_resource("{user_id}")

        # /users/{user_id}/enable resource
        user_enable_resource = user_id_resource.add_resource("enable")

        # /users/{user_id}/disable resource
        user_disable_resource = user_id_resource.add_resource("disable")

        # /users/profile resource
        profile_resource = users_resource.add_resource("profile")

        # /users/settings resource
        settings_resource = users_resource.add_resource("settings")

        # /users/settings/{namespace} resource
        settings_namespace_resource = settings_resource.add_resource("{namespace}")

        # /users/settings/{namespace}/{key} resource
        settings_namespace_key_resource = settings_namespace_resource.add_resource(
            "{key}"
        )

        # /users/favorites resource
        favorites_resource = users_resource.add_resource("favorites")

        # /users/favorites/{itemType} resource
        favorites_item_type_resource = favorites_resource.add_resource("{itemType}")

        # /users/favorites/{itemType}/{itemId} resource
        favorites_item_type_item_id_resource = (
            favorites_item_type_resource.add_resource("{itemId}")
        )

        # Create Lambda integration (proxy integration for all methods)
        lambda_integration = api_gateway.LambdaIntegration(
            users_lambda.function,
            proxy=True,
        )

        # Add methods to resources

        # POST /users - Create user
        users_post_method = users_resource.add_method(
            "POST",
            lambda_integration,
        )
        cfn_method = users_post_method.node.default_child
        cfn_method.authorization_type = "CUSTOM"
        cfn_method.authorizer_id = props.authorizer.authorizer_id

        # GET /users/{user_id} - Get user
        user_get_method = user_id_resource.add_method(
            "GET",
            lambda_integration,
        )
        cfn_method = user_get_method.node.default_child
        cfn_method.authorization_type = "CUSTOM"
        cfn_method.authorizer_id = props.authorizer.authorizer_id

        # PUT /users/{user_id} - Update user
        user_put_method = user_id_resource.add_method(
            "PUT",
            lambda_integration,
        )
        cfn_method = user_put_method.node.default_child
        cfn_method.authorization_type = "CUSTOM"
        cfn_method.authorizer_id = props.authorizer.authorizer_id

        # DELETE /users/{user_id} - Delete user
        user_delete_method = user_id_resource.add_method(
            "DELETE",
            lambda_integration,
        )
        cfn_method = user_delete_method.node.default_child
        cfn_method.authorization_type = "CUSTOM"
        cfn_method.authorizer_id = props.authorizer.authorizer_id

        # POST /users/{user_id}/enable - Enable user
        user_enable_method = user_enable_resource.add_method(
            "POST",
            lambda_integration,
        )
        cfn_method = user_enable_method.node.default_child
        cfn_method.authorization_type = "CUSTOM"
        cfn_method.authorizer_id = props.authorizer.authorizer_id

        # POST /users/{user_id}/disable - Disable user
        user_disable_method = user_disable_resource.add_method(
            "POST",
            lambda_integration,
        )
        cfn_method = user_disable_method.node.default_child
        cfn_method.authorization_type = "CUSTOM"
        cfn_method.authorizer_id = props.authorizer.authorizer_id

        # GET /users/profile - Get user profile
        profile_get_method = profile_resource.add_method(
            "GET",
            lambda_integration,
        )
        cfn_method = profile_get_method.node.default_child
        cfn_method.authorization_type = "CUSTOM"
        cfn_method.authorizer_id = props.authorizer.authorizer_id

        # PUT /users/profile - Update user profile
        profile_put_method = profile_resource.add_method(
            "PUT",
            lambda_integration,
        )
        cfn_method = profile_put_method.node.default_child
        cfn_method.authorization_type = "CUSTOM"
        cfn_method.authorizer_id = props.authorizer.authorizer_id

        # GET /users/settings - Get user settings
        settings_get_method = settings_resource.add_method(
            "GET",
            lambda_integration,
        )
        cfn_method = settings_get_method.node.default_child
        cfn_method.authorization_type = "CUSTOM"
        cfn_method.authorizer_id = props.authorizer.authorizer_id

        # PUT /users/settings/{namespace}/{key} - Update user setting
        settings_put_method = settings_namespace_key_resource.add_method(
            "PUT",
            lambda_integration,
        )
        cfn_method = settings_put_method.node.default_child
        cfn_method.authorization_type = "CUSTOM"
        cfn_method.authorizer_id = props.authorizer.authorizer_id

        # GET /users/favorites - Get user favorites
        favorites_get_method = favorites_resource.add_method(
            "GET",
            lambda_integration,
        )
        cfn_method = favorites_get_method.node.default_child
        cfn_method.authorization_type = "CUSTOM"
        cfn_method.authorizer_id = props.authorizer.authorizer_id

        # POST /users/favorites - Add a favorite
        favorites_post_method = favorites_resource.add_method(
            "POST",
            lambda_integration,
        )
        cfn_method = favorites_post_method.node.default_child
        cfn_method.authorization_type = "CUSTOM"
        cfn_method.authorizer_id = props.authorizer.authorizer_id

        # DELETE /users/favorites/{itemType}/{itemId} - Remove a favorite
        favorites_delete_method = favorites_item_type_item_id_resource.add_method(
            "DELETE",
            lambda_integration,
        )
        cfn_method = favorites_delete_method.node.default_child
        cfn_method.authorization_type = "CUSTOM"
        cfn_method.authorizer_id = props.authorizer.authorizer_id

        # Add CORS support to all resources
        add_cors_options_method(users_resource)
        add_cors_options_method(user_id_resource)
        add_cors_options_method(user_enable_resource)
        add_cors_options_method(user_disable_resource)
        add_cors_options_method(profile_resource)
        add_cors_options_method(settings_resource)
        add_cors_options_method(settings_namespace_resource)
        add_cors_options_method(settings_namespace_key_resource)
        add_cors_options_method(favorites_resource)
        add_cors_options_method(favorites_item_type_resource)
        add_cors_options_method(favorites_item_type_item_id_resource)

        # Store reference to the unified Lambda
        self._users_lambda = users_lambda

    @property
    def users_lambda(self):
        """Return the unified users Lambda function"""
        return self._users_lambda
