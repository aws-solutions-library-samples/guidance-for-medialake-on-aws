"""
Cognito Update Stack for Media Lake.

This stack attaches the Lambda triggers to the Cognito User Pool after the core
Cognito resources are created, through a custom resource rather than the pool's
own LambdaConfig, to avoid circular dependencies between stacks:
- Pre token generation (always): resolves groups into the permissions claim
- Post confirmation (when federated default-group assignment is enabled)
- Inbound federation (when IdP group mapping is enabled)
"""

import datetime
import json
from dataclasses import dataclass
from typing import Optional

import aws_cdk as cdk
from aws_cdk import Stack
from aws_cdk import aws_cognito as cognito
from aws_cdk import aws_iam as iam
from aws_cdk import custom_resources as cr
from constructs import Construct

from medialake_constructs.shared_constructs.lambda_base import Lambda, LambdaConfig


@dataclass
class CognitoUpdateStackProps:
    """Configuration for Cognito Update Stack."""

    cognito_user_pool: cognito.IUserPool
    cognito_user_pool_id: str
    cognito_user_pool_arn: str
    auth_table_name: str
    # Passed as a name rather than a table object: the post confirmation
    # Lambda's IAM policy is built here with an inline ARN to avoid the
    # cross-stack dependency cycle that importing the table would create.
    system_settings_table_name: Optional[str] = None


