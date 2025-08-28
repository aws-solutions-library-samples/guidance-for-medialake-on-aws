"""
Permissions Stack for Media Lake.

This stack defines the AWS resources for the permissions system, including:
- API Gateway endpoints for managing permission sets under the /permissions path
- Lambda functions for CRUD operations on permission sets
- Integration with the authorization DynamoDB table
"""

from dataclasses import dataclass

import aws_cdk as cdk
from aws_cdk import Duration, Fn
from aws_cdk import aws_apigateway as apigateway
from aws_cdk import aws_cognito as cognito
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_secretsmanager as secrets_manager
from constructs import Construct

from medialake_constructs.api_gateway.api_gateway_utils import add_cors_options_method
from medialake_constructs.auth.authorizer_utils import (
    create_shared_custom_authorizer,
    ensure_shared_authorizer_permissions,
)
from medialake_constructs.shared_constructs.lambda_base import Lambda, LambdaConfig


@dataclass
class PermissionsStackProps:
    """Configuration for Permissions Stack."""

    api_resource: apigateway.IRestApi
    x_origin_verify_secret: secrets_manager.Secret
    cognito_user_pool: cognito.UserPool
    auth_table: dynamodb.TableV2


class PermissionsStack(cdk.NestedStack):
    """
    Stack for Permissions resources.

    This stack creates API Gateway endpoints for managing permission sets under the /permissions path,
    along with the necessary Lambda functions for CRUD operations.
    """

    def __init__(
        self, scope: Construct, id: str, props: PermissionsStackProps, **kwargs
    ):
        super().__init__(scope, id, **kwargs)

        # Use the shared custom authorizer
        api_id = Fn.import_value("MediaLakeApiGatewayCore-ApiGatewayId")

        self._api_authorizer = create_shared_custom_authorizer(
            self, "PermissionsCustomApiAuthorizer", api_gateway_id=api_id
        )

        root_resource_id = Fn.import_value("MediaLakeApiGatewayCore-RootResourceId")

        api = apigateway.RestApi.from_rest_api_attributes(
            self,
            "PermissionsImportedApi",
            rest_api_id=api_id,
            root_resource_id=root_resource_id,
        )

        # Ensure the shared authorizer has permissions for this API Gateway
        ensure_shared_authorizer_permissions(self, "Permissions", api)

        # Create the base permissions resource
        permissions_resource = api.root.add_resource("permissions")

        # Set up common environment variables for all Lambda functions
        common_env_vars = {
            "X_ORIGIN_VERIFY_SECRET_ARN": props.x_origin_verify_secret.secret_arn,
            "AUTH_TABLE_NAME": props.auth_table.table_name,
            "COGNITO_USER_POOL_ID": props.cognito_user_pool.user_pool_id,
        }

        # Set up common CORS configuration
        cors_config = apigateway.CorsOptions(
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

        # POST /permissions - Create a new custom Permission Set
        create_permission_set_lambda = Lambda(
            self,
            "CreatePermissionSetLambda",
            config=LambdaConfig(
                name="permissions_create_permission_set",  # New name to avoid conflicts
                entry="lambdas/api/permissions/post_permission_set",
                environment_variables=common_env_vars,
            ),
        )
        props.auth_table.grant_read_write_data(create_permission_set_lambda.function)

        permissions_resource.add_method(
            "POST",
            apigateway.LambdaIntegration(create_permission_set_lambda.function),
            authorization_type=apigateway.AuthorizationType.CUSTOM,
            authorizer=self._api_authorizer,
        )

        # GET /permissions - List all Permission Sets
        list_permission_sets_lambda = Lambda(
            self,
            "ListPermissionSetsLambda",
            config=LambdaConfig(
                name="permissions_list_permission_sets",  # New name to avoid conflicts
                entry="lambdas/api/permissions/get_permission_sets",
                environment_variables=common_env_vars,
            ),
        )
        props.auth_table.grant_read_data(list_permission_sets_lambda.function)

        permissions_resource.add_method(
            "GET",
            apigateway.LambdaIntegration(list_permission_sets_lambda.function),
            authorization_type=apigateway.AuthorizationType.CUSTOM,
            authorizer=self._api_authorizer,
        )

        # Permission Set by ID resource
        permission_set_id_resource = permissions_resource.add_resource(
            "{permissionSetId}"
        )

        # GET /permissions/{permissionSetId} - Get details of a specific Permission Set
        get_permission_set_lambda = Lambda(
            self,
            "GetPermissionSetLambda",
            config=LambdaConfig(
                name="permissions_get_permission_set",  # New name to avoid conflicts
                entry="lambdas/api/permissions/get_permission_set",
                environment_variables=common_env_vars,
            ),
        )
        props.auth_table.grant_read_data(get_permission_set_lambda.function)

        permission_set_id_resource.add_method(
            "GET",
            apigateway.LambdaIntegration(
                get_permission_set_lambda.function,
                request_templates={
                    "application/json": '{ "permissionSetId": "$input.params(\'permissionSetId\')" }'
                },
            ),
            authorization_type=apigateway.AuthorizationType.CUSTOM,
            authorizer=self._api_authorizer,
        )

        # PUT /permissions/{permissionSetId} - Update an existing custom Permission Set
        update_permission_set_lambda = Lambda(
            self,
            "UpdatePermissionSetLambda",
            config=LambdaConfig(
                name="permissions_update_permission_set",  # New name to avoid conflicts
                entry="lambdas/api/permissions/put_permission_set",
                environment_variables=common_env_vars,
            ),
        )
        props.auth_table.grant_read_write_data(update_permission_set_lambda.function)

        permission_set_id_resource.add_method(
            "PUT",
            apigateway.LambdaIntegration(
                update_permission_set_lambda.function,
                request_templates={
                    "application/json": '{ "permissionSetId": "$input.params(\'permissionSetId\')" }'
                },
            ),
            authorization_type=apigateway.AuthorizationType.CUSTOM,
            authorizer=self._api_authorizer,
        )

        # DELETE /permissions/{permissionSetId} - Delete a custom Permission Set
        delete_permission_set_lambda = Lambda(
            self,
            "DeletePermissionSetLambda",
            config=LambdaConfig(
                name="permissions_delete_permission_set",  # New name to avoid conflicts
                entry="lambdas/api/permissions/delete_permission_set",
                environment_variables=common_env_vars,
            ),
        )
        props.auth_table.grant_read_write_data(delete_permission_set_lambda.function)

        permission_set_id_resource.add_method(
            "DELETE",
            apigateway.LambdaIntegration(
                delete_permission_set_lambda.function,
                request_templates={
                    "application/json": '{ "permissionSetId": "$input.params(\'permissionSetId\')" }'
                },
            ),
            authorization_type=apigateway.AuthorizationType.CUSTOM,
            authorizer=self._api_authorizer,
        )

        # Add CORS support to all resources
        add_cors_options_method(permissions_resource)
        add_cors_options_method(permission_set_id_resource)

        # Store resources as instance variables so they can be accessed by properties
        self._permissions_resource = permissions_resource
        self._permission_set_id_resource = permission_set_id_resource

    @property
    def permissions_resource(self):
        """Return the permissions resource"""
        return self._permissions_resource

    @property
    def permission_set_id_resource(self):
        """Return the permission set ID resource"""
        return self._permission_set_id_resource
