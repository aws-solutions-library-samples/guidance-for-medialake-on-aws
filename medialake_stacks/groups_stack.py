"""
Groups Stack for MediaLake.

This module defines the GroupsStack class which sets up API Gateway endpoints
and associated Lambda functions for managing Groups and group members.
"""

from dataclasses import dataclass

import aws_cdk as cdk
from aws_cdk import aws_apigateway as api_gateway
from aws_cdk import aws_apigateway as apigateway
from aws_cdk import aws_cognito as cognito
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_iam as iam
from constructs import Construct

from medialake_constructs.api_gateway.api_gateway_utils import add_cors_options_method
from medialake_constructs.auth.authorizer_utils import (
    ensure_shared_authorizer_permissions,
)
from medialake_constructs.shared_constructs.lambda_base import Lambda, LambdaConfig


@dataclass
class GroupsStackProps:
    """Properties for the Groups Stack."""

    # x_origin_verify_secret: secrets_manager.Secret
    cognito_user_pool: cognito.UserPool
    auth_table: dynamodb.TableV2
    authorizer: apigateway.IAuthorizer
    api_resource: apigateway.RestApi


class GroupsStack(cdk.NestedStack):
    """
    Groups Stack for managing Groups and group members.
    """

    def __init__(
        self, scope: Construct, constructor_id: str, props: GroupsStackProps, **kwargs
    ) -> None:
        super().__init__(scope, constructor_id, **kwargs)

        # Use the shared custom authorizer
        # api_id = Fn.import_value("MediaLakeApiGatewayCore-ApiGatewayId")

        # self._api_authorizer = create_shared_custom_authorizer(
        #     self, "GroupsCustomApiAuthorizer", api_gateway_id=api_id
        # )

        # root_resource_id = Fn.import_value("MediaLakeApiGatewayCore-RootResourceId")

        # api = apigateway.RestApi.from_rest_api_attributes(
        #     self,
        #     "GroupsImportedApi",
        #     rest_api_id=api_id,
        #     root_resource_id=root_resource_id,
        # )

        # Ensure the shared authorizer has permissions for this API Gateway
        ensure_shared_authorizer_permissions(self, "Groups", props.api_resource)

        # Create the groups resource directly off the root
        groups_resource = props.api_resource.root.add_resource("groups")

        # Set up common environment variables for all Lambda functions
        common_env_vars = {
            # "X_ORIGIN_VERIFY_SECRET_ARN": props.x_origin_verify_secret.secret_arn,
            "AUTH_TABLE_NAME": props.auth_table.table_name,
            "COGNITO_USER_POOL_ID": props.cognito_user_pool.user_pool_id,
        }

        # Single unified Lambda for all groups operations
        groups_unified_lambda = Lambda(
            self,
            "groups-unified",
            config=LambdaConfig(
                name="groups-unified",
                entry="lambdas/api/groups_unified",
                environment_variables=common_env_vars,
            ),
        )
        
        # Grant permissions
        props.auth_table.grant_read_write_data(groups_unified_lambda.function)
        
        # Grant permissions for Cognito group management
        groups_unified_lambda.function.add_to_role_policy(
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

        # POST /groups - Create a new Group
        groups_post_method = groups_resource.add_method(
            "POST",
            api_gateway.LambdaIntegration(groups_unified_lambda.function),
            # authorization_type=api_gateway.AuthorizationType.CUSTOM,
            # authorizer=props.authorizer,
        )

        cfn_method = groups_resource.node.default_child
        cfn_method.authorization_type = "CUSTOM"
        cfn_method.authorizer_id = props.authorizer.authorizer_id

        # GET /groups - List all Groups
        groups_get_method = groups_resource.add_method(
            "GET",
            api_gateway.LambdaIntegration(groups_unified_lambda.function),
            # authorization_type=api_gateway.AuthorizationType.CUSTOM,
            # authorizer=props.authorizer,
        )

        cfn_method = groups_get_method.node.default_child
        cfn_method.authorization_type = "CUSTOM"
        cfn_method.authorizer_id = props.authorizer.authorizer_id

        # Group by ID resource
        group_id_resource = groups_resource.add_resource("{groupId}")

        # GET /groups/{groupId} - Get details of a specific Group
        group_id_get_method = group_id_resource.add_method(
            "GET",
            api_gateway.LambdaIntegration(
                groups_unified_lambda.function,
                request_templates={
                    "application/json": '{ "groupId": "$input.params(\'groupId\')" }'
                },
            ),
            # authorization_type=api_gateway.AuthorizationType.CUSTOM,
            # authorizer=self._api_authorizer,
        )

        cfn_method = group_id_get_method.node.default_child
        cfn_method.authorization_type = "CUSTOM"
        cfn_method.authorizer_id = props.authorizer.authorizer_id

        # PUT /groups/{groupId} - Update an existing Group
        group_id_put_method = group_id_resource.add_method(
            "PUT",
            api_gateway.LambdaIntegration(
                groups_unified_lambda.function,
                request_templates={
                    "application/json": '{ "groupId": "$input.params(\'groupId\')" }'
                },
            ),
            # authorization_type=api_gateway.AuthorizationType.CUSTOM,
            # authorizer=props.authorizer,
        )
        cfn_method = group_id_put_method.node.default_child
        cfn_method.authorization_type = "CUSTOM"
        cfn_method.authorizer_id = props.authorizer.authorizer_id

        # DELETE /groups/{groupId} - Delete a Group
        group_id_delete_method = group_id_resource.add_method(
            "DELETE",
            api_gateway.LambdaIntegration(
                groups_unified_lambda.function,
                request_templates={
                    "application/json": '{ "groupId": "$input.params(\'groupId\')" }'
                },
            ),
            # authorization_type=api_gateway.AuthorizationType.CUSTOM,
            # authorizer=self._api_authorizer,
        )
        cfn_method = group_id_delete_method.node.default_child
        cfn_method.authorization_type = "CUSTOM"
        cfn_method.authorizer_id = props.authorizer.authorizer_id

        # Group members resource
        group_members_resource = group_id_resource.add_resource("members")

        # POST /groups/{groupId}/members - Add members to a Group
        group_members_post_method = group_members_resource.add_method(
            "POST",
            api_gateway.LambdaIntegration(
                groups_unified_lambda.function,
                request_templates={
                    "application/json": '{ "groupId": "$input.params(\'groupId\')" }'
                },
            ),
            # authorization_type=api_gateway.AuthorizationType.CUSTOM,
            # authorizer=props.authorizer,
        )
        cfn_method = group_members_post_method.node.default_child
        cfn_method.authorization_type = "CUSTOM"
        cfn_method.authorizer_id = props.authorizer.authorizer_id

        # Group member by ID resource
        group_member_id_resource = group_members_resource.add_resource("{userId}")

        # DELETE /groups/{groupId}/members/{userId} - Remove a member from a Group
        group_member_id_delete_method = group_member_id_resource.add_method(
            "DELETE",
            api_gateway.LambdaIntegration(
                groups_unified_lambda.function,
                request_templates={
                    "application/json": '{ "groupId": "$input.params(\'groupId\')", "userId": "$input.params(\'userId\')" }'
                },
            ),
            # authorization_type=api_gateway.AuthorizationType.CUSTOM,
            # authorizer=self._api_authorizer,
        )
        cfn_method = group_member_id_delete_method.node.default_child
        cfn_method.authorization_type = "CUSTOM"
        cfn_method.authorizer_id = props.authorizer.authorizer_id

        # Add CORS support to all resources
        add_cors_options_method(groups_resource)
        add_cors_options_method(group_id_resource)
        add_cors_options_method(group_members_resource)
        add_cors_options_method(group_member_id_resource)
        add_cors_options_method(groups_resource)
        add_cors_options_method(group_members_resource)
