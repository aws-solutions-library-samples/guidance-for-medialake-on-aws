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
from aws_cdk import aws_lambda_event_sources as eventsources
from constructs import Construct
from dataclasses import dataclass

# Local imports
from config import GLOBAL_PREFIX, generate_short_uid, config
from medialake_constructs.shared_constructs.eventbridge import EventBus, EventBusConfig
from medialake_constructs.shared_constructs.dynamodb import DynamoDB, DynamoDBProps

from medialake_constructs.shared_constructs.lambda_base import (
    Lambda,
    LambdaConfig,
)


@dataclass
class SettingsStackProps:
    # x_origin_verify_secret: secretsmanager.Secret
    test: str


class SettingsStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        props: SettingsStackProps,
        **kwargs,
    ):
        super().__init__(scope, construct_id, **kwargs)

        # self._user_settings_table = DynamoDB(
        #     self,
        #     "UserSettingsTable",
        #     props=DynamoDBProps(
        #         name="medialake_user_settings_table",
        #         partition_key_name="user_id",
        #         partition_key_type=dynamodb.AttributeType.STRING,
        #     ),
        # )
