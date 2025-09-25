"""
Auth Lambda Construct for Media Lake.

This construct creates the Custom API Gateway Lambda Authorizer that can be used by multiple stacks.
"""

from dataclasses import dataclass

from constructs import Construct


@dataclass
class AuthLambdaConstructProps:
    """Configuration for Auth Lambda Construct."""

    auth_table_name: str
    avp_policy_store_id: str
    avp_policy_store_arn: str


class AuthLambdaConstruct(Construct):
    """
    Construct for Auth Lambda resources.

    This construct creates the Custom API Gateway Lambda Authorizer that can be used by multiple stacks.
    """

    def __init__(
        self, scope: Construct, id: str, props: AuthLambdaConstructProps, **kwargs
    ):
        super().__init__(scope, id, **kwargs)

        # Common environment variables for Lambda functions
        # common_env_vars = {
        #     "AUTH_TABLE_NAME": props.auth_table_name,
        #     "AVP_POLICY_STORE_ID": props.avp_policy_store_id,
        # }

        # Create the Custom API Gateway Lambda Authorizer
        # self._custom_authorizer_lambda = Lambda(
        #     self,
        #     "CustomAuthorizerLambda",
        #     function_name="CustomAuthorizerLambda",
        #     handler="index.handler",
        #     runtime=lambda_.Runtime.PYTHON_3_12,
        # )

        # Grant IsAuthorized permission for AVP
        # self._custom_authorizer_lambda.function.add_to_role_policy(
        #     iam.PolicyStatement(
        #         actions=["verifiedpermissions:IsAuthorized"],
        #         resources=[props.avp_policy_store_arn],
        #     )
        # )

    # @property
    # def custom_authorizer_lambda(self):
    #     """Return the custom authorizer Lambda function"""
    #     return self._custom_authorizer_lambda.function
