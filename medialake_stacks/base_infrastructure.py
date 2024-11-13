from aws_cdk import (
    Stack,
    Environment,
    aws_events as events,
    aws_dynamodb as dynamodb,
    aws_lambda as lambda_,
    aws_iam as iam,
    aws_s3_notifications as s3n,
    aws_s3 as s3,
)
from aws_cdk import aws_lambda_event_sources as eventsources
from constructs import Construct

# Local imports
from config import GLOBAL_PREFIX, generate_short_uid, config
from medialake_constructs.shared_constructs.s3bucket import S3Bucket, S3Config
from medialake_constructs.shared_constructs.eventbridge import EventBus, EventBusConfig
from medialake_constructs.vpc import CustomVpc, CustomVpcProps
from medialake_constructs.shared_constructs.opensearch_managed_cluster import (
    OpenSearchCluster,
    OpenSearchClusterProps,
)
from medialake_constructs.shared_constructs.opensearch_serverless import (
    OpenSearchServerlessConstruct,
    OpenSearchServerlessProps,
)
from medialake_constructs.shared_constructs.lambda_layers import (
    SearchLayer,
    PynamoDbLambdaLayer,
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
        self.vpc = CustomVpc(
            self,
            "MediaLakeVPC",
            props=CustomVpcProps(vpc_name=f"{GLOBAL_PREFIX}-vpc-{region}"),
        )

        self.opensearch_cluster = OpenSearchCluster(
            self,
            "MediaLakeOpenSearch",
            props=OpenSearchClusterProps(
                domain_name=f"{GLOBAL_PREFIX}-opensearch",
                vpc=self.vpc.vpc,
            ),
        )

        self.media_assets_bucket = S3Bucket(
            self,
            "MediaAssets",
            s3_config=S3Config(
                bucket_name=f"{GLOBAL_PREFIX}-asset-bucket-{config.account_id}-{region}-{short_uid}",
                cors=[
                    s3.CorsRule(
                        allowed_methods=[
                            s3.HttpMethods.GET,
                            s3.HttpMethods.PUT,
                            s3.HttpMethods.POST,
                            s3.HttpMethods.DELETE,
                            s3.HttpMethods.HEAD,
                        ],
                        allowed_origins=[
                            "http://localhost:5173",
                            "https://*.cloudfront.net",
                        ],
                        allowed_headers=["*"],
                        exposed_headers=["ETag"],
                        max_age=3000,
                    )
                ],
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
                bucket_name=f"medialake-iac-assets-{config.account_id}-{short_uid}",
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

        # Create Pipeline Executions EventBus
        self._pipeline_event_bus = EventBus(
            self,
            "PipelineEventBus",
            props=EventBusConfig(
                bus_name=f"medialake-pipeline-executions-{region}",
                log_all=True,
            ),
        )

        # Configure S3 bucket to send notifications to EventBridge
        # self.media_assets_bucket.bucket.enable_event_bridge_notification()

        # Create EventBridge rule to route S3 events to pipeline event bus
        # events.Rule(
        #     self,
        #     "S3ToPipelineEventBusRule",
        #     event_pattern=events.EventPattern(
        #         source=["aws.s3"],
        #         detail_type=["AWS API Call via CloudTrail"],
        #         detail={
        #             "eventSource": ["s3.amazonaws.com"],
        #             "eventName": [
        #                 "StartExecution",
        #                 "StopExecution",
        #                 "ExecutionSucceeded",
        #                 "ExecutionFailed",
        #                 "ExecutionTimedOut",
        #                 "ExecutionAborted",
        #             ],
        #         },
        #     ),
        #     targets=[self._pipeline_event_bus.event_bus],
        # )

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
                partition_key_name="InventoryID",
                partition_key_type=dynamodb.AttributeType.STRING,
                sort_key_name="ID",
                sort_key_type=dynamodb.AttributeType.STRING,
                stream=dynamodb.StreamViewType.NEW_IMAGE,
                point_in_time_recovery=True,
            ),
        )
        self._asset_table.table.add_global_secondary_index(
            index_name="AssetIDIndex",
            partition_key=dynamodb.Attribute(
                name="ID", type=dynamodb.AttributeType.STRING
            ),
            projection_type=dynamodb.ProjectionType.ALL,
        )

        self._asset_table.table.add_global_secondary_index(
            index_name="FileHashIndex",
            partition_key=dynamodb.Attribute(
                name="FileHash", type=dynamodb.AttributeType.STRING
            ),
            projection_type=dynamodb.ProjectionType.ALL,
        )

        opensearch_layer = SearchLayer(self, "OpenSearchLayer")
        pynamodb_layer = PynamoDbLambdaLayer(self, "PynamoDbLayer")

        asset_lambda_stream = Lambda(
            self,
            "AssetTableLambdaStream",
            config=LambdaConfig(
                name=f"{GLOBAL_PREFIX}-asset-table-stream",
                entry="lambdas/back_end/asset_table_stream",
                environment_variables={
                    "OPENSEARCH_ENDPOINT": self.opensearch_serverless.collection_endpoint,
                    "OPENSEARCH_INDEX": "media",
                },
                layers=[opensearch_layer.layer, pynamodb_layer.layer],
            ),
        )

        # Add OpenSearch policy to Lambda function
        asset_lambda_stream.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=["aoss:APIAccessAll"],
                resources=[self.opensearch_serverless.collection_arn],
            )
        )

        self._asset_table.table.grant_stream(asset_lambda_stream.function)
        asset_lambda_stream.function.add_event_source(
            eventsources.DynamoEventSource(
                self._asset_table.table,
                starting_position=lambda_.StartingPosition.LATEST,
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

    @property
    def pipeline_event_bus(self) -> events.EventBus:
        return self._pipeline_event_bus.event_bus

    @property
    def pipeline_event_bus_name(self) -> str:
        return self._pipeline_event_bus.event_bus_name
