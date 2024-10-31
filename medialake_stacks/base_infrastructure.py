from aws_cdk import (
    Stack,
    Environment,
    aws_events as events,
    aws_dynamodb as dynamodb,
    aws_lambda as lambda_,
    RemovalPolicy,
    CfnOutput
)
import aws_cdk.aws_lambda_event_sources as eventsources
from constructs import Construct
from medialake_constructs.shared_constructs.s3bucket import S3Bucket, S3Config
from config import config
from medialake_constructs.shared_constructs.eventbridge import EventBus, EventBusConfig
from medialake_constructs.shared_constructs.opensearch_serverless import OpenSearchServerlessConstruct, OpenSearchServerlessProps
from medialake_constructs.shared_constructs.dynamodb import DynamoDB, DynamoDBProps
from medialake_constructs.shared_constructs.lambda_base import (
    Lambda,
    LambdaConfig,
)

class BaseInfrastructureStack(Stack):
    def __init__(self, scope: Construct, id: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        env = kwargs.get('env')
        region = env.region if isinstance(env, Environment) else config.primary_region

        # Create media assets bucket with explicit name including region
        media_assets_bucket_config = S3Config(
            bucket_name=f"medialake-media-assets-{region}"
        )
        self.media_assets_bucket = S3Bucket(
            self,
            "MediaAssets",
            s3_config=media_assets_bucket_config
        )
        
        # Create EventBus with retention policy
        ingest_event_bus_config = EventBusConfig(
            bus_name=f"medialake-ingest-{region}",
            description="event bus",
            log_all=True,
        )
        self._ingest_event_bus = EventBus(
            self,
            "IngestEventBus",
            props=ingest_event_bus_config
        )


        self.opensearch_serverless = OpenSearchServerlessConstruct(
            self,
            "MediaLakeOSEmbeddings",
            props=OpenSearchServerlessProps(
                collection_name="medialake",
                public_access=True,
                collection_type="VECTORSEARCH",
                collection_desc="Collection to be used for vector search using OpenSearch Serverless",
                collection_indexes=["media"]
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
                name="connectors_get_lambda",
                entry="lambdas/back_end/asset_table_stream",
                environment_variables={
                },
            ),
        )
        
        asset_lambda_stream.function.add_event_source(eventsources.DynamoEventSource(self._asset_table.table,
            starting_position=lambda_.StartingPosition.LATEST,
            filters=[lambda_.FilterCriteria.filter({"event_name": lambda_.FilterRule.is_equal("INSERT")})]
        ))
        # # Export the EventBus name and ARN
        # CfnOutput(
        #     self,
        #     "IngestEventBusName",
        #     value=self._ingest_event_bus.event_bus_name,
        #     export_name=f"{id}-ingest-event-bus-name"
        # )
        # CfnOutput(
        #     self,
        #     "IngestEventBusArn",
        #     value=self._ingest_event_bus.event_bus.event_bus_arn,
        #     export_name=f"{id}-ingest-event-bus-arn"
        # )
    
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
