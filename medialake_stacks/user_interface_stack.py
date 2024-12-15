from dataclasses import dataclass

# from medialake_stacks.auth_stack import AuthStack
from constructs import Construct
from aws_cdk import (
    Stack,
    aws_s3 as s3,
)
from medialake_constructs.userInterface import UIConstruct, UIConstructProps


@dataclass
class UserInterfaceStackProps:
    api_gateway_rest_id: str
    cognito_user_pool: str
    cognito_user_pool_client_id: str
    cognito_identity_pool: str
    # medialake_ui_s3_bucket: s3.IBucket
    access_log_bucket: s3.IBucket


class UserInterfaceStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        props: UserInterfaceStackProps,
        **kwargs,
    ):
        super().__init__(scope, construct_id, **kwargs)

        self._ui = UIConstruct(
            self,
            "UserInterface",
            props=UIConstructProps(
                cognito_user_pool_id=props.cognito_user_pool,
                cognito_user_pool_client_id=props.cognito_user_pool_client_id,
                cognito_identity_pool=props.cognito_identity_pool,
                api_gateway_rest_id=props.api_gateway_rest_id,
                access_log_bucket=props.access_log_bucket,
                # medialake_ui_s3_bucket=props.medialake_ui_s3_bucket,
            ),
        )
