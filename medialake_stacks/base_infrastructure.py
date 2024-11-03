from aws_cdk import (
    Stack,
    Environment,
    aws_events as events,
    aws_dynamodb as dynamodb,
    aws_lambda as lambda_,
)
from aws_cdk import aws_lambda_event_sources as eventsources
from constructs import Construct

# Local imports
from config import GLOBAL_PREFIX, generate_short_uid, config
from medialake_constructs.shared_constructs.s3bucket import S3Bucket, S3Config
from medialake_constructs.shared_constructs.eventbridge import EventBus, EventBusConfig
from medialake_constructs.shared_constructs.opensearch_serverless import (
    OpenSearchServerlessConstruct,
    OpenSearchServerlessProps,
)
from medialake_constructs.shared_constructs.dynamodb import DynamoDB, DynamoDBProps
from medialake_constructs.shared_constructs.lambda_base import (
    Lambda,
    LambdaConfig,
)


class BaseInfrastructureStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs):
        super().__init__(scope, construct_id, **kwargs)

        env = kwargs.get("env")
        region = env.region if isinstance(env, Environment) else config.primary_region

        # Generate a short unique identifier
        short_uid = generate_short_uid(self, length=8)

        # Calculate the maximum length for the fixed name prefix
        max_prefix_length = 4 - len(short_uid) - 1  # Subtract 1 for the separator

        # Truncate the fixed name prefix if it exceeds the maximum length
        truncated_prefix = GLOBAL_PREFIX[:max_prefix_length]

        # Combine the truncated prefix, separator, and unique identifier
        lambda_function_name = f"{truncated_prefix}_{short_uid}"
        # Use the generated name for your Lambda function
        self.media_assets_bucket = S3Bucket(
            self,
            "MediaAssets",
            s3_config=S3Config(
                bucket_name=f"{GLOBAL_PREFIX}-asset-bucket-343424234234-{region}-{short_uid}"
            ),
        )

        # Create IAC assets bucket with explicit name including region
        medialake_iac_assets_config = S3Config(
            bucket_name=f"medialake-iac-assets-{config.account_id}-{Stack.of(self).region}-{id}".lower()
        )
        self.iac_assets_bucket = S3Bucket(
            self,
            "IACAssets",
            s3_config=S3Config(
                bucket_name=f"medialake-iac-assets-343424234234-{short_uid}"
            ),
        )

        # Create EventBus with retention policy
        ingest_event_bus_config = EventBusConfig(
            bus_name=f"medialake-ingest-{region}",
            description="event bus",
            log_all=True,
        )
        self._ingest_event_bus = EventBus(
            self, "IngestEventBus", props=ingest_event_bus_config
        )

        self.opensearch_serverless = OpenSearchServerlessConstruct(
            self,
            "OpenSearch",
            props=OpenSearchServerlessProps(
                collection_name="medialake",
                public_access=True,
                collection_type="VECTORSEARCH",
                collection_desc="Collection to be used for vector search using OpenSearch Serverless",
                collection_indexes=["media"],
            ),
        )

        self._asset_table = DynamoDB(
            self,
            "MediaLakeAssetTable",
            props=DynamoDBProps(
                name="medialake-asset-table",
                partition_key_name="id",
                partition_key_type=dynamodb.AttributeType.STRING,
                stream=dynamodb.StreamViewType.NEW_IMAGE,
                # # sort_key="createdAt",
                # removal_policy=RemovalPolicy.DESTROY,
            ),
        )

        asset_lambda_stream = Lambda(
            self,
            "AssetTableLambdaStream",
            config=LambdaConfig(
                name=f"{GLOBAL_PREFIX}-asset-table-stream",
                entry="lambdas/back_end/asset_table_stream",
                environment_variables={},
            ),
        )

        self._asset_table.table.grant_stream(asset_lambda_stream.function)
        asset_lambda_stream.function.add_event_source(
            eventsources.DynamoEventSource(
                self._asset_table.table,
                starting_position=lambda_.StartingPosition.LATEST,
                filters=[
                    lambda_.FilterCriteria.filter(
                        {"event_name": lambda_.FilterRule.is_equal("INSERT")}
                    )
                ],
            )
        )

    @property
    def ingest_event_bus(self) -> events.EventBus:
        return self._ingest_event_bus.event_bus

    @property
    def ingest_event_bus_name(self) -> str:
        return self._ingest_event_bus.event_bus_name

    @property
    def asset_table(self) -> dynamodb.TableV2:
        return self._asset_table

    @property
    def asset_table_name(self) -> str:
        return self._asset_table.table.table_name

    @property
    def collection_dashboards_url(self) -> str:
        return self.opensearch_serverless.collection_dashboards_url

    @property
    def collection_endpoint(self) -> str:
        return self.opensearch_serverless.collection_endpoint

    @property
    def collection_arn(self) -> str:
        return self.opensearch_serverless.collection_arn
