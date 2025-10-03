from dataclasses import dataclass
from typing import Optional

from aws_cdk import RemovalPolicy, Stack
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_iam as iam
from aws_cdk import aws_kms as kms
from aws_cdk import aws_s3 as s3
from constructs import Construct

from config import config


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
    removal_policy: Optional[RemovalPolicy] = RemovalPolicy.DESTROY
    global_secondary_indexes: Optional[list[dynamodb.GlobalSecondaryIndexPropsV2]] = (
        None
    )
    billing_mode: Optional[dynamodb.Billing] = None
    ttl_attribute: Optional[str] = None


class DynamoDB(Construct):
    def __init__(self, scope: Construct, id: str, props: DynamoDBProps, **kwargs):
        super().__init__(scope, id, **kwargs)

        stack = Stack.of(self)

        self.region = stack.region
        self.account_id = stack.account

        if config.db.use_existing_tables:
            # Import existing table
            self._table = dynamodb.Table.from_table_attributes(
                self,
                f"{id}Existing",
                table_name=props.name,
                table_stream_arn=(
                    f"arn:aws:dynamodb:{self.region}:{self.account_id}:table/{props.name}/stream/{props.stream}"
                    if props.stream
                    else None
                ),
            )
        else:
            # Create a custom KMS key for encryption
            self._kms_key = kms.Key(
                self,
                "DynamoDBKMSKey",
                removal_policy=props.removal_policy,
                enable_key_rotation=True,
                description="KMS key for DynamoDB table encryption",
            )

            # Create new table with all configurations
            table_props = {
                "table_name": props.name,
                "partition_key": dynamodb.Attribute(
                    name=props.partition_key_name, type=props.partition_key_type
                ),
                "point_in_time_recovery": props.point_in_time_recovery,
                "removal_policy": (
                    RemovalPolicy.RETAIN
                    if config.should_retain_tables
                    else RemovalPolicy.DESTROY
                ),
                "dynamo_stream": props.stream,
                "encryption": dynamodb.TableEncryptionV2.dynamo_owned_key(),
                "billing": props.billing_mode or dynamodb.Billing.on_demand(),
            }

            # Add TTL attribute if provided
            if props.ttl_attribute:
                table_props["time_to_live_attribute"] = props.ttl_attribute

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
    def table(self) -> dynamodb.ITable:
        return self._table

    @property
    def table_name(self) -> str:
        return self._table.table_name

    @property
    def table_arn(self) -> str:
        return self._table.table_arn
