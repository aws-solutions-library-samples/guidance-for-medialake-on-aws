"""
Shared Custom Authorizer Construct for Media Lake.

This construct creates a single custom authorizer that can be shared across multiple API Gateway stacks.
"""

from dataclasses import dataclass

import aws_cdk as cdk
from aws_cdk import CfnOutput, Duration
from aws_cdk import aws_events as events
from aws_cdk import aws_events_targets as targets
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from constructs import Construct

from constants import Lambda as LambdaConstants
from medialake_constructs.shared_constructs.lambda_base import Lambda, LambdaConfig


@dataclass
class SharedAuthorizerConstructProps:
    """Configuration for Shared Authorizer Construct."""

    auth_table_name: str
    avp_policy_store_id: str
    avp_policy_store_arn: str
    cognito_user_pool_id: str
    api_keys_table_name: str
    api_keys_table_arn: str


class SharedAuthorizerConstruct(Construct):
    """
    Construct for creating a shared custom authorizer.

    This construct creates a single custom authorizer Lambda that can be used
    across multiple API Gateway stacks and resources.
    """

    def __init__(
        self, scope: Construct, id: str, props: SharedAuthorizerConstructProps, **kwargs
    ):
        super().__init__(scope, id, **kwargs)

        # Environment variables for the authorizer lambda
        common_env_vars = {
            "AUTH_TABLE_NAME": props.auth_table_name,
            "AVP_POLICY_STORE_ID": props.avp_policy_store_id,
            "COGNITO_USER_POOL_ID": props.cognito_user_pool_id,
            "API_KEYS_TABLE_NAME": props.api_keys_table_name,
            "DEBUG_MODE": "true",  # Temporarily enabled for debugging user creation issue
            "NAMESPACE": "MediaLake",
            "TOKEN_TYPE": "identityToken",
        }

        # Create the shared custom authorizer Lambda
        self._authorizer_lambda = Lambda(
            self,
            "SharedCustomAuthorizerLambda",
            config=LambdaConfig(
                name="shared_custom_authorizer",
                entry="lambdas/auth/custom_authorizer",
                memory_size=256,
                timeout_minutes=1,
                snap_start=False,  # Disable SnapStart to avoid versioning
                environment_variables=common_env_vars,
            ),
        )

        # Grant necessary permissions to the authorizer lambda
        self._authorizer_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "verifiedpermissions:IsAuthorizedWithToken",
                    "verifiedpermissions:IsAuthorized",
                ],
                resources=[props.avp_policy_store_arn],
            )
        )

        # Grant permissions to access API keys table
        self._authorizer_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "dynamodb:GetItem",
                    "dynamodb:Query",
                ],
                resources=[props.api_keys_table_arn],
            )
        )

        # Grant permissions to access Secrets Manager for API key validation
        self._authorizer_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "secretsmanager:GetSecretValue",
                ],
                resources=[
                    f"arn:aws:secretsmanager:{cdk.Aws.REGION}:{cdk.Aws.ACCOUNT_ID}:secret:medialake/api-keys/*"
                ],
            )
        )

        # Grant KMS permissions if secrets are encrypted (using default AWS managed key)
        self._authorizer_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "kms:Decrypt",
                ],
                resources=["*"],  # For AWS managed keys
                conditions={
                    "StringEquals": {
                        "kms:ViaService": f"secretsmanager.{cdk.Aws.REGION}.amazonaws.com"
                    }
                },
            )
        )

        # Note: API Gateway authorizer is not created here since we're using utility functions
        # Each stack creates its own authorizer instance using create_shared_custom_authorizer()

        # Add resource-based policy to allow API Gateway to invoke this Lambda
        # This allows any API Gateway in the account to invoke this authorizer
        self._authorizer_lambda.function.add_permission(
            "ApiGatewayInvokePermission",
            principal=iam.ServicePrincipal("apigateway.amazonaws.com"),
            action="lambda:InvokeFunction",
            source_arn=f"arn:aws:execute-api:{cdk.Aws.REGION}:{cdk.Aws.ACCOUNT_ID}:*/*/*",
        )

        # Export the Lambda function ARN for cross-stack usage
        CfnOutput(
            self,
            "SharedAuthorizerLambdaArn",
            value=self._authorizer_lambda.function.function_arn,
            export_name="MediaLake-SharedAuthorizerLambdaArn",
        )

        # Export the Lambda function name for cross-stack usage
        CfnOutput(
            self,
            "SharedAuthorizerLambdaName",
            value=self._authorizer_lambda.function.function_name,
            export_name="MediaLake-SharedAuthorizerLambdaName",
        )

        # Lambda warming for shared custom authorizer
        events.Rule(
            self,
            "SharedAuthorizerWarmerRule",
            schedule=events.Schedule.rate(
                Duration.minutes(LambdaConstants.WARMER_INTERVAL_MINUTES)
            ),
            targets=[
                targets.LambdaFunction(
                    self._authorizer_lambda.function,
                    event=events.RuleTargetInput.from_object({"lambda_warmer": True}),
                ),
            ],
            description="Keeps shared custom authorizer Lambda warm via scheduled EventBridge rule.",
        )

    @property
    def authorizer_lambda(self) -> lambda_.Function:
        """Return the shared authorizer Lambda function"""
        return self._authorizer_lambda.function
