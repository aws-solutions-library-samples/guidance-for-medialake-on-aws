"""
Cognito Stack for Media Lake.

This stack creates the Cognito User Pool and related resources that can be shared
across multiple stacks without creating circular dependencies.
"""

from dataclasses import dataclass

from aws_cdk import CfnOutput, RemovalPolicy, Stack
from aws_cdk import aws_cognito as cognito
from constructs import Construct

from medialake_constructs.cognito import CognitoConstruct, CognitoProps


@dataclass
class CognitoStackProps:
    """Configuration for Cognito Stack."""


class CognitoStack(Stack):
    """
    Stack for Cognito resources.

    This stack creates the Cognito User Pool, Identity Pool, and related resources
    that can be shared across multiple stacks.
    """

    def __init__(
        self, scope: Construct, id: str, props: CognitoStackProps = None, **kwargs
    ):
        super().__init__(scope, id, **kwargs)

        # Create Cognito construct
        self._cognito_construct = CognitoConstruct(
            self,
            "Cognito",
            props=CognitoProps(
                self_sign_up_enabled=False,
                auto_verify_email=True,
                auto_verify_phone=True,
                sign_in_with_email=True,
                generate_secret=False,
                admin_user_password=True,
                user_password=True,
                user_srp=True,
                removal_policy=RemovalPolicy.DESTROY,
            ),
        )

        # Export Cognito resources for cross-stack usage
        CfnOutput(
            self,
            "UserPoolId",
            value=self._cognito_construct.user_pool_id,
            export_name=f"{self.stack_name}-UserPoolId",
        )

        CfnOutput(
            self,
            "UserPoolArn",
            value=self._cognito_construct.user_pool_arn,
            export_name=f"{self.stack_name}-UserPoolArn",
        )

        CfnOutput(
            self,
            "UserPoolClientId",
            value=self._cognito_construct.user_pool_client_id,
            export_name=f"{self.stack_name}-UserPoolClientId",
        )

        CfnOutput(
            self,
            "IdentityPoolId",
            value=self._cognito_construct.identity_pool,
            export_name=f"{self.stack_name}-IdentityPoolId",
        )

        CfnOutput(
            self,
            "CognitoDomainPrefix",
            value=self._cognito_construct.cognito_domain_prefix,
            export_name=f"{self.stack_name}-CognitoDomainPrefix",
        )

    @property
    def cognito_construct(self):
        """Return the Cognito construct."""
        return self._cognito_construct

    @property
    def user_pool(self) -> cognito.IUserPool:
        """Return the Cognito User Pool."""
        return self._cognito_construct.user_pool

    @property
    def user_pool_arn(self):
        """Return the Cognito User Pool ARN."""
        return self._cognito_construct.user_pool_arn

    @property
    def identity_pool(self):
        """Return the Cognito Identity Pool."""
        return self._cognito_construct.identity_pool

    @property
    def user_pool_client(self) -> cognito.UserPoolClient:
        """Return the Cognito User Pool Client."""
        return self._cognito_construct.user_pool_client

    @property
    def user_pool_client_id(self):
        """Return the Cognito User Pool Client ID."""
        return self._cognito_construct.user_pool_client_id

    @property
    def user_pool_id(self):
        """Return the Cognito User Pool ID."""
        return self._cognito_construct.user_pool_id

    @property
    def cognito_domain_prefix(self):
        """Return the Cognito Domain Prefix."""
        return self._cognito_construct.cognito_domain_prefix

    @property
    def pre_token_generation_lambda(self):
        """Return the Pre-Token Generation Lambda."""
        return self._cognito_construct._pre_token_generation_lambda
