"""
Authorization Stack for Media Lake.

This stack defines the AWS resources for the new authorization system, including:
- DynamoDB table for authorization configuration
- Amazon Verified Permissions (AVP) Policy Store
- Lambda functions for authorization and policy synchronization
- IAM roles and permissions
"""

import datetime
from dataclasses import dataclass
from typing import Any

import aws_cdk as cdk
from aws_cdk import CustomResource, Duration, RemovalPolicy, Stack
from aws_cdk import aws_cognito as cognito
from aws_cdk import aws_events as events
from aws_cdk import aws_events_targets as targets
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_lambda_event_sources as lambda_event_sources
from aws_cdk import aws_verifiedpermissions as avp
from constructs import Construct

from constants import Lambda as LambdaConstants
from medialake_constructs.auth.shared_authorizer_construct import (
    SharedAuthorizerConstruct,
    SharedAuthorizerConstructProps,
)

# DynamoDB table is now created in the Cognito construct
from medialake_constructs.shared_constructs.lambda_base import Lambda, LambdaConfig


@dataclass
class AuthorizationStackProps:
    """Configuration for Authorization Stack."""

    cognito_user_pool: cognito.UserPool
    cognito_user_pool_client: cognito.UserPoolClient
    cognito_construct: Any


class AuthorizationStack(Stack):
    """
    Stack for Authorization resources.

    This stack creates the DynamoDB table, AVP Policy Store, Lambda functions,
    and IAM roles for the new authorization system.
    """

    def __init__(
        self, scope: Construct, id: str, props: AuthorizationStackProps, **kwargs
    ):
        super().__init__(scope, id, **kwargs)

        # Get the auth table from the Cognito construct (to avoid circular dependencies)
        self._auth_table = props.cognito_construct.auth_table

        # 2. Create the AVP Policy Store
        self._policy_store = avp.CfnPolicyStore(
            self,
            "AVPPolicyStore",
            validation_settings=avp.CfnPolicyStore.ValidationSettingsProperty(
                mode="OFF"
            ),
            schema=avp.CfnPolicyStore.SchemaDefinitionProperty(
                cedar_json="""{
                    "MediaLake": {
                        "entityTypes": {
                            "User": {
                                "memberOfTypes": ["Group"],
                                "shape": {
                                    "type": "Record",
                                    "attributes": {}
                                }
                            },
                            "Group": {
                                "shape": {
                                    "type": "Record",
                                    "attributes": {}
                                }
                            },
                            "Resource": {
                                "shape": {
                                    "type": "Record",
                                    "attributes": {}
                                }
                            }
                        },
                        "actions": {
                            "Action": {
                                "appliesTo": {
                                    "principalTypes": ["User", "Group"],
                                    "resourceTypes": ["Resource"],
                                    "context": {
                                        "type": "Record",
                                        "attributes": {}
                                    }
                                }
                            }
                        }
                    }
                }"""
            ),
        )

        # Create a default "permit all" policy in the AVP Policy Store
        self._default_policy = avp.CfnPolicy(
            self,
            "DefaultPermitAllPolicy",
            policy_store_id=self._policy_store.attr_policy_store_id,
            definition=avp.CfnPolicy.PolicyDefinitionProperty(
                static=avp.CfnPolicy.StaticPolicyDefinitionProperty(
                    statement="permit(principal, action, resource);",
                    description="Default policy that permits all actions",
                )
            ),
        )

        # Create the shared custom authorizer
        self._shared_authorizer = SharedAuthorizerConstruct(
            self,
            "SharedAuthorizer",
            props=SharedAuthorizerConstructProps(
                auth_table_name=self._auth_table.table_name,
                avp_policy_store_id=self._policy_store.attr_policy_store_id,
                avp_policy_store_arn=f"arn:aws:verifiedpermissions::{cdk.Aws.ACCOUNT_ID}:policy-store/{self._policy_store.attr_policy_store_id}",
                cognito_user_pool_id=props.cognito_user_pool.user_pool_id,
            ),
        )

        # Grant table read access to the shared authorizer
        self._auth_table.grant_read_data(self._shared_authorizer.authorizer_lambda)

        # Common environment variables for Lambda functions
        common_env_vars = {
            "AUTH_TABLE_NAME": self._auth_table.table_name,
            "AVP_POLICY_STORE_ID": self._policy_store.attr_policy_store_id,
            "DEBUG_MODE": "true",
            "COGNITO_USER_POOL_ID": props.cognito_user_pool.user_pool_id,
        }

        # 3. Use the Custom API Gateway Lambda Authorizer from props
        # self._custom_authorizer_lambda = props.custom_authorizer_lambda

        self._custom_authorizer_lambda = Lambda(
            self,
            "CustomAuthorizerLambda",
            config=LambdaConfig(
                name="custom_api_authorizer",
                entry="lambdas/auth/custom_authorizer",
                memory_size=256,
                timeout_minutes=1,
                snap_start=False,  # Disable SnapStart to avoid versioning
                environment_variables=common_env_vars,
            ),
        )

        self._auth_table.grant_read_data(self._custom_authorizer_lambda.function)
        self._custom_authorizer_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "verifiedpermissions:IsAuthorizedWithToken",
                    "verifiedpermissions:IsAuthorized",
                ],
                resources=[
                    f"arn:aws:verifiedpermissions::{cdk.Aws.ACCOUNT_ID}:policy-store/{self._policy_store.attr_policy_store_id}"
                ],
            )
        )

        # 4. Create the DynamoDB Stream Lambda for policy synchronization
        self._policy_sync_lambda = Lambda(
            self,
            "PolicySyncLambda",
            config=LambdaConfig(
                name="policy_sync",
                entry="lambdas/auth/policy_sync",
                memory_size=256,
                timeout_minutes=5,
                environment_variables=common_env_vars,
            ),
        )

        # 5. Create the Auth Table Seeder Lambda for seeding default permission sets
        self._auth_seeder_lambda = Lambda(
            self,
            "AuthTableSeederLambda",
            config=LambdaConfig(
                name="auth-table-seeder",
                entry="lambdas/auth/auth_seeder",
                memory_size=256,
                timeout_minutes=2,
                environment_variables=common_env_vars,
            ),
        )

        # Add DynamoDB Stream as an event source for the Policy Sync Lambda
        self._policy_sync_lambda.function.add_event_source(
            lambda_event_sources.DynamoEventSource(
                table=self._auth_table,
                starting_position=lambda_.StartingPosition.LATEST,
                batch_size=100,
                retry_attempts=3,
            )
        )

        # 6. Cognito Pre-Signup Lambda is now handled in CognitoUpdateStack
        # This avoids circular dependencies and timing issues

        # Add the Cognito Identity Source to the AVP Policy Store
        # Get the client ID directly from the cognito construct
        cognito_client_id = props.cognito_user_pool_client.user_pool_client_id

        self._identity_source = avp.CfnIdentitySource(
            self,
            "CognitoIdentitySource",
            policy_store_id=self._policy_store.attr_policy_store_id,
            configuration=avp.CfnIdentitySource.IdentitySourceConfigurationProperty(
                cognito_user_pool_configuration=avp.CfnIdentitySource.CognitoUserPoolConfigurationProperty(
                    user_pool_arn=props.cognito_user_pool.user_pool_arn,
                    client_ids=[cognito_client_id],
                )
            ),
            principal_entity_type="MediaLake::User",
        )

        # Policy Sync Lambda: Permissions to manage policies in AVP
        self._policy_sync_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "verifiedpermissions:CreatePolicy",
                    "verifiedpermissions:UpdatePolicy",
                    "verifiedpermissions:DeletePolicy",
                    "verifiedpermissions:ListPolicies",
                    "verifiedpermissions:GetPolicy",
                    "verifiedpermissions:BatchIsAuthorized",
                ],
                resources=[
                    f"arn:aws:verifiedpermissions::{cdk.Aws.ACCOUNT_ID}:policy-store/{self._policy_store.attr_policy_store_id}"
                ],
            )
        )

        # Cognito Pre-Token Generation Lambda permissions and environment variables
        # are now configured in the Cognito stack to avoid circular dependencies

        # Pre-Signup Lambda and trigger configuration is now handled in CognitoUpdateStack
        # This avoids circular dependencies and timing issues

        # Auth Table Seeder Lambda: Write access to the auth table
        self._auth_table.grant_read_write_data(self._auth_seeder_lambda.function)

        # 9. Create a Custom Resource to seed the default permission sets
        self._auth_seeder_custom_resource = CustomResource(
            self,
            "AuthTableSeederCustomResource",
            service_token=self._auth_seeder_lambda.function.function_arn,
            removal_policy=RemovalPolicy.RETAIN,  # Don't remove permission sets on stack deletion
            properties={
                "timestamp": str(
                    datetime.datetime.now().timestamp()
                ),  # Force update on each deployment
            },
        )

        # Lambda warming for custom_authorizer
        # Note: pre_token_generation lambda warming is now handled in CognitoUpdateStack
        events.Rule(
            self,
            "CustomAuthorizerWarmerRule",
            schedule=events.Schedule.rate(
                Duration.minutes(LambdaConstants.WARMER_INTERVAL_MINUTES)
            ),
            targets=[
                targets.LambdaFunction(
                    self._custom_authorizer_lambda.function,
                    event=events.RuleTargetInput.from_object({"lambda_warmer": True}),
                ),
            ],
            description="Keeps custom_authorizer Lambda warm via scheduled EventBridge rule.",
        )

    @property
    def auth_table(self):
        """Return the authorization table"""
        return self._auth_table

    @property
    def policy_store(self):
        """Return the AVP policy store"""
        return self._policy_store

    @property
    def policy_sync_lambda(self):
        """Return the policy sync Lambda function"""
        return self._policy_sync_lambda.function

    # pre_signup_lambda is now handled in CognitoUpdateStack

    @property
    def auth_seeder_lambda(self):
        """Return the auth table seeder Lambda function"""
        return self._auth_seeder_lambda.function

    @property
    def authorizer_lambda(self):
        """Return the custom authorizer Lambda function"""
        return self._custom_authorizer_lambda.function

    @property
    def shared_authorizer_lambda(self):
        """Return the shared authorizer Lambda function"""
        return self._shared_authorizer.authorizer_lambda
