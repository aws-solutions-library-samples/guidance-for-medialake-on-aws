# import json
from constructs import Construct
from aws_cdk import (
    Stack,
    Environment,
    aws_events as events,
    aws_dynamodb as dynamodb,
    aws_s3 as s3,
    aws_ec2 as ec2,
    # custom_resources as cr,
    Duration,
)
from config import config
from medialake_constructs.shared_constructs.s3_logging import (
    add_s3_access_logging_policy,
)

from medialake_constructs.shared_constructs.s3bucket import S3Bucket, S3BucketProps
from medialake_constructs.shared_constructs.eventbridge import EventBus, EventBusConfig
from medialake_constructs.vpc import CustomVpc, CustomVpcProps
from medialake_constructs.shared_constructs.opensearch_managed_cluster import (
    OpenSearchCluster,
    OpenSearchClusterProps,
)
from medialake_constructs.shared_constructs.opensearch_ingestion_pipeline import (
    OpenSearchIngestionPipeline,
    OpenSearchIngestionPipelineProps,
)
from medialake_constructs.shared_constructs.dynamodb import DynamoDB, DynamoDBProps

from cdk_nag import AwsSolutionsChecks, NagSuppressions

"""
Base infrastructure stack that sets up core AWS resources for the MediaLake application.

This stack creates and configures:
- VPC and networking components
- OpenSearch cluster
- S3 buckets for media assets, IAC assets, and DynamoDB exports  
- EventBridge event bus
- DynamoDB tables for asset management
- Ingestion pipeline for syncing DynamoDB to OpenSearch
"""


