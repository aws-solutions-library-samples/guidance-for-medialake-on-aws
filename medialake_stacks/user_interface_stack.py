from aws_cdk import (
    Stack,
    Environment,
    aws_events as events,
    aws_dynamodb as dynamodb,
    aws_lambda as lambda_,
    aws_iam as iam,
    aws_events_targets as targets,
    aws_s3_notifications as s3n,
    aws_s3 as s3,
    aws_secretsmanager as secretsmanager,
)
from medialake_constructs.userInterface import UIConstruct, UIConstructProps
from dataclasses import dataclass


@dataclasses
class UserInterfaceStackProps:
    api_gateway_rest_id: str = None
    cognit_user_pool: str = None
    cognito_user_pool_client: str = None
    cognito_identity_pool: str = None


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
                props.api_gateway_rest_id,
                props.cognit_user_pool,
                props.cognito_user_pool_client,
                props.cognito_identity_pool,
            ),
        )
