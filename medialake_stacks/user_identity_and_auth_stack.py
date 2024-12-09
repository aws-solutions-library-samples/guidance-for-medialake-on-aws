from aws_cdk import Stack, RemovalPolicy, Construct
from medialake_constructs.cognito import CognitoConstruct, CognitoProps
from dataclasses import dataclass


@dataclass
class UserIdentityAndAuthStackProps:
    self_sign_up_enabled: bool = False
    auto_verify_email: bool = True
    auto_verify_phone: bool = True
    sign_in_with_email: bool = True
    generate_secret: bool = False
    admin_user_password: bool = True
    user_password: bool = True
    user_srp: bool = True
    removal_policy: RemovalPolicy = RemovalPolicy.DESTROY


class UserIdentityAndAuthStack(Stack):

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        props: UserIdentityAndAuthStackProps,
        **kwargs,
    ):
        super().__init__(scope, construct_id, **kwargs)

        # User auth with Cognito
        self._cognito = CognitoConstruct(
            self,
            "Cognito",
            props=CognitoProps(),
        )

    @property
    def user_pool(self) -> str:
        return self._table.table_arn
