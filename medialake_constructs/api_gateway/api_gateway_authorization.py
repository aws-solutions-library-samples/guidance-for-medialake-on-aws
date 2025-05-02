"""
API Gateway Authorization module for MediaLake.

This module defines the AuthorizationApi class which sets up API Gateway endpoints
and associated Lambda functions for managing Permission Sets and other authorization resources.
"""

from dataclasses import dataclass
from constructs import Construct
from aws_cdk import (
    aws_apigateway as api_gateway,
    aws_dynamodb as dynamodb,
    aws_iam as iam,
    aws_cognito as cognito,
    aws_secretsmanager as secrets_manager,
    Duration,
)
from medialake_constructs.api_gateway.api_gateway_utils import add_cors_options_method
from config import config
from medialake_constructs.shared_constructs.lambda_base import (
    Lambda,
    LambdaConfig,
)


@dataclass
class AuthorizationApiProps:
    """Properties for the Authorization API construct."""
    x_origin_verify_secret: secrets_manager.Secret
    api_resource: api_gateway.IResource
    cognito_authorizer: api_gateway.IAuthorizer
    cognito_user_pool: cognito.UserPool
    auth_table: dynamodb.TableV2


class AuthorizationApi(Construct):
    """
    Authorization API Gateway deployment for managing Permission Sets and other authorization resources.
    """

    def __init__(
        self,
        scope: Construct,
        constructor_id: str,
        props: AuthorizationApiProps,
    ) -> None:
        super().__init__(scope, constructor_id)

        # Create the base authorization resource if it doesn't exist
        authorization_resource = props.api_resource.get_resource("authorization")
        if authorization_resource is None:
            authorization_resource = props.api_resource.add_resource("authorization")

        # Set up common environment variables for all Lambda functions
        common_env_vars = {
            "X_ORIGIN_VERIFY_SECRET_ARN": props.x_origin_verify_secret.secret_arn,
            "AUTH_TABLE_NAME": props.auth_table.table_name,
            "COGNITO_USER_POOL_ID": props.cognito_user_pool.user_pool_id,
        }

        # Set up common CORS configuration
        # cors_config = api_gateway.CorsOptions(
        #     allow_origins=["http://localhost:5173"],
        #     allow_methods=["GET", "PUT", "OPTIONS", "DELETE", "POST"],
        #     allow_headers=["Content-Type", "Authorization", "X-Amz-Date", "X-Api-Key", "X-Amz-Security-Token"],
        #     allow_credentials=True,
        #     max_age=Duration.seconds(300),
        # )

        # 1. Permission Sets Endpoints
        permission_sets_resource = authorization_resource.add_resource("permission-sets")

        # POST /authorization/permission-sets - Create a new custom Permission Set
        create_permission_set_lambda = Lambda(
            self,
            "CreatePermissionSetLambda",
            config=LambdaConfig(
                name="create_permission_set",
                entry="lambdas/api/authorization/permission_sets/post_permission_set",
                environment_variables=common_env_vars,
            ),
        )
        props.auth_table.grant_read_write_data(create_permission_set_lambda.function)

        permission_sets_resource.add_method(
            "POST",
            api_gateway.LambdaIntegration(create_permission_set_lambda.function),
            authorization_type=api_gateway.AuthorizationType.CUSTOM,
            authorizer=props.cognito_authorizer,
        )

        # GET /authorization/permission-sets - List all Permission Sets
        list_permission_sets_lambda = Lambda(
            self,
            "ListPermissionSetsLambda",
            config=LambdaConfig(
                name="list_permission_sets",
                entry="lambdas/api/authorization/permission_sets/get_permission_sets",
                environment_variables=common_env_vars,
            ),
        )
        props.auth_table.grant_read_data(list_permission_sets_lambda.function)

        permission_sets_resource.add_method(
            "GET",
            api_gateway.LambdaIntegration(list_permission_sets_lambda.function),
            authorization_type=api_gateway.AuthorizationType.CUSTOM,
            authorizer=props.cognito_authorizer,
        )

        # Permission Set by ID resource
        permission_set_id_resource = permission_sets_resource.add_resource("{permissionSetId}")

        # GET /authorization/permission-sets/{permissionSetId} - Get details of a specific Permission Set
        get_permission_set_lambda = Lambda(
            self,
            "GetPermissionSetLambda",
            config=LambdaConfig(
                name="get_permission_set",
                entry="lambdas/api/authorization/permission_sets/get_permission_set",
                environment_variables=common_env_vars,
            ),
        )
        props.auth_table.grant_read_data(get_permission_set_lambda.function)

        permission_set_id_resource.add_method(
            "GET",
            api_gateway.LambdaIntegration(
                get_permission_set_lambda.function,
                request_templates={
                    "application/json": '{ "permissionSetId": "$input.params(\'permissionSetId\')" }'
                },
            ),
            authorization_type=api_gateway.AuthorizationType.CUSTOM,
            authorizer=props.cognito_authorizer,
        )

        # PUT /authorization/permission-sets/{permissionSetId} - Update an existing custom Permission Set
        update_permission_set_lambda = Lambda(
            self,
            "UpdatePermissionSetLambda",
            config=LambdaConfig(
                name="update_permission_set",
                entry="lambdas/api/authorization/permission_sets/put_permission_set",
                environment_variables=common_env_vars,
            ),
        )
        props.auth_table.grant_read_write_data(update_permission_set_lambda.function)

        permission_set_id_resource.add_method(
            "PUT",
            api_gateway.LambdaIntegration(
                update_permission_set_lambda.function,
                request_templates={
                    "application/json": '{ "permissionSetId": "$input.params(\'permissionSetId\')" }'
                },
            ),
            authorization_type=api_gateway.AuthorizationType.CUSTOM,
            authorizer=props.cognito_authorizer,
        )

        # DELETE /authorization/permission-sets/{permissionSetId} - Delete a custom Permission Set
        delete_permission_set_lambda = Lambda(
            self,
            "DeletePermissionSetLambda",
            config=LambdaConfig(
                name="delete_permission_set",
                entry="lambdas/api/authorization/permission_sets/delete_permission_set",
                environment_variables=common_env_vars,
            ),
        )
        props.auth_table.grant_read_write_data(delete_permission_set_lambda.function)

        permission_set_id_resource.add_method(
            "DELETE",
            api_gateway.LambdaIntegration(
                delete_permission_set_lambda.function,
                request_templates={
                    "application/json": '{ "permissionSetId": "$input.params(\'permissionSetId\')" }'
                },
            ),
            authorization_type=api_gateway.AuthorizationType.CUSTOM,
            authorizer=props.cognito_authorizer,
        )

        # Add CORS support to all resources
        add_cors_options_method(authorization_resource)
        add_cors_options_method(permission_sets_resource)
        add_cors_options_method(permission_set_id_resource)
