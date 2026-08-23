"""
Cognito Update Stack for Media Lake.

This stack handles additional Cognito User Pool configuration and triggers that need to be
applied after the core Cognito resources are created. This includes:
- Pre-signup Lambda trigger configuration
- Additional Lambda trigger setup
- User pool updates that might conflict if done during initial creation
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
    # Passed as a name rather than a table object: the pre-token-generation
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

        common_env_vars = {
            "AUTH_TABLE_NAME": props.auth_table_name,
            "COGNITO_USER_POOL_ID": props.cognito_user_pool_id,
        }

        # TODO: Create the Cognito Pre-Signup Lambda for additional signup validation
        # Commented out for now as requested
        # self._pre_signup_lambda = Lambda(
        #     self,
        #     "PreSignupLambda",
        #     config=LambdaConfig(
        #         name="cognito_pre_signup",
        #         entry="lambdas/auth/cognito_pre_signup",
        #         memory_size=256,
        #         timeout_minutes=1,
        #         environment_variables=common_env_vars,
        #     ),
        # )

        # Create the Pre-Token Generation Lambda
        from config import config as app_config

        jit = app_config.authZ.jit_provisioning

        pre_token_env_vars = {
            **common_env_vars,
            "DEBUG_MODE": "true",
            # Just-in-time provisioning for first-time federated users. The
            # master switch is deploy-time because it also controls whether the
            # IAM permissions below exist; the default group itself is a runtime
            # setting an administrator edits in System Settings.
            "JIT_PROVISIONING_ENABLED": str(jit.enabled).lower(),
            "JIT_DEFAULT_GROUP": jit.default_group,
            "JIT_ALLOW_IDP_GROUP_ASSERTIONS": str(
                jit.allow_idp_group_assertions
            ).lower(),
            "JIT_IDP_GROUP_MAPPING": json.dumps(jit.idp_group_mapping or {}),
            "SYSTEM_SETTINGS_TABLE_NAME": props.system_settings_table_name or "",
        }

        self._pre_token_generation_lambda = Lambda(
            self,
            "PreTokenGenerationLambda",
            config=LambdaConfig(
                name="pre_token_generation",
                entry="lambdas/auth/pre_token_generation",
                timeout_minutes=1,
                lambda_handler="handler",
                snap_start=False,
                environment_variables=pre_token_env_vars,
            ),
        )

        # Grant permissions for the pre-token generation lambda to interact with the auth table
        auth_table_arn = f"arn:aws:dynamodb:{self.region}:{self.account}:table/{props.auth_table_name}"

        self._pre_token_generation_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "dynamodb:GetItem",
                    "dynamodb:PutItem",
                    "dynamodb:UpdateItem",
                    "dynamodb:Query",
                    "dynamodb:Scan",
                ],
                resources=[auth_table_arn],
            )
        )

        # Extra permissions required only by just-in-time provisioning. Granted
        # conditionally so that deployments with the feature off do not hand the
        # token-path Lambda the ability to change group membership.
        if jit.enabled:
            self._pre_token_generation_lambda.function.add_to_role_policy(
                iam.PolicyStatement(
                    actions=[
                        "cognito-idp:AdminAddUserToGroup",
                        "cognito-idp:AdminListGroupsForUser",
                    ],
                    resources=[props.cognito_user_pool_arn],
                )
            )

            if props.system_settings_table_name:
                system_settings_table_arn = (
                    f"arn:aws:dynamodb:{self.region}:{self.account}:"
                    f"table/{props.system_settings_table_name}"
                )
                self._pre_token_generation_lambda.function.add_to_role_policy(
                    iam.PolicyStatement(
                        actions=["dynamodb:GetItem"],
                        resources=[system_settings_table_arn],
                    )
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
                # "PreSignupLambdaArn": self._pre_signup_lambda.function.function_arn,  # Commented out for now
                "PreTokenGenerationLambdaArn": self._pre_token_generation_lambda.function.function_arn,
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

        # TODO: Grant permissions for Cognito to invoke pre-signup Lambda (commented out for now)
        # self._pre_signup_lambda.function.add_permission(
        #     "CognitoInvokePermissionPreSignup",
        #     principal=iam.ServicePrincipal("cognito-idp.amazonaws.com"),
        #     source_arn=props.cognito_user_pool_arn,
        # )

        # Grant permissions for Cognito to invoke the pre-token generation Lambda
        self._pre_token_generation_lambda.function.add_permission(
            "CognitoInvokePermissionPreTokenGeneration",
            principal=iam.ServicePrincipal("cognito-idp.amazonaws.com"),
            source_arn=props.cognito_user_pool_arn,
        )

    # TODO: Re-enable when pre-signup lambda is uncommented
    # @property
    # def pre_signup_lambda(self):
    #     """Return the pre-signup Lambda function"""
    #     return self._pre_signup_lambda.function

    @property
    def pre_token_generation_lambda(self):
        """Return the pre-token generation Lambda function"""
        return self._pre_token_generation_lambda.function

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
