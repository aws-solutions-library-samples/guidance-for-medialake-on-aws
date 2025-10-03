"""
Cognito Update Stack for Media Lake.

This stack handles additional Cognito User Pool configuration and triggers that need to be
applied after the core Cognito resources are created. This includes:
- Pre-signup Lambda trigger configuration
- Additional Lambda trigger setup
- User pool updates that might conflict if done during initial creation
"""

import datetime
from dataclasses import dataclass

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
        pre_token_env_vars = {
            **common_env_vars,
            "DEBUG_MODE": "true",
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
    def cognito_trigger_update(self):
        """Return the Cognito trigger update custom resource"""
        return self._cognito_trigger_update