class BaseInfrastructureStack(Stack):
    """
    Core infrastructure stack containing foundational AWS resources.

    Creates and configures the base infrastructure components needed by the MediaLake
    application including networking, storage, search, and data persistence layers.

    Args:
        scope (Construct): CDK construct scope
        construct_id (str): Unique identifier for the stack
        **kwargs: Additional arguments passed to Stack
    """

    def __init__(self, scope: Construct, construct_id: str, **kwargs):
        super().__init__(scope, construct_id, **kwargs)

        env = kwargs.get("env")
        region = env.region if isinstance(env, Environment) else config.primary_region
        account = env.account if isinstance(env, Environment) else config.account_id
        opensearch_index_name = "media"

        self.access_logs_bucket = S3Bucket(
            self,
            "AccessLogsBucket",
            props=S3BucketProps(
                bucket_name=f"{config.global_prefix}-access-logs-{config.account_id}-{self.region}-{config.environment}".lower(),
                intelligent_tiering_configurations=[
                    s3.IntelligentTieringConfiguration(
                        name="All",
                        archive_access_tier_time=Duration.days(90),
                        deep_archive_access_tier_time=Duration.days(180),
                    )
                ],
                lifecycle_rules=[
                    s3.LifecycleRule(
                        enabled=True,
                        abort_incomplete_multipart_upload_after=Duration.days(7),
                    ),
                    s3.LifecycleRule(
                        enabled=True,
                        transitions=[
                            s3.Transition(
                                storage_class=s3.StorageClass.INTELLIGENT_TIERING,
                                transition_after=Duration.minutes(0),
                            )
                        ],
                    ),
                ],
            ),
        )

        # self.dynamodb_cloudtrail_logs = DynamoDBCloudTrailLogs(
        #     self,
        #     "DynamoDBCloudTrailLogs",
        #     props=DynamoDBCloudTrailLogsProps(
        #         access_logs_bucket=self.access_logs_bucket.bucket,
        #     ),
        # )

        self.ddb_export_bucket = S3Bucket(
            self,
            "DynamodbExportBucket",
            props=S3BucketProps(
                bucket_name=f"{config.global_prefix}-ddb-export-{config.account_id}-{self.region}-{config.environment}".lower(),
                access_logs=True,
                access_logs_bucket=self.access_logs_bucket.bucket,
            ),
        )

        # VPC used for OpenSearch, Lambda's, and VPC Endpoints
        self._vpc = CustomVpc(
            self,
            "MediaLakeVPC",
            props=CustomVpcProps(
                vpc_name=f"{config.global_prefix}-vpc-{self.region}-{config.environment}"
            ),
        )

        # self._vpc = CustomVpc(
        #     self,
        #     "MediaLakeVPC",
        #     props=CustomVpcProps(
        #         vpc_name=f"{config.global_prefix}-vpc-{self.region}-{config.environment}",
        #         max_azs=config.vpc.max_azs,
        #         nat_gateways=config.vpc.nat_gateways,
        #         cidr=config.vpc.cidr,
        #         enable_dns_hostnames=config.vpc.enable_dns_hostnames,
        #         enable_dns_support=config.vpc.enable_dns_support,
        #         # vpc_id=config.vpc.vpc_id,
        #     ),
        # )

        # Security group for Lambdas
        self._security_group = ec2.SecurityGroup(
            self,
            "MediaLakeSecurityGroup",
            description="MediaLake Security Group",
            vpc=self._vpc.vpc,
        )

        # Allow HTTPS ingress from the VPC CIDR
        self._security_group.add_ingress_rule(
            peer=ec2.Peer.ipv4(self._vpc.vpc.vpc_cidr_block),
            connection=ec2.Port.tcp(443),
            description="Allow HTTPS ingress from VPC CIDR",
        )

        # Allow HTTP ingress from the VPC CIDR
        self._security_group.add_ingress_rule(
            peer=ec2.Peer.ipv4(self._vpc.vpc.vpc_cidr_block),
            connection=ec2.Port.tcp(80),
            description="Allow HTTP ingress from VPC CIDR",
        )

        # Create OpenSearch managed cluster
        self._opensearch_cluster = OpenSearchCluster(
            self,
            "MediaLakeOpenSearch",
            props=OpenSearchClusterProps(
                domain_name=f"{config.global_prefix}-os-{self.region}-{config.environment}",
                vpc=self._vpc.vpc,
                collection_indexes=[opensearch_index_name],
                security_group=self._security_group,
            ),
        )

        # Create media asset bucket
        self.media_assets_s3_bucket = S3Bucket(
            self,
            "MediaAssets",
            props=S3BucketProps(
                bucket_name=f"{config.global_prefix}-asset-bucket-{config.account_id}-{self.region}-{config.environment}",
                access_logs=True,
                access_logs_bucket=self.access_logs_bucket.bucket,
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

        add_s3_access_logging_policy(
            self,
            access_logs_bucket=self.access_logs_bucket.bucket,
            source_bucket=self.media_assets_s3_bucket.bucket,
        )

        # Create IAC assets bucket with explicit name including region
        self.iac_assets_bucket = S3Bucket(
            self,
            "IACAssets",
            props=S3BucketProps(
                bucket_name=f"{config.global_prefix}-iac-assets-{config.account_id}-{self.region}-{config.environment}".lower(),
                access_logs=True,
                access_logs_bucket=self.access_logs_bucket.bucket,
            ),
        )

        self._ingest_event_bus = EventBus(
            self,
            "IngestEventBus",
            props=EventBusConfig(
                bus_name=f"{config.global_prefix}-ingest-{self.region}-{config.environment}",
                description="event bus",
                log_all=True,
            ),
        )

        self._pipelne_table = DynamoDB(
            self,
            "PipelinesTable",
            props=DynamoDBProps(
                name=f"medialake_pipeline_table",
                partition_key_name="id",
                partition_key_type=dynamodb.AttributeType.STRING,
            ),
        )

        self._asset_table = DynamoDB(
            self,
            "MediaLakeAssetTable",
            props=DynamoDBProps(
                name=f"{config.global_prefix}-asset-table-{config.environment}",
                partition_key_name="InventoryID",
                partition_key_type=dynamodb.AttributeType.STRING,
                sort_key_name="DigitalSourceAsset.ID",
                sort_key_type=dynamodb.AttributeType.STRING,
                pipeline_name=f"{config.global_prefix}-dynamodb-etl-pipeline",
                ddb_export_bucket=self.ddb_export_bucket,
                stream=dynamodb.StreamViewType.NEW_IMAGE,
                point_in_time_recovery=True,
            ),
        )

        self._asset_table.table.add_global_secondary_index(
            index_name="AssetIDIndex",
            partition_key=dynamodb.Attribute(
                name="DigitalSourceAsset.ID", type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="DigitalSourceAsset.IngestedAt",
                type=dynamodb.AttributeType.STRING,
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

        self._opensearch_ingestion_pipeline = OpenSearchIngestionPipeline(
            self,
            "MediaLakeOSIngestionPipeline",
            props=OpenSearchIngestionPipelineProps(
                asset_table=self._asset_table,
                access_logs_bucket=self.access_logs_bucket,
                opensearch_cluster=self._opensearch_cluster,
                ddb_export_bucket=self.ddb_export_bucket,
                index_name=opensearch_index_name,
                vpc=self._vpc,
                security_group=self._security_group,
            ),
        )

    @property
    def ingest_event_bus(self) -> events.EventBus:
        """
        Returns the EventBridge event bus used for ingestion events.

        Returns:
            events.EventBus: The configured EventBridge event bus
        """

        return self._ingest_event_bus.event_bus

    @property
    def ingest_event_bus_name(self) -> str:
        """
        Returns the name of the ingestion event bus.

        Returns:
            str: Name of the EventBridge event bus
        """

        return self._ingest_event_bus.event_bus_name

    @property
    def asset_table(self) -> dynamodb.TableV2:
        """
        Returns the DynamoDB table used for storing media asset metadata.

        Returns:
            dynamodb.TableV2: The configured DynamoDB table
        """

        return self._asset_table

    @property
    def pipeline_table(self) -> dynamodb.TableV2:
        """
        Returns the DynamoDB table used for storing pipelines.

        Returns:
            dynamodb.TableV2: The configured DynamoDB table
        """

        return self._pipelne_table.table

    @property
    def asset_table_name(self) -> str:
        """
        Returns the name of the asset DynamoDB table.

        Returns:
            str: Name of the DynamoDB table
        """

        return self._asset_table.table.table_name

    @property
    def asset_table_file_hash_index_name(self) -> str:
        """
        Returns the name of the FileHash GSI on the asset table.

        Returns:
            str: Name of the FileHash global secondary index
        """

        return "FileHashIndex"

    @property
    def asset_table_file_hash_index_arn(self) -> str:
        """
        Returns the ARN of the FileHash GSI on the asset table.

        Returns:
            str: ARN of the FileHash global secondary index
        """

        return f"{self._asset_table.table.table_arn}/index/FileHashIndex"

    @property
    def asset_table_asset_id_index_name(self) -> str:
        """
        Returns the name of the AssetID GSI on the asset table.

        Returns:
            str: Name of the AssetID global secondary index
        """

        return "AssetIDIndex"

    @property
    def asset_table_asset_id_index_arn(self) -> str:
        """
        Returns the ARN of the AssetID GSI on the asset table.

        Returns:
            str: ARN of the AssetID global secondary index
        """

        return f"{self._asset_table.table.table_arn}/index/AssetIDIndex"

    @property
    def collection_dashboards_url(self) -> str:
        """
        Returns the URL for the OpenSearch Dashboards interface.

        Returns:
            str: OpenSearch Dashboards URL
        """

        return self._opensearch_cluster.domain_endpoint + "/_dashboards"

    @property
    def collection_endpoint(self) -> str:
        """
        Returns the endpoint URL for the OpenSearch cluster.

        Returns:
            str: OpenSearch cluster endpoint
        """

        return self._opensearch_cluster.domain_endpoint

    @property
    def collection_arn(self) -> str:
        """
        Returns the ARN of the OpenSearch cluster.

        Returns:
            str: ARN of the OpenSearch domain
        """

        return self._opensearch_cluster.domain_arn

    @property
    def vpc(self) -> ec2.Vpc:
        """
        Returns the VPC of vpc.

        Returns:
            str: VPC
        """
        return self._vpc.vpc

    @property
    def security_group(self) -> ec2.SecurityGroup:
        """
        Returns the SecurityGroup.

        Returns:
            str: SecurityGroup
        """
        return self._security_group

    @property
    def media_assets_bucket(self) -> s3.IBucket:
        """
        Returns the URL for the OpenSearch Dashboards interface.

        Returns:
            s3.IBucket: S3 bucket object
        """

        return self.media_assets_s3_bucket

    @property
    def access_log_bucket(self) -> s3.IBucket:
        """
        Returns the access log bucket.

        Returns:
            s3.IBucket: S3 bucket object
        """
        return self.access_logs_bucket.bucket
