"""
Auth Lambda Stack for Media Lake.

This stack creates the Custom API Gateway Lambda Authorizer that can be used by multiple stacks.
"""

from dataclasses import dataclass

import aws_cdk as cdk
from constructs import Construct


@dataclass
class AuthLambdaStackProps:
    """Configuration for Auth Lambda Stack."""

    auth_table_name: str
    avp_policy_store_id: str
    avp_policy_store_arn: str


class AuthLambdaStack(cdk.NestedStack):
    """
    Stack for Auth Lambda resources.

    This stack creates the Custom API Gateway Lambda Authorizer that can be used by multiple stacks.
    """

    def __init__(
        self, scope: Construct, id: str, props: AuthLambdaStackProps, **kwargs
    ):
        super().__init__(scope, id, **kwargs)

        # Common environment variables for Lambda functions
        # common_env_vars = {
        #     "AUTH_TABLE_NAME": props.auth_table_name,
        #     "AVP_POLICY_STORE_ID": props.avp_policy_store_id,
        # }

        # # Create the Custom API Gateway Lambda Authorizer
        # self._custom_authorizer_lambda = Lambda(
        #     self,
        #     "CustomAuthorizerLambda",
        #     config=LambdaConfig(
        #         name="custom_api_authorizer",
        #         entry="lambdas/auth/custom_authorizer",
        #         memory_size=256,
        #         timeout_minutes=1,
        #         environment_variables=common_env_vars,
        #     ),
        # )

        # Grant IsAuthorized permission for AVP
        # self._custom_authorizer_lambda.function.add_to_role_policy(
        #     iam.PolicyStatement(
        #         actions=["verifiedpermissions:IsAuthorized"],
        #         resources=[props.avp_policy_store_arn],
        #     )
        # )

        # Export the Lambda function ARN
        # cdk.CfnOutput(
        #     self,
        #     "CustomAuthorizerLambdaArn",
        #     value=self._custom_authorizer_lambda.function.function_arn,
        #     export_name=f"{self.stack_name}-CustomAuthorizerLambdaArn",
        # )

    # @property
    # def custom_authorizer_lambda(self):
    #     """Return the custom authorizer Lambda function"""
    #     return self._custom_authorizer_lambda.function
