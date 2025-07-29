from dataclasses import dataclass

from aws_cdk import Stack
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_s3 as s3
from constructs import Construct

from config import config
from medialake_constructs.shared_constructs.dynamodb import DynamoDB, DynamoDBProps


@dataclass
class SharedAssetsStackProps:
    asset_table: dynamodb.TableV2
    media_assets_bucket: s3.IBucket


class SharedAssetsStack(Stack):

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        props: SharedAssetsStackProps,
        **kwargs,
    ):
        super().__init__(scope, construct_id, **kwargs)

        kwargs.get("env")
        Stack.of(self).account
        Stack.of(self).region

        # Create Assets Table
        assets_table_props = DynamoDBProps(
            name=f"{config.resource_prefix}-assets-table-{config.environment}",
            partition_key_name="PK",
            partition_key_type=dynamodb.AttributeType.STRING,
            sort_key_name="SK",
            sort_key_type=dynamodb.AttributeType.STRING,
            point_in_time_recovery=True,
            global_secondary_indexes=[
                dynamodb.GlobalSecondaryIndexPropsV2(
                    index_name="GSI-Time",
                    partition_key=dynamodb.Attribute(
                        name="GSI-Time-PK", type=dynamodb.AttributeType.STRING
                    ),
                    sort_key=dynamodb.Attribute(
                        name="GSI-Time-SK", type=dynamodb.AttributeType.STRING
                    ),
                )
            ],
        )

        self.assets_table = DynamoDB(
            self, "AssetsTable", props=assets_table_props
        ).table

        # Create Derivatives Table
        derivatives_table_props = DynamoDBProps(
            name=f"{config.resource_prefix}-derivatives-table-{config.environment}",
            partition_key_name="PK",
            partition_key_type=dynamodb.AttributeType.STRING,
            sort_key_name="SK",
            sort_key_type=dynamodb.AttributeType.STRING,
            point_in_time_recovery=True,
            global_secondary_indexes=[
                dynamodb.GlobalSecondaryIndexPropsV2(
                    index_name="GSI-Time",
                    partition_key=dynamodb.Attribute(
                        name="GSI-Time-PK", type=dynamodb.AttributeType.STRING
                    ),
                    sort_key=dynamodb.Attribute(
                        name="GSI-Time-SK", type=dynamodb.AttributeType.STRING
                    ),
                )
            ],
        )

        self.derivatives_table = DynamoDB(
            self, "DerivativesTable", props=derivatives_table_props
        ).table

        # Create Components Table
        components_table_props = DynamoDBProps(
            name=f"{config.resource_prefix}-components-table-{config.environment}",
            partition_key_name="PK",
            partition_key_type=dynamodb.AttributeType.STRING,
            sort_key_name="SK",
            sort_key_type=dynamodb.AttributeType.STRING,
            point_in_time_recovery=True,
            global_secondary_indexes=[
                dynamodb.GlobalSecondaryIndexPropsV2(
                    index_name="GSI-Path",
                    partition_key=dynamodb.Attribute(
                        name="GSI-Path-PK", type=dynamodb.AttributeType.STRING
                    ),
                    sort_key=dynamodb.Attribute(
                        name="GSI-Path-SK", type=dynamodb.AttributeType.STRING
                    ),
                )
            ],
        )

        self.components_table = DynamoDB(
            self, "ComponentsTable", props=components_table_props
        ).table
