"""
Shared Custom Authorizer Construct for Media Lake.

This construct creates a single custom authorizer that can be shared across multiple API Gateway stacks.
"""

from dataclasses import dataclass

import aws_cdk as cdk
from aws_cdk import CfnOutput
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from constructs import Construct

from medialake_constructs.shared_constructs.lambda_base import Lambda, LambdaConfig


@dataclass
class SharedAuthorizerConstructProps:
    """Configuration for Shared Authorizer Construct."""

    auth_table_name: str
    avp_policy_store_id: str
    avp_policy_store_arn: str
    cognito_user_pool_id: str


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

    @property
    def authorizer_lambda(self) -> lambda_.Function:
        """Return the shared authorizer Lambda function"""
        return self._authorizer_lambda.function
