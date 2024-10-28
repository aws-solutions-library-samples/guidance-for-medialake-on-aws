import aws_cdk as cdk
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_kms as kms
from constructs import Construct

from dataclasses import dataclass


@dataclass
class DynamoDBConfig:
    """Configuration for DynamoDB creation."""

    name: str
    partition_key_name: str
    partition_key_type: str


class DynamoDB(Construct):
    def __init__(self, scope: Construct, id: str, config: DynamoDBConfig, **kwargs):
        super().__init__(scope, id, **kwargs)

        # Create a custom KMS key for encryption
        self._kms_key = kms.Key(
            self, "DynamoDBKMSKey", removal_policy=cdk.RemovalPolicy.DESTROY
        )

        # Create the DynamoDB table with the provided configuration
        self._table = dynamodb.Table(
            self,
            "DynamoDBTable",
            table_name=config.name,
            partition_key=dynamodb.Attribute(
                name=config.partition_key_name, type=config.partition_key_type
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            encryption=dynamodb.TableEncryption.CUSTOMER_MANAGED,
            encryption_key=self._kms_key,
            # point_in_time_recovery=config.get("point_in_time_recovery", False),
            removal_policy=cdk.RemovalPolicy.DESTROY,
        )

    @property
    def table(self) -> dynamodb.Table:
        return self._table

    @property
    def table_name(self) -> str:
        return self._table.table_name

    @property
    def table_arn(self) -> str:
        return self._table.table_arn

    @property
    def kms_key(self) -> kms.Key:
        return self._kms_key
