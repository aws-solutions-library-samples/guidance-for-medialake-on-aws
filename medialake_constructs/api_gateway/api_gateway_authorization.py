"""
API Gateway Authorization module for MediaLake.

This module defines the AuthorizationApi class which sets up API Gateway endpoints
and associated Lambda functions for managing Permission Sets, Groups, and other authorization resources.
"""

from dataclasses import dataclass
from constructs import Construct
from aws_cdk import (
    aws_apigateway as api_gateway,
    aws_dynamodb as dynamodb,
    aws_iam as iam,
    aws_cognito as cognito,
    aws_secretsmanager as secrets_manager,
    aws_apigateway as apigateway,
    Duration,
    Fn,
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
    cognito_user_pool: cognito.UserPool
    auth_table: dynamodb.TableV2


class AuthorizationApi(Construct):
    """
    Authorization API Gateway deployment for managing Permission Sets, Groups, and other authorization resources.
    """

    def __init__(
        self,
        scope: Construct,
        constructor_id: str,
        props: AuthorizationApiProps,
    ) -> None:
        super().__init__(scope, constructor_id)


        common_env_vars = {
            "AUTH_TABLE_NAME": "mlake-demo-authorization-dev",
            "DEBUG_MODE": "true",  # Add a debug mode flag to bypass AVP authorization
        }
        
        self._authorization_authorizer_lambda = Lambda(
            self,
            "AuthorizationAuthorizerLambda",
            config=LambdaConfig(
                name="authorization_authorizer",
                entry="lambdas/auth/custom_authorizer",
                memory_size=256,
                timeout_minutes=1,
                environment_variables=common_env_vars,
            ),
        )
                
        self._api_authorizer = apigateway.RequestAuthorizer(
            self,
            "CustomApiAuthorizer",
            handler=self._authorization_authorizer_lambda.function,
            identity_sources=["method.request.header.Authorization"],
            results_cache_ttl=Duration.minutes(5),
        )

        api_id = Fn.import_value("MediaLakeApiGatewayCore-ApiGatewayId")
        root_resource_id = Fn.import_value("MediaLakeApiGatewayCore-RootResourceId")
                
        api = apigateway.RestApi.from_rest_api_attributes(self, "AuthorizationImportedApi",
            rest_api_id=api_id,
            root_resource_id=root_resource_id
        )
        
        # Create the base authorization resource if it doesn't exist
        # authorization_resource = props.api_resource.get_resource("authorization")
        # if authorization_resource is None:
        authorization_resource = api.root.add_resource("authorization")


        # Set up common environment variables for all Lambda functions
        common_env_vars = {
            "X_ORIGIN_VERIFY_SECRET_ARN": props.x_origin_verify_secret.secret_arn,
            "AUTH_TABLE_NAME": props.auth_table.table_name,
            "COGNITO_USER_POOL_ID": props.cognito_user_pool.user_pool_id,
        }

        # Set up common CORS configuration
        cors_config = api_gateway.CorsOptions(
            allow_origins=["http://localhost:5173"],
            allow_methods=["GET", "PUT", "OPTIONS", "DELETE", "POST"],
            allow_headers=["Content-Type", "Authorization", "X-Amz-Date", "X-Api-Key", "X-Amz-Security-Token"],
            allow_credentials=True,
            max_age=Duration.seconds(300),
        )

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
            authorizer=self._api_authorizer,
        )

        # GET /authorization/# The above code is a comment in Python. Comments are used to provide
        # explanations or notes within the code for better understanding. In this
        # case, the comment is "permission". Comments in Python start with the
        # hash symbol (#) and extend to the end of the line. They are ignored by
        # the Python interpreter and do not affect the execution of the code.
        # permission-sets - List all Permission Sets
        list_permission_sets_lambda = Lambda(
            self,
            "ListPermissionSetsLambda",
            config=LambdaConfig(
                name="permission-sets-get",
                entry="lambdas/api/authorization/permission_sets/get_permission_sets",
                environment_variables=common_env_vars,
            ),
        )
        props.auth_table.grant_read_data(list_permission_sets_lambda.function)

        permission_sets_resource.add_method(
            "GET",
            api_gateway.LambdaIntegration(list_permission_sets_lambda.function),
            authorization_type=api_gateway.AuthorizationType.CUSTOM,
            authorizer=self._api_authorizer,
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
            authorizer=self._api_authorizer,
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
            authorizer=self._api_authorizer,
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
            authorizer=self._api_authorizer,
        )

        # 2. Groups Endpoints
        groups_resource = authorization_resource.add_resource("groups")
        
        # POST /authorization/groups - Create a new Group
        post_groups_lambda = Lambda(
            self,
            "post-groups",
            config=LambdaConfig(
                name="post-groups",
                entry="lambdas/api/authorization/groups/create_group",
                environment_variables=common_env_vars,
            ),
        )
        props.auth_table.grant_read_write_data(post_groups_lambda.function)
        
        groups_resource.add_method(
            "POST",
            api_gateway.LambdaIntegration(post_groups_lambda.function),
            authorization_type=api_gateway.AuthorizationType.CUSTOM,
            authorizer=self._api_authorizer,
        )
        
        # GET /authorization/groups - List all Groups
        authorization_groups_get = Lambda(
            self,
            "authorization-groups-get",
            config=LambdaConfig(
                name="authorization-groups-get",
                entry="lambdas/api/authorization/groups/list_groups",
                environment_variables=common_env_vars,
            ),
        )
        props.auth_table.grant_read_data(authorization_groups_get.function)
        
        groups_resource.add_method(
            "GET",
            api_gateway.LambdaIntegration(authorization_groups_get.function),
            authorization_type=api_gateway.AuthorizationType.CUSTOM,
            authorizer=self._api_authorizer,
        )
        
        # Group by ID resource
        group_id_resource = groups_resource.add_resource("{groupId}")
        
        # GET /authorization/groups/{groupId} - Get details of a specific Group
        authorization_groups_group_id_get = Lambda(
            self,
            "authorization-groups-group-id-get",
            config=LambdaConfig(
                name="authorization-groups-group-id-get",
                entry="lambdas/api/authorization/groups/get_group",
                environment_variables=common_env_vars,
            ),
        )
        props.auth_table.grant_read_data(authorization_groups_group_id_get.function)
        
        group_id_resource.add_method(
            "GET",
            api_gateway.LambdaIntegration(
                authorization_groups_group_id_get.function,
                request_templates={
                    "application/json": '{ "groupId": "$input.params(\'groupId\')" }'
                },
            ),
            authorization_type=api_gateway.AuthorizationType.CUSTOM,
            authorizer=self._api_authorizer,
        )
        
        # PUT /authorization/groups/{groupId} - Update an existing Group
        authorization_groups_group_id_put = Lambda(
            self,
            "authorization-groups-group-id-put",
            config=LambdaConfig(
                name="authorization-groups-group-id-put",
                entry="lambdas/api/authorization/groups/update_group",
                environment_variables=common_env_vars,
            ),
        )
        props.auth_table.grant_read_write_data(authorization_groups_group_id_put.function)
        
        group_id_resource.add_method(
            "PUT",
            api_gateway.LambdaIntegration(
                authorization_groups_group_id_put.function,
                request_templates={
                    "application/json": '{ "groupId": "$input.params(\'groupId\')" }'
                },
            ),
            authorization_type=api_gateway.AuthorizationType.CUSTOM,
            authorizer=self._api_authorizer,
        )
        
        # DELETE /authorization/groups/{groupId} - Delete a Group
        authorization_groups_group_id_delete = Lambda(
            self,
            "authorization-groups-group-id-delete",
            config=LambdaConfig(
                name="authorization-groups-group-id-delete",
                entry="lambdas/api/authorization/groups/delete_group",
                environment_variables=common_env_vars,
            ),
        )
        props.auth_table.grant_read_write_data(authorization_groups_group_id_delete.function)
        
        group_id_resource.add_method(
            "DELETE",
            api_gateway.LambdaIntegration(
                authorization_groups_group_id_delete.function,
                request_templates={
                    "application/json": '{ "groupId": "$input.params(\'groupId\')" }'
                },
            ),
            authorization_type=api_gateway.AuthorizationType.CUSTOM,
            authorizer=self._api_authorizer,
        )
        
        # Group members resource
        group_members_resource = group_id_resource.add_resource("members")
        
        # POST /authorization/groups/{groupId}/members - Add members to a Group
        add_group_members_lambda = Lambda(
            self,
            "authorization-groups-group-id-members-post",
            config=LambdaConfig(
                name="authorization-groups-group-id-members-post",
                entry="lambdas/api/authorization/groups/add_group_members",
                environment_variables=common_env_vars,
            ),
        )
        props.auth_table.grant_read_write_data(add_group_members_lambda.function)
        
        group_members_resource.add_method(
            "POST",
            api_gateway.LambdaIntegration(
                add_group_members_lambda.function,
                request_templates={
                    "application/json": '{ "groupId": "$input.params(\'groupId\')" }'
                },
            ),
            authorization_type=api_gateway.AuthorizationType.CUSTOM,
            authorizer=self._api_authorizer,
        )
        
        # Group member by ID resource
        group_member_id_resource = group_members_resource.add_resource("{userId}")
        
        # DELETE /authorization/groups/{groupId}/members/{userId} - Remove a member from a Group
        remove_group_member_lambda = Lambda(
            self,
            "RemoveGroupMemberLambda",
            config=LambdaConfig(
                name="remove_group_member",
                entry="lambdas/api/authorization/groups/remove_group_member",
                environment_variables=common_env_vars,
            ),
        )
        props.auth_table.grant_read_write_data(remove_group_member_lambda.function)
        
        group_member_id_resource.add_method(
            "DELETE",
            api_gateway.LambdaIntegration(
                remove_group_member_lambda.function,
                request_templates={
                    "application/json": '{ "groupId": "$input.params(\'groupId\')", "userId": "$input.params(\'userId\')" }'
                },
            ),
            authorization_type=api_gateway.AuthorizationType.CUSTOM,
            authorizer=self._api_authorizer,
        )
                
        # 3. Assignments Endpoints
        assignments_resource = authorization_resource.add_resource("assignments")
        
        # User Assignments
        user_assignments_resource = assignments_resource.add_resource("users")
        user_id_assignments_resource = user_assignments_resource.add_resource("{userId}")
        
        # POST /authorization/assignments/users/{userId} - Assign Permission Sets to a User
        assign_ps_to_user_lambda = Lambda(
            self,
            "authorization-assignments-users-post",
            config=LambdaConfig(
                name="authorization-assignments-users-post",
                entry="lambdas/api/authorization/assignments/assign_ps_to_user",
                environment_variables=common_env_vars,
            ),
        )
        props.auth_table.grant_read_write_data(assign_ps_to_user_lambda.function)
        
        user_id_assignments_resource.add_method(
            "POST",
            api_gateway.LambdaIntegration(
                assign_ps_to_user_lambda.function,
                request_templates={
                    "application/json": '{ "userId": "$input.params(\'userId\')" }'
                },
            ),
            authorization_type=api_gateway.AuthorizationType.CUSTOM,
            authorizer=self._api_authorizer,
        )
        
        # GET /authorization/assignments/users/{userId} - List Permission Sets assigned to a User
        authorization_assignments_users_get = Lambda(
            self,
            "authorization-assignments-users-get",
            config=LambdaConfig(
                name="authorization-assignments-users-get",
                entry="lambdas/api/authorization/assignments/list_user_assignments",
                environment_variables=common_env_vars,
            ),
        )
        props.auth_table.grant_read_data(authorization_assignments_users_get.function)
        
        user_id_assignments_resource.add_method(
            "GET",
            api_gateway.LambdaIntegration(
                authorization_assignments_users_get.function,
                request_templates={
                    "application/json": '{ "userId": "$input.params(\'userId\')" }'
                },
            ),
            authorization_type=api_gateway.AuthorizationType.CUSTOM,
            authorizer=self._api_authorizer,
        )
        
        # User Permission Set resource
        user_ps_resource = user_id_assignments_resource.add_resource("permission-sets")
        user_ps_id_resource = user_ps_resource.add_resource("{permissionSetId}")
        
        # DELETE /authorization/assignments/users/{userId}/permission-sets/{permissionSetId} - Remove a Permission Set from a User
        authorization_assignments_users_permission_sets_id_delete = Lambda(
            self,
            "authorization-assignments-users-permission-sets-id-delete",
            config=LambdaConfig(
                name="users-permission-sets-id-delete",
                entry="lambdas/api/authorization/assignments/remove_user_assignment",
                environment_variables=common_env_vars,
            ),
        )
        props.auth_table.grant_read_write_data(authorization_assignments_users_permission_sets_id_delete.function)
        
        user_ps_id_resource.add_method(
            "DELETE",
            api_gateway.LambdaIntegration(
                authorization_assignments_users_permission_sets_id_delete.function,
                request_templates={
                    "application/json": '{ "userId": "$input.params(\'userId\')", "permissionSetId": "$input.params(\'permissionSetId\')" }'
                },
            ),
            authorization_type=api_gateway.AuthorizationType.CUSTOM,
            authorizer=self._api_authorizer,
        )
        
        # Group Assignments
        group_assignments_resource = assignments_resource.add_resource("groups")
        group_id_assignments_resource = group_assignments_resource.add_resource("{groupId}")
        
        # POST /authorization/assignments/groups/{groupId} - Assign Permission Sets to a Group
        authorization_assignments_groups_post = Lambda(
            self,
            "authorization-assignments-groups-post",
            config=LambdaConfig(
                name="authorization-assignments-groups-post",
                entry="lambdas/api/authorization/assignments/assign_ps_to_group",
                environment_variables=common_env_vars,
            ),
        )
        props.auth_table.grant_read_write_data(authorization_assignments_groups_post.function)
        
        group_id_assignments_resource.add_method(
            "POST",
            api_gateway.LambdaIntegration(
                authorization_assignments_groups_post.function,
                request_templates={
                    "application/json": '{ "groupId": "$input.params(\'groupId\')" }'
                },
            ),
            authorization_type=api_gateway.AuthorizationType.CUSTOM,
            authorizer=self._api_authorizer,
        )
        
        # GET /authorization/assignments/groups/{groupId} - List Permission Sets assigned to a Group
        list_group_assignments_lambda = Lambda(
            self,
            "ListGroupAssignmentsLambda",
            config=LambdaConfig(
                name="list_group_assignments",
                entry="lambdas/api/authorization/assignments/list_group_assignments",
                environment_variables=common_env_vars,
            ),
        )
        props.auth_table.grant_read_data(list_group_assignments_lambda.function)
        
        group_id_assignments_resource.add_method(
            "GET",
            api_gateway.LambdaIntegration(
                list_group_assignments_lambda.function,
                request_templates={
                    "application/json": '{ "groupId": "$input.params(\'groupId\')" }'
                },
            ),
            authorization_type=api_gateway.AuthorizationType.CUSTOM,
            authorizer=self._api_authorizer,
        )
        
        # Group Permission Set resource
        group_ps_resource = group_id_assignments_resource.add_resource("permission-sets")
        group_ps_id_resource = group_ps_resource.add_resource("{permissionSetId}")
        
        # DELETE /authorization/assignments/groups/{groupId}/permission-sets/{permissionSetId} - Remove a Permission Set from a Group
        remove_group_assignment_lambda = Lambda(
            self,
            "RemoveGroupAssignmentLambda",
            config=LambdaConfig(
                name="remove_group_assignment",
                entry="lambdas/api/authorization/assignments/remove_group_assignment",
                environment_variables=common_env_vars,
            ),
        )
        props.auth_table.grant_read_write_data(remove_group_assignment_lambda.function)
        
        group_ps_id_resource.add_method(
            "DELETE",
            api_gateway.LambdaIntegration(
                remove_group_assignment_lambda.function,
                request_templates={
                    "application/json": '{ "groupId": "$input.params(\'groupId\')", "permissionSetId": "$input.params(\'permissionSetId\')" }'
                },
            ),
            authorization_type=api_gateway.AuthorizationType.CUSTOM,
            authorizer=self._api_authorizer,
        )
        
        # Add CORS support to all resources
        add_cors_options_method(authorization_resource)
        add_cors_options_method(group_member_id_resource)
        add_cors_options_method(assignments_resource)
        add_cors_options_method(user_assignments_resource)
        add_cors_options_method(user_id_assignments_resource)
        add_cors_options_method(user_ps_resource)
        add_cors_options_method(user_ps_id_resource)
        add_cors_options_method(group_assignments_resource)
        add_cors_options_method(group_id_assignments_resource)
        add_cors_options_method(group_ps_resource)
        add_cors_options_method(group_ps_id_resource)
        add_cors_options_method(permission_sets_resource)
        add_cors_options_method(permission_set_id_resource)
        add_cors_options_method(groups_resource)
        add_cors_options_method(group_id_resource)
        add_cors_options_method(group_members_resource)
