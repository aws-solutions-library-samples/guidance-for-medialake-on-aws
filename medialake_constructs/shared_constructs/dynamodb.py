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
    global_secondary_indexes: Optional[list[dynamodb.GlobalSecondaryIndexPropsV2]] = (
        None
    )


class DynamoDB(Construct):
    def __init__(self, scope: Construct, id: str, props: DynamoDBProps, **kwargs):
        super().__init__(scope, id, **kwargs)

        stack = Stack.of(self)

        self.region = stack.region
        self.account_id = stack.account

        # Create a custom KMS key for encryption
        self._kms_key = kms.Key(
            self,
            "DynamoDBKMSKey",
            removal_policy=RemovalPolicy.DESTROY,
            enable_key_rotation=True,
            description="KMS key for DynamoDB table encryption",
        )

        # Create the DynamoDB table with the provided configuration
        table_props = {
            "table_name": props.name,
            "partition_key": dynamodb.Attribute(
                name=props.partition_key_name, type=props.partition_key_type
            ),
            "point_in_time_recovery": props.point_in_time_recovery,
            "removal_policy": RemovalPolicy.DESTROY,
            "dynamo_stream": props.stream,
            "encryption": dynamodb.TableEncryptionV2.dynamo_owned_key(),
        }

        # Add sort key if provided
        if props.sort_key_name and props.sort_key_type:
            table_props["sort_key"] = dynamodb.Attribute(
                name=props.sort_key_name, type=props.sort_key_type
            )

        # Add global secondary indexes if provided
        if props.global_secondary_indexes:
            table_props["global_secondary_indexes"] = props.global_secondary_indexes

        self._table = dynamodb.TableV2(self, "DynamoDBTable", **table_props)

    @property
    def table(self) -> dynamodb.TableV2:
        return self._table

    @property
    def table_name(self) -> str:
        return self._table.table_name

    @property
    def table_arn(self) -> str:
        return self._table.table_arn
