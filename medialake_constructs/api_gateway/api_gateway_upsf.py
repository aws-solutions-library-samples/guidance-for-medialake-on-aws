"""
API Gateway UPSF module for MediaLake.

This module defines the UPSFApi class which sets up API Gateway endpoints
and associated Lambda functions for User Profile, Settings, and Favorites (UPSF) features.
"""

from dataclasses import dataclass

from aws_cdk import aws_apigateway as api_gateway
from aws_cdk import aws_cognito as cognito
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_secretsmanager as secrets_manager
from constructs import Construct

from medialake_constructs.api_gateway.api_gateway_utils import add_cors_options_method
from medialake_constructs.shared_constructs.lambda_base import Lambda, LambdaConfig


@dataclass
class UPSFApiProps:
    """Properties for the UPSF API construct."""

    x_origin_verify_secret: secrets_manager.Secret
    api_resource: api_gateway.IResource
    cognito_authorizer: api_gateway.IAuthorizer
    cognito_user_pool: cognito.UserPool
    user_table: dynamodb.Table


class UPSFApi(Construct):
    """
    UPSF API Gateway deployment for User Profile, Settings, and Favorites features.
    """

    def __init__(
        self,
        scope: Construct,
        constructor_id: str,
        props: UPSFApiProps,
    ) -> None:
        super().__init__(scope, constructor_id)

        # IMPORTANT: The UsersApi construct creates the /users resource
        # We should NOT create another /users resource as it will conflict
        # Instead, we need the UsersApi to expose its users_resource for reuse
        # For now, we'll disable the UPSFApi endpoints to prevent conflicts
        # TODO: Refactor to properly share the users resource between constructs
        return  # Early return to prevent resource conflicts

        # Set up common environment variables for all Lambda functions
        common_env_vars = {
            "X_ORIGIN_VERIFY_SECRET_ARN": props.x_origin_verify_secret.secret_arn,
            "USER_TABLE_NAME": props.user_table.table_name,
            "COGNITO_USER_POOL_ID": props.cognito_user_pool.user_pool_id,
        }

        # 1. User Profile Endpoints
        profile_resource = users_resource.add_resource("profile")

        # GET /users/profile - Get user profile
        get_profile_lambda = Lambda(
            self,
            "GetProfileLambda",
            config=LambdaConfig(
                name="get_user_profile",
                entry="lambdas/api/users/profile/get_profile",
                environment_variables=common_env_vars,
            ),
        )
        props.user_table.grant_read_data(get_profile_lambda.function)

        profile_resource.add_method(
            "GET",
            api_gateway.LambdaIntegration(get_profile_lambda.function),
            authorization_type=api_gateway.AuthorizationType.COGNITO,
            authorizer=props.cognito_authorizer,
        )

        # PUT /users/profile - Update user profile
        put_profile_lambda = Lambda(
            self,
            "UserProfilePutLambda",
            config=LambdaConfig(
                name="user-profile-put",
                entry="lambdas/api/users/profile/put_profile",
                environment_variables=common_env_vars,
            ),
        )
        props.user_table.grant_read_write_data(put_profile_lambda.function)

        profile_resource.add_method(
            "PUT",
            api_gateway.LambdaIntegration(put_profile_lambda.function),
            authorization_type=api_gateway.AuthorizationType.COGNITO,
            authorizer=props.cognito_authorizer,
        )

        # 2. User Settings Endpoints
        settings_resource = users_resource.add_resource("settings")

        # GET /users/settings - Get user settings
        get_settings_lambda = Lambda(
            self,
            "UserSettingsGetLambda",
            config=LambdaConfig(
                name="user-settings-get",
                entry="lambdas/api/users/settings/get_settings",
                environment_variables=common_env_vars,
            ),
        )
        props.user_table.grant_read_data(get_settings_lambda.function)

        settings_resource.add_method(
            "GET",
            api_gateway.LambdaIntegration(get_settings_lambda.function),
            authorization_type=api_gateway.AuthorizationType.COGNITO,
            authorizer=props.cognito_authorizer,
        )

        # PUT /users/settings/{namespace}/{key} - Update user setting
        settings_namespace_resource = settings_resource.add_resource("{namespace}")
        settings_namespace_key_resource = settings_namespace_resource.add_resource(
            "{key}"
        )

        put_setting_lambda = Lambda(
            self,
            "UserSettingsPutLambda",
            config=LambdaConfig(
                name="user-settings-put",
                entry="lambdas/api/users/settings/put_setting",
                environment_variables=common_env_vars,
            ),
        )
        props.user_table.grant_read_write_data(put_setting_lambda.function)

        settings_namespace_key_resource.add_method(
            "PUT",
            api_gateway.LambdaIntegration(
                put_setting_lambda.function,
                request_templates={
                    "application/json": '{ "namespace": "$input.params(\'namespace\')", "key": "$input.params(\'key\')" }'
                },
            ),
            authorization_type=api_gateway.AuthorizationType.COGNITO,
            authorizer=props.cognito_authorizer,
        )

        # 3. User Favorites Endpoints
        favorites_resource = users_resource.add_resource("favorites")

        # POST /users/favorites - Add favorite
        post_favorite_lambda = Lambda(
            self,
            "PostFavoriteLambda",
            config=LambdaConfig(
                name="add_favorite",
                entry="lambdas/api/users/favorites/post_favorite",
                environment_variables=common_env_vars,
            ),
        )
        props.user_table.grant_read_write_data(post_favorite_lambda.function)

        favorites_resource.add_method(
            "POST",
            api_gateway.LambdaIntegration(post_favorite_lambda.function),
            authorization_type=api_gateway.AuthorizationType.COGNITO,
            authorizer=props.cognito_authorizer,
        )

        # GET /users/favorites - List favorites
        get_favorites_lambda = Lambda(
            self,
            "GetFavoritesLambda",
            config=LambdaConfig(
                name="list_favorites",
                entry="lambdas/api/users/favorites/get_favorites",
                environment_variables=common_env_vars,
            ),
        )
        props.user_table.grant_read_data(get_favorites_lambda.function)

        favorites_resource.add_method(
            "GET",
            api_gateway.LambdaIntegration(get_favorites_lambda.function),
            authorization_type=api_gateway.AuthorizationType.COGNITO,
            authorizer=props.cognito_authorizer,
        )

        # DELETE /users/favorites/{itemType}/{itemId} - Remove favorite
        favorites_item_type_resource = favorites_resource.add_resource("{itemType}")
        favorites_item_type_item_id_resource = (
            favorites_item_type_resource.add_resource("{itemId}")
        )

        delete_favorite_lambda = Lambda(
            self,
            "UsersFavoritesDeleteLambda",
            config=LambdaConfig(
                name="users-favorites-delete",
                entry="lambdas/api/users/favorites/delete_favorite",
                environment_variables=common_env_vars,
            ),
        )
        props.user_table.grant_read_write_data(delete_favorite_lambda.function)

        favorites_item_type_item_id_resource.add_method(
            "DELETE",
            api_gateway.LambdaIntegration(
                delete_favorite_lambda.function,
                request_templates={
                    "application/json": '{ "itemType": "$input.params(\'itemType\')", "itemId": "$input.params(\'itemId\')" }'
                },
            ),
            authorization_type=api_gateway.AuthorizationType.COGNITO,
            authorizer=props.cognito_authorizer,
        )

        # Add CORS support to all resources
        # Don't add OPTIONS to users_resource if it was reused from UsersApi
        # Only add OPTIONS to the sub-resources that UPSFApi creates
        add_cors_options_method(settings_namespace_resource)
        add_cors_options_method(favorites_item_type_resource)
        add_cors_options_method(profile_resource)
        add_cors_options_method(settings_resource)
        add_cors_options_method(favorites_resource)
        add_cors_options_method(settings_namespace_key_resource)
        add_cors_options_method(favorites_item_type_item_id_resource)
