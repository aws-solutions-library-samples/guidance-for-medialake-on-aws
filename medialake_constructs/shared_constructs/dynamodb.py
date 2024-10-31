import aws_cdk as cdk
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_kms as kms
from constructs import Construct

from dataclasses import dataclass
from typing import Dict, Optional, List


@dataclass
class DynamoDBProps:
    """Configuration for DynamoDB creation."""
    name: str
    partition_key_name: str
    partition_key_type: str
    stream: Optional[dynamodb.StreamViewType] = None
    
    

class DynamoDB(Construct):
    def __init__(self, scope: Construct, id: str, props: DynamoDBProps, **kwargs):
        super().__init__(scope, id, **kwargs)

        # Create a custom KMS key for encryption
        self._kms_key = kms.Key(
            self, "DynamoDBKMSKey", removal_policy=cdk.RemovalPolicy.DESTROY
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
            # point_in_time_recovery=config.get("point_in_time_recovery", False),
            removal_policy=cdk.RemovalPolicy.DESTROY,
        )

    @property
    def table(self) -> dynamodb.TableV2:
        return self._table

    @property
    def table_name(self) -> str:
        return self._table.table_name

    @property
    def table_arn(self) -> str:
        return self._table.table_arn

    # @property
    # def kms_key(self) -> kms.Key:
    #     return self._kms_key