class CognitoUpdateStack(Stack):
    """
    Stack for Cognito User Pool updates and additional trigger configuration.

    This stack applies additional configuration to the Cognito User Pool after
    it has been created, including triggers that might conflict if applied
    during the initial user pool creation.
    """

    def __init__(
        self, scope: Construct, id: str, props: CognitoUpdateStackProps, **kwargs
    ):
        super().__init__(scope, id, **kwargs)

        from config import config as app_config

        jit = app_config.authZ.jit_provisioning

        # Create the Pre-Token Generation Lambda. It only shapes claims: it
        # resolves the user's Cognito groups into the custom:permissions claim
        # and never changes group membership.
        self._pre_token_generation_lambda = Lambda(
            self,
            "PreTokenGenerationLambda",
            config=LambdaConfig(
                name="pre_token_generation",
                entry="lambdas/auth/pre_token_generation",
                timeout_minutes=1,
                lambda_handler="handler",
                snap_start=False,
                environment_variables={
                    "AUTH_TABLE_NAME": props.auth_table_name,
                    "DEBUG_MODE": "true",
                },
            ),
        )

        # Read-only: group records and permission sets are fetched by key.
        auth_table_arn = f"arn:aws:dynamodb:{self.region}:{self.account}:table/{props.auth_table_name}"
        self._pre_token_generation_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=["dynamodb:GetItem"],
                resources=[auth_table_arn],
            )
        )

        # Post confirmation trigger: assigns the default group to a federated
        # user on their first sign-in. Cognito invokes it once per user, right
        # after it creates the profile, so the assignment is never re-applied
        # over an administrator's later change.
        #
        # Only created when the feature is enabled, so that deployments with it
        # off have no Lambda able to change group membership. The default group
        # is carried in as an environment variable and can be overridden at
        # runtime from System Settings.
        self._post_confirmation_lambda = None
        if jit.enabled:
            self._post_confirmation_lambda = Lambda(
                self,
                "PostConfirmationLambda",
                config=LambdaConfig(
                    name="post_confirmation",
                    entry="lambdas/auth/post_confirmation",
                    # Cognito allows a trigger 5 seconds regardless.
                    timeout_minutes=1,
                    lambda_handler="handler",
                    snap_start=False,
                    environment_variables={
                        "JIT_DEFAULT_GROUP": jit.default_group,
                        "SYSTEM_SETTINGS_TABLE_NAME": (
                            props.system_settings_table_name or ""
                        ),
                        "JIT_ALLOW_IDP_GROUP_ASSERTIONS": str(
                            jit.allow_idp_group_assertions
                        ).lower(),
                        "JIT_IDP_GROUP_MAPPING": json.dumps(
                            jit.idp_group_mapping or {}
                        ),
                        # With the inbound federation trigger attached,
                        # custom:groups already holds mapped Media Lake ids.
                        "JIT_GROUPS_PRE_MAPPED": str(
                            jit.inbound_federation_trigger_enabled
                        ).lower(),
                    },
                ),
            )

            self._post_confirmation_lambda.function.add_to_role_policy(
                iam.PolicyStatement(
                    actions=["cognito-idp:AdminAddUserToGroup"],
                    resources=[props.cognito_user_pool_arn],
                )
            )

            if props.system_settings_table_name:
                system_settings_table_arn = (
                    f"arn:aws:dynamodb:{self.region}:{self.account}:"
                    f"table/{props.system_settings_table_name}"
                )
                self._post_confirmation_lambda.function.add_to_role_policy(
                    iam.PolicyStatement(
                        actions=["dynamodb:GetItem"],
                        resources=[system_settings_table_arn],
                    )
                )

            self._post_confirmation_lambda.function.add_permission(
                "CognitoInvokePermissionPostConfirmation",
                principal=iam.ServicePrincipal("cognito-idp.amazonaws.com"),
                source_arn=props.cognito_user_pool_arn,
            )

        # Inbound federation trigger. Normalizes and remaps the group assertion
        # coming from an external identity provider before Cognito creates or
        # updates the federated user profile. Only created when configured,
        # since attaching it changes how provider attributes are stored.
        self._inbound_federation_lambda = None
        if jit.enabled and jit.inbound_federation_trigger_enabled:
            # Which raw provider attribute carries group membership, per
            # provider. Cognito applies the provider's attribute mapping to
            # whatever the trigger returns, so the trigger has to write back to
            # the raw claim name rather than to custom:groups directly.
            provider_groups_claims = {}
            for provider in app_config.authZ.identity_providers:
                if provider.identity_provider_method == "oidc":
                    provider_groups_claims[provider.identity_provider_name] = (
                        provider.oidc_groups_claim
                    )
                elif provider.identity_provider_method == "saml":
                    # Matches the SAML attribute mapping in CognitoConstruct.
                    provider_groups_claims[provider.identity_provider_name] = (
                        "http://schemas.microsoft.com/ws/2008/06/identity/claims/groups"
                    )

            self._inbound_federation_lambda = Lambda(
                self,
                "InboundFederationLambda",
                config=LambdaConfig(
                    name="inbound_federation",
                    entry="lambdas/auth/inbound_federation",
                    # Cognito allows this trigger 5 seconds.
                    timeout_minutes=1,
                    lambda_handler="handler",
                    snap_start=False,
                    environment_variables={
                        "JIT_ALLOW_IDP_GROUP_ASSERTIONS": str(
                            jit.allow_idp_group_assertions
                        ).lower(),
                        "JIT_IDP_GROUP_MAPPING": json.dumps(
                            jit.idp_group_mapping or {}
                        ),
                        "JIT_PROVIDER_GROUPS_CLAIM": json.dumps(provider_groups_claims),
                    },
                ),
            )

            self._inbound_federation_lambda.function.add_permission(
                "CognitoInvokePermissionInboundFederation",
                principal=iam.ServicePrincipal("cognito-idp.amazonaws.com"),
                source_arn=props.cognito_user_pool_arn,
            )

        # Create a Lambda function for updating Cognito User Pool triggers
        self._cognito_trigger_update_lambda = Lambda(
            self,
            "CognitoTriggerUpdateProvider",
            config=LambdaConfig(
                name="cognito_trigger_update",
                entry="lambdas/custom_resources/auth/cognito_trigger_update",
                memory_size=256,
                timeout_minutes=5,
                environment_variables={},
            ),
        )

        # Grant permission for the custom resource Lambda to update Cognito
        self._cognito_trigger_update_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "cognito-idp:DescribeUserPool",
                    "cognito-idp:UpdateUserPool",
                ],
                resources=[props.cognito_user_pool_arn],
            )
        )

        # Grant permission to read CloudFront domain from SSM for email templates
        cloudfront_domain_ssm_param = app_config.ssm_param(
            "cloudfront-distribution-domain"
        )
        self._cognito_trigger_update_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=["ssm:GetParameter"],
                resources=[
                    f"arn:aws:ssm:{self.region}:{self.account}:parameter{cloudfront_domain_ssm_param}"
                ],
            )
        )

        # Create a provider for the Cognito trigger updates
        cognito_update_provider = cr.Provider(
            self,
            "CognitoUpdateProvider",
            on_event_handler=self._cognito_trigger_update_lambda.function,  # type: ignore
        )

        # Create a custom resource to update the Cognito triggers
        self._cognito_trigger_update = cdk.CustomResource(
            self,
            "CognitoTriggerUpdate",
            service_token=cognito_update_provider.service_token,
            properties={
                "UserPoolId": props.cognito_user_pool_id,
                "PreTokenGenerationLambdaArn": self._pre_token_generation_lambda.function.function_arn,
                # Empty when the feature is not enabled, which the custom
                # resource treats as "detach it if present".
                "PostConfirmationLambdaArn": (
                    self._post_confirmation_lambda.function.function_arn
                    if self._post_confirmation_lambda
                    else ""
                ),
                # Empty when the inbound federation trigger is not enabled, which
                # the custom resource treats as "detach it if present".
                "InboundFederationLambdaArn": (
                    self._inbound_federation_lambda.function.function_arn
                    if self._inbound_federation_lambda
                    else ""
                ),
                "CloudFrontDomainSsmParam": cloudfront_domain_ssm_param,
                "Timestamp": str(
                    datetime.datetime.now().timestamp()
                ),  # Force update on each deployment
            },
        )

        # Grant permissions for Cognito to invoke the pre-token generation Lambda
        self._pre_token_generation_lambda.function.add_permission(
            "CognitoInvokePermissionPreTokenGeneration",
            principal=iam.ServicePrincipal("cognito-idp.amazonaws.com"),
            source_arn=props.cognito_user_pool_arn,
        )

    @property
    def pre_token_generation_lambda(self):
        """Return the pre-token generation Lambda function"""
        return self._pre_token_generation_lambda.function

    @property
    def post_confirmation_lambda(self):
        """Return the post confirmation Lambda function, if it was created."""
        return (
            self._post_confirmation_lambda.function
            if self._post_confirmation_lambda
            else None
        )

    @property
    def inbound_federation_lambda(self):
        """Return the inbound federation Lambda function, if it was created."""
        return (
            self._inbound_federation_lambda.function
            if self._inbound_federation_lambda
            else None
        )

    @property
    def cognito_trigger_update(self):
        """Return the Cognito trigger update custom resource"""
        return self._cognito_trigger_update
