from aws_cdk import (
    Stack,
    aws_iam as iam,
    aws_kms as kms,
    aws_s3 as s3,
    aws_dynamodb as dynamodb,
    custom_resources as cr,
    RemovalPolicy,
)

from constructs import Construct

from dataclasses import dataclass
from typing import Optional


@dataclass
class DynamoDBProps:
    """Configuration for DynamoDB creation."""

    name: str
    partition_key_name: str
    partition_key_type: str
    pipeline_name: Optional[str] = None
    pipeline_role: Optional[iam.Role] = None
    ddb_export_bucket: Optional[s3.Bucket] = None
    sort_key_name: Optional[str] = None
    sort_key_type: Optional[dynamodb.AttributeType] = None
    stream: Optional[dynamodb.StreamViewType] = None
    point_in_time_recovery: Optional[bool] = True


class DynamoDB(Construct):
    def __init__(self, scope: Construct, id: str, props: DynamoDBProps, **kwargs):
        super().__init__(scope, id, **kwargs)

        stack = Stack.of(self)

        self.region = stack.region
        self.account_id = stack.account

        # Create a custom KMS key for encryption
        self._kms_key = kms.Key(
            self, "DynamoDBKMSKey", removal_policy=RemovalPolicy.DESTROY
        )

        # Create the DynamoDB table with the provided configuration
        self._table = dynamodb.TableV2(
            self,
            "DynamoDBTable",
            table_name=props.name,
            partition_key=dynamodb.Attribute(
                name=props.partition_key_name, type=props.partition_key_type
            ),
            # encryption_key=self._kms_key,
            point_in_time_recovery=props.point_in_time_recovery,
            removal_policy=RemovalPolicy.DESTROY,
            dynamo_stream=props.stream,
        )

    # dynamo_db_pipeline_custom_resource_provider = cr.Provider(
    #         self,
    #         "DynamoDBPipelineCustomResourceProvider",
    #         on_event_handler=on_event,
    #         log_retention=logs.RetentionDays.ONE_DAY,
    #     )

    # custom_resource = cr.CustomResource(
    #         self,
    #         "DynamoDBPipelineCustomResource",
    #         service_token=dynamo_db_pipeline_custom_resource_provider.service_token,
    #     )

    @property
    def table(self) -> dynamodb.TableV2:
        return self._table

    @property
    def table_name(self) -> str:
        return self._table.table_name

    @property
    def table_arn(self) -> str:
        return self._table.table_arn
