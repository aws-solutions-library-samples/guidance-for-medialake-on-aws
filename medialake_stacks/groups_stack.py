"""
Groups Stack for MediaLake.

This module defines the GroupsStack class which sets up API Gateway endpoints
and associated Lambda functions for managing Groups and group members.
"""

from dataclasses import dataclass

import aws_cdk as cdk
from aws_cdk import Fn
from aws_cdk import aws_apigateway as api_gateway
from aws_cdk import aws_apigateway as apigateway
from aws_cdk import aws_cognito as cognito
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_iam as iam
from constructs import Construct

from medialake_constructs.api_gateway.api_gateway_utils import add_cors_options_method
from medialake_constructs.auth.authorizer_utils import (
    create_shared_custom_authorizer,
    ensure_shared_authorizer_permissions,
)
from medialake_constructs.shared_constructs.lambda_base import Lambda, LambdaConfig


@dataclass
class GroupsStackProps:
    """Properties for the Groups Stack."""

    # x_origin_verify_secret: secrets_manager.Secret
    cognito_user_pool: cognito.UserPool
    auth_table: dynamodb.TableV2


class GroupsStack(cdk.NestedStack):
    """
    Groups Stack for managing Groups and group members.
    """

    def __init__(
        self, scope: Construct, constructor_id: str, props: GroupsStackProps, **kwargs
    ) -> None:
        super().__init__(scope, constructor_id, **kwargs)

        # Use the shared custom authorizer
        api_id = Fn.import_value("MediaLakeApiGatewayCore-ApiGatewayId")

        self._api_authorizer = create_shared_custom_authorizer(
            self, "GroupsCustomApiAuthorizer", api_gateway_id=api_id
        )

        root_resource_id = Fn.import_value("MediaLakeApiGatewayCore-RootResourceId")

        api = apigateway.RestApi.from_rest_api_attributes(
            self,
            "GroupsImportedApi",
            rest_api_id=api_id,
            root_resource_id=root_resource_id,
        )

        # Ensure the shared authorizer has permissions for this API Gateway
        ensure_shared_authorizer_permissions(self, "Groups", api)

        # Create the groups resource directly off the root
        groups_resource = api.root.add_resource("groups")

        # Set up common environment variables for all Lambda functions
        common_env_vars = {
            # "X_ORIGIN_VERIFY_SECRET_ARN": props.x_origin_verify_secret.secret_arn,
            "AUTH_TABLE_NAME": props.auth_table.table_name,
            "COGNITO_USER_POOL_ID": props.cognito_user_pool.user_pool_id,
        }

        # POST /groups - Create a new Group
        post_groups_lambda = Lambda(
            self,
            "post-groups",
            config=LambdaConfig(
                name="post-groups",
                entry="lambdas/api/groups/post_groups",
                environment_variables=common_env_vars,
            ),
        )
        props.auth_table.grant_read_write_data(post_groups_lambda.function)

        # Grant permissions for Cognito group management
        post_groups_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "cognito-idp:CreateGroup",
                    "cognito-idp:DeleteGroup",
                    "cognito-idp:GetGroup",
                    "cognito-idp:ListGroups",
                ],
                resources=[props.cognito_user_pool.user_pool_arn],
            )
        )

        groups_resource.add_method(
            "POST",
            api_gateway.LambdaIntegration(post_groups_lambda.function),
            authorization_type=api_gateway.AuthorizationType.CUSTOM,
            authorizer=self._api_authorizer,
        )

        # GET /groups - List all Groups
        authorization_groups_get = Lambda(
            self,
            "authorization-groups-get",
            config=LambdaConfig(
                name="authorization-groups-get",
                entry="lambdas/api/groups/get_groups",
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

        # GET /groups/{groupId} - Get details of a specific Group
        authorization_groups_group_id_get = Lambda(
            self,
            "authorization-groups-group-id-get",
            config=LambdaConfig(
                name="authorization-groups-group-id-get",
                entry="lambdas/api/groups/get_group",
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

        # PUT /groups/{groupId} - Update an existing Group
        authorization_groups_group_id_put = Lambda(
            self,
            "authorization-groups-group-id-put",
            config=LambdaConfig(
                name="authorization-groups-group-id-put",
                entry="lambdas/api/groups/update_group",
                environment_variables=common_env_vars,
            ),
        )
        props.auth_table.grant_read_write_data(
            authorization_groups_group_id_put.function
        )

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

        # DELETE /groups/{groupId} - Delete a Group
        authorization_groups_group_id_delete = Lambda(
            self,
            "authorization-groups-group-id-delete",
            config=LambdaConfig(
                name="authorization-groups-group-id-delete",
                entry="lambdas/api/groups/rp_groupId/del_groupId",
                environment_variables=common_env_vars,
            ),
        )
        props.auth_table.grant_read_write_data(
            authorization_groups_group_id_delete.function
        )

        # Grant permissions for Cognito group management
        authorization_groups_group_id_delete.function.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "cognito-idp:CreateGroup",
                    "cognito-idp:DeleteGroup",
                    "cognito-idp:GetGroup",
                    "cognito-idp:ListGroups",
                ],
                resources=[props.cognito_user_pool.user_pool_arn],
            )
        )

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

        # POST /groups/{groupId}/members - Add members to a Group
        add_group_members_lambda = Lambda(
            self,
            "authorization-groups-group-id-members-post",
            config=LambdaConfig(
                name="authorization-groups-group-id-members-post",
                entry="lambdas/api/groups/add_group_members",
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

        # DELETE /groups/{groupId}/members/{userId} - Remove a member from a Group
        remove_group_member_lambda = Lambda(
            self,
            "RemoveGroupMemberLambda",
            config=LambdaConfig(
                name="remove_group_member",
                entry="lambdas/api/groups/remove_group_member",
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

        # Add CORS support to all resources
        add_cors_options_method(groups_resource)
        add_cors_options_method(group_id_resource)
        add_cors_options_method(group_members_resource)
        add_cors_options_method(group_member_id_resource)
