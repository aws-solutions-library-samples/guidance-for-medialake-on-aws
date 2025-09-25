# import json
import aws_cdk as cdk
from aws_cdk import CfnOutput, Duration, RemovalPolicy, Stack
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_events as events
from aws_cdk import aws_events_targets as targets
from aws_cdk import aws_s3 as s3
from constructs import Construct

from config import config
from constants import Lambda as LambdaConstants
from medialake_constructs.shared_constructs.dynamodb import DynamoDB, DynamoDBProps
from medialake_constructs.shared_constructs.eventbridge import EventBus, EventBusConfig
from medialake_constructs.shared_constructs.opensearch_ingestion_pipeline import (
    OpenSearchIngestionPipeline,
    OpenSearchIngestionPipelineProps,
)
from medialake_constructs.shared_constructs.opensearch_managed_cluster import (
    OpenSearchCluster,
    OpenSearchClusterProps,
)
from medialake_constructs.shared_constructs.s3_logging import (
    add_s3_access_logging_policy,
)
from medialake_constructs.shared_constructs.s3_vectors import (
    S3VectorCluster,
    S3VectorClusterProps,
)
from medialake_constructs.shared_constructs.s3bucket import S3Bucket, S3BucketProps
from medialake_constructs.vpc import CustomVpc, CustomVpcProps

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
        lambda_warmer (
                           bool): If True,
                           create a warming EventBridge rule (default: False
                       )
        lambda_functions_to_warm (Optional[List[aws_lambda.Function]]): List of Lambda functions to keep warm
        **kwargs: Additional arguments passed to Stack
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        lambda_warmer: bool = False,
        lambda_functions_to_warm=None,
        **kwargs,
    ):
        super().__init__(scope, construct_id, **kwargs)

        # env = kwargs.get("env")
        Stack.of(self).account
        region = Stack.of(self).region
        opensearch_index_name = "media"
        s3_vector_index_name = "media-vectors"
        parent_stack = cdk.Stack.of(self)
        parent_stack.region

        if config.s3.use_existing_buckets:
            # Import existing buckets
            self._access_logs_bucket = S3Bucket(
                self,
                "AccessLogsBucket",
                props=S3BucketProps(
                    bucket_name=config.s3.access_logs_bucket.bucket_name,
                    destroy_on_delete=config.environment != "prod",
                    existing_bucket_arn=config.s3.access_logs_bucket.bucket_arn,
                ),
            )

        else:
            self._access_logs_bucket = S3Bucket(
                self,
                "AccessLogsBucket",
                props=S3BucketProps(
                    # bucket_name=f"{config.resource_prefix}-access-logs-{config.account_id}-{region}-{config.environment}".lower(),
                    destroy_on_delete=config.environment != "prod",
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

        ## CloudTrail Logs for DynamDB, commented out due to feature request
        # self.dynamodb_cloudtrail_logs = DynamoDBCloudTrailLogs(
        #     self,
        #     "DynamoDBCloudTrailLogs",
        #     props=DynamoDBCloudTrailLogsProps(
        #         access_logs_bucket=self.access_logs_bucket.bucket,
        #     ),
        # )

        self.external_payload_bucket = S3Bucket(
            self,
            "ExternalPaylodBucket",
            props=S3BucketProps(
                destroy_on_delete=True,
                access_logs=True,
                access_logs_bucket=self.access_logs_bucket,
            ),
        )

        self.ddb_export_bucket = S3Bucket(
            self,
            "DynamodbExportBucket",
            props=S3BucketProps(
                destroy_on_delete=True,
                access_logs=True,
                access_logs_bucket=self.access_logs_bucket,
            ),
        )

        self._vpc = CustomVpc(
            self,
            "MediaLakeVPC",
            props=CustomVpcProps(
                use_existing_vpc=config.vpc.use_existing_vpc,
                existing_vpc=config.vpc.existing_vpc,
                new_vpc=config.vpc.new_vpc,
            ),
        )

        # Security group for Lambdas
        if config.vpc.security_groups.use_existing_groups:
            self._security_group = ec2.SecurityGroup.from_security_group_id(
                self,
                "MediaLakeSecurityGroup",
                security_group_id=config.vpc.security_groups.existing_groups.media_lake_sg,
            )
        else:
            self._security_group = ec2.SecurityGroup(
                self,
                "MediaLakeSecurityGroup",
                vpc=self._vpc.vpc,
                security_group_name=config.vpc.security_groups.new_groups[
                    "media_lake_sg"
                ].name,
                description=config.vpc.security_groups.new_groups[
                    "media_lake_sg"
                ].description,
            )
            # If the environment is prod, apply a retention policy to the security group
            if config.environment == "prod":
                self._security_group.apply_removal_policy(RemovalPolicy.RETAIN)

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
        # Calculate the effective availability zone count based on data node count
        opensearch_settings = config.resolved_opensearch_cluster_settings
        effective_az_count = min(
            opensearch_settings.availability_zone_count,
            opensearch_settings.data_node_count,
        )

        if config.vpc.use_existing_vpc:
            selected_subnet_ids = config.vpc.existing_vpc.subnet_ids["private"][
                :effective_az_count
            ]
        else:
            private_subnets = self._vpc.get_subnet_ids(
                ec2.SubnetType.PRIVATE_WITH_EGRESS
            )
            selected_subnet_ids = [
                subnet["subnet_id"] for subnet in private_subnets[:effective_az_count]
            ]

        # Create a shorter domain name to comply with OpenSearch 28-character limit
        # Original format: {resource_prefix}-os-{region}-{environment}
        # New format: {resource_prefix}-{region_short}-{env_short}
        region_short = region.replace("-", "")[
            :8
        ]  # Remove hyphens and limit to 8 chars
        env_short = config.environment[:3]  # Limit environment to 3 chars
        domain_name = f"{config.resource_prefix}-{region_short}-{env_short}"

        # Ensure domain name doesn't exceed 28 characters
        if len(domain_name) > 28:
            # Further truncate if needed
            max_prefix_length = (
                28 - len(region_short) - len(env_short) - 2
            )  # 2 for hyphens
            domain_name = f"{config.resource_prefix[:max_prefix_length]}-{region_short}-{env_short}"

        self._opensearch_cluster = OpenSearchCluster(
            self,
            "MediaLakeOpenSearch",
            props=OpenSearchClusterProps(
                domain_name=domain_name,
                vpc=self._vpc.vpc,
                subnet_ids=selected_subnet_ids,
                collection_indexes=[opensearch_index_name],
                security_group=self._security_group,
            ),
        )

        # Create S3 Vector cluster
        self._s3_vector_cluster = S3VectorCluster(
            self,
            "MediaLakeS3Vector",
            props=S3VectorClusterProps(
                bucket_name=f"{config.resource_prefix}-vectors-{self.account}-{region}-{config.environment}",
                vector_dimension=1024,
                collection_indexes=[s3_vector_index_name],
                vpc=self._vpc.vpc,
                security_group=self._security_group,
            ),
        )

        # Handle media asset bucket
        if config.s3.use_existing_buckets and config.s3.asset_bucket:
            # Import existing asset bucket
            self.media_assets_s3_bucket = S3Bucket(
                self,
                "MediaAssets",
                props=S3BucketProps(
                    # bucket_name=config.s3.asset_bucket.bucket_name,
                    destroy_on_delete=config.environment != "prod",
                    access_logs=True,
                    access_logs_bucket=self.access_logs_bucket,
                    existing_bucket_arn=config.s3.asset_bucket.bucket_arn,
                    existing_kms_key_arn=(
                        config.s3.asset_bucket.kms_key_arn
                        if config.s3.asset_bucket.kms_key_arn
                        else None
                    ),
                ),
            )
        else:
            # Create new media asset bucket
            self.media_assets_s3_bucket = S3Bucket(
                self,
                "MediaAssets",
                props=S3BucketProps(
                    # bucket_name=f"{config.resource_prefix}-asset-bucket-{config.account_id}-{self.region}-{config.environment}",
                    destroy_on_delete=config.environment != "prod",
                    access_logs=True,
                    access_logs_bucket=self.access_logs_bucket,
                    existing_kms_key_arn=(
                        config.s3.asset_bucket.kms_key_arn
                        if config.s3.use_existing_buckets
                        and config.s3.asset_bucket
                        and config.s3.asset_bucket.kms_key_arn
                        else None
                    ),
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
                                "http://localhost:5174",
                                "http://localhost:3000",
                                "http://localhost:8080",
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
            access_logs_bucket=self.access_logs_bucket,
            source_bucket=self.media_assets_s3_bucket,
        )

        # Create new IAC assets bucket
        self.iac_assets_bucket = S3Bucket(
            self,
            "IACAssets",
            props=S3BucketProps(
                # bucket_name=f"{config.resource_prefix}-iac-assets-{account}-{region}-{config.environment}".lower(),
                destroy_on_delete=True,
                access_logs=True,
                access_logs_bucket=self.access_logs_bucket,
            ),
        )

        self._pipelines_event_bus = EventBus(
            self,
            "PipelinesEventBus",
            props=EventBusConfig(
                bus_name=f"{config.resource_prefix}-pipelines-{region}-{config.environment}",
                description="event bus",
                log_all=False,
            ),
        )

        self._application_service_events_internal_event_bus = EventBus(
            self,
            "ApplicationServiceEventsInternalEventBus",
            props=EventBusConfig(
                bus_name=f"{config.resource_prefix}-application-service-events-internal-{region}-{config.environment}",
                description=f"{config.resource_prefix} application service events for internal use",
                log_all=False,
            ),
        )

        self._application_service_events_external_event_bus = EventBus(
            self,
            "ApplicationServiceEventsExternalEventBus",
            props=EventBusConfig(
                bus_name=f"{config.resource_prefix}-application-service-events-external-{region}-{config.environment}",
                description=f"{config.resource_prefix} application service events for external use",
                log_all=False,
            ),
        )

        # Create a rule to forward all events from internal to external event bus
        # events.Rule(
        #     self,
        #     "InternalToExternalEventBusRule",
        #     event_bus=self._application_service_events_internal_event_bus.event_bus,
        #     description="Forwards all events from internal event bus to external event bus",
        #     event_pattern=events.EventPattern(
        #         source=[account]
        #     ),
        #     targets=[
        #         events.EventBus(self._application_service_events_external_event_bus.event_bus)
        #     ],
        # )

        # Pipeline table

        pipeline_table = DynamoDB(
            self,
            "PipelinesTable",
            props=DynamoDBProps(
                name=f"{config.resource_prefix}_pipeline_table_{config.environment}",
                partition_key_name="id",
                partition_key_type=dynamodb.AttributeType.STRING,
                removal_policy=RemovalPolicy.DESTROY,
            ),
        )
        self._pipeline_table = pipeline_table.table

        # Asset table
        if config.db.use_existing_tables:
            self._asset_table = dynamodb.Table.from_table_arn(
                self,
                "ImportedAssetTable",
                config.db.asset_table_arn,
            )
        else:
            asset_table = DynamoDB(
                self,
                "MediaLakeAssetTable",
                props=DynamoDBProps(
                    name=f"{config.resource_prefix}-asset-table-{config.environment}",
                    partition_key_name="InventoryID",
                    partition_key_type=dynamodb.AttributeType.STRING,
                    pipeline_name=f"{config.resource_prefix}-dynamodb-etl-pipeline",
                    ddb_export_bucket=self.ddb_export_bucket,
                    stream=dynamodb.StreamViewType.NEW_IMAGE,
                    point_in_time_recovery=True,
                    removal_policy=(
                        RemovalPolicy.RETAIN
                        if config.should_retain_tables
                        else RemovalPolicy.DESTROY
                    ),
                ),
            )
            self._asset_table = asset_table.table

            # Add GSIs only for new tables
            self._asset_table.add_global_secondary_index(
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

            self._asset_table.add_global_secondary_index(
                index_name="FileHashIndex",
                partition_key=dynamodb.Attribute(
                    name="FileHash", type=dynamodb.AttributeType.STRING
                ),
                projection_type=dynamodb.ProjectionType.ALL,
            )

            self._asset_table.add_global_secondary_index(
                index_name="S3PathIndex",
                partition_key=dynamodb.Attribute(
                    name="StoragePath", type=dynamodb.AttributeType.STRING
                ),
                projection_type=dynamodb.ProjectionType.ALL,
            )

        ## Asset V2 table, commented out until implementation needed
        # if config.db.use_existing_tables:
        #     self._assetv2_table = dynamodb.Table.from_table_arn(
        #         self,
        #         "ImportedAssetV2Table",
        #         config.db.assetv2_table_arn,
        #     )
        # else:
        #     assetv2_table = DynamoDB(
        #         self,
        #         "MediaLakeAssetTableV2",
        #         props=DynamoDBProps(
        #             name=f"{config.resource_prefix}-asset-table-v2-{config.environment}",
        #             partition_key_name="PK",
        #             partition_key_type=dynamodb.AttributeType.STRING,
        #             point_in_time_recovery=True,
        #             sort_key_name="SK",
        #             sort_key_type=dynamodb.AttributeType.STRING,
        #             removal_policy=(
        #                 RemovalPolicy.RETAIN
        #                 if config.should_retain_tables
        #                 else RemovalPolicy.DESTROY
        #             ),
        #         ),
        #     )
        #     self._assetv2_table = assetv2_table.table

        # if not config.db.use_existing_tables:
        #     # Add GSI1 -
        #     self._assetv2_table.add_global_secondary_index(
        #         index_name="GSI1",
        #         partition_key=dynamodb.Attribute(
        #             name="GSI1PK", type=dynamodb.AttributeType.STRING
        #         ),
        #         sort_key=dynamodb.Attribute(
        #             name="GSI1SK", type=dynamodb.AttributeType.STRING
        #         ),
        #     )

        #     # Add GSI2 - Hash Index
        #     self._assetv2_table.add_global_secondary_index(
        #         index_name="GSI2",
        #         partition_key=dynamodb.Attribute(
        #             name="GSI2PK", type=dynamodb.AttributeType.STRING
        #         ),
        #         sort_key=dynamodb.Attribute(
        #             name="GSI2SK", type=dynamodb.AttributeType.STRING
        #         ),
        #     )

        #     # Add GSI3 - Recent Assets Index
        #     self._assetv2_table.add_global_secondary_index(
        #         index_name="GSI3",
        #         partition_key=dynamodb.Attribute(
        #             name="GSI3PK", type=dynamodb.AttributeType.STRING
        #         ),
        #         sort_key=dynamodb.Attribute(
        #             name="GSI3SK", type=dynamodb.AttributeType.STRING
        #         ),
        #     )

        #     # Add GSI4 - TBD
        #     self._assetv2_table.add_global_secondary_index(
        #         index_name="GSI4",
        #         partition_key=dynamodb.Attribute(
        #             name="GSI4PK", type=dynamodb.AttributeType.STRING
        #         ),
        #         sort_key=dynamodb.Attribute(
        #             name="GSI4SK", type=dynamodb.AttributeType.STRING
        #         ),
        #     )

        #     # Add GSI5 - TBD
        #     self._assetv2_table.add_global_secondary_index(
        #         index_name="GSI5",
        #         partition_key=dynamodb.Attribute(
        #             name="GSI5PK", type=dynamodb.AttributeType.STRING
        #         ),
        #         sort_key=dynamodb.Attribute(
        #             name="GSI5SK", type=dynamodb.AttributeType.STRING
        #         ),
        #     )

        #     # Add GSI6 - TBD
        #     self._assetv2_table.add_global_secondary_index(
        #         index_name="GSI6",
        #         partition_key=dynamodb.Attribute(
        #             name="GSI6PK", type=dynamodb.AttributeType.STRING
        #         ),
        #         sort_key=dynamodb.Attribute(
        #             name="GSI6SK", type=dynamodb.AttributeType.STRING
        #         ),
        #     )

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

        # Lambda warmer EventBridge rule
        if lambda_warmer and lambda_functions_to_warm:
            for fn in lambda_functions_to_warm:
                events.Rule(
                    self,
                    f"{fn.node.id}WarmerRule",
                    event_bus=self._application_service_events_internal_event_bus.event_bus,
                    schedule=events.Schedule.rate(
                        Duration.minutes(LambdaConstants.WARMER_INTERVAL_MINUTES)
                    ),
                    targets=[
                        targets.LambdaFunction(
                            fn,
                            event=events.RuleTargetInput.from_object(
                                {"lambda_warmer": True}
                            ),
                        )
                    ],
                    description=f"Keeps {fn.function_name} warm via scheduled EventBridge rule.",
                )

        # Add outputs for retained resources in prod environment
        self.add_retained_resources_outputs()

    def add_retained_resources_outputs(self):
        """
        Adds CloudFormation outputs for retained resources in production environment.
        Only executes when config.environment == "prod".
        """
        if config.environment != "prod":
            return

        # VPC Outputs
        CfnOutput(
            self,
            "RetainedVpcId",
            value=self._vpc.vpc.vpc_id,
            description="Retained VPC ID",
        )

        CfnOutput(
            self,
            "RetainedVpcCidr",
            value=self._vpc.vpc.vpc_cidr_block,
            description="Retained VPC CIDR Block",
        )

        # Security Group Output
        CfnOutput(
            self,
            "RetainedSecurityGroup",
            value=self._security_group.security_group_id,
            description="Retained Security Group ID",
        )

        # DynamoDB Tables Outputs
        CfnOutput(
            self,
            "RetainedPipelineTable",
            value=f"{self._pipeline_table.table_name}|{self._pipeline_table.table_arn}",
            description="Retained Pipeline Table (Name|ARN)",
        )

        CfnOutput(
            self,
            "RetainedAssetTable",
            value=f"{self._asset_table.table_name}|{self._asset_table.table_arn}",
            description="Retained Asset Table (Name|ARN)",
        )

        # Asset Table GSIs
        CfnOutput(
            self,
            "RetainedAssetTableGSIs",
            value="AssetIDIndex,FileHashIndex,S3PathIndex",
            description="Retained Asset Table GSIs",
        )

        # CfnOutput(
        #     self,
        #     "RetainedAssetV2Table",
        #     value=f"{self._assetv2_table.table_name}|{self._assetv2_table.table_arn}",
        #     description="Retained Asset V2 Table (Name|ARN)",
        # )

        # Asset V2 Table GSIs
        # CfnOutput(
        #     self,
        #     "RetainedAssetV2TableGSIs",
        #     value="GSI1,GSI2,GSI3,GSI4,GSI5,GSI6",
        #     description="Retained Asset V2 Table GSIs",
        # )

        # OpenSearch Cluster Outputs
        CfnOutput(
            self,
            "RetainedOpenSearchCluster",
            value=f"{self._opensearch_cluster.domain_endpoint}|{self._opensearch_cluster.domain_arn}",
            description="Retained OpenSearch Cluster (Endpoint|ARN)",
        )

        # S3 Vector Cluster Outputs
        CfnOutput(
            self,
            "RetainedS3VectorCluster",
            value=f"{self._s3_vector_cluster.bucket_name}|{self._s3_vector_cluster.bucket_arn}",
            description="Retained S3 Vector Cluster (Bucket Name|ARN)",
        )

        CfnOutput(
            self,
            "RetainedS3VectorDimension",
            value=str(self._s3_vector_cluster.vector_dimension),
            description="Retained S3 Vector Dimension",
        )

        CfnOutput(
            self,
            "RetainedS3VectorIndexes",
            value=",".join(self._s3_vector_cluster.indexes),
            description="Retained S3 Vector Indexes",
        )

        # S3 Bucket Outputs
        CfnOutput(
            self,
            "RetainedAccessLogsBucket",
            value=f"{self._access_logs_bucket.bucket_name}|{self._access_logs_bucket.bucket_arn}",
            description="Retained Access Logs Bucket (Name|ARN)",
        )

        CfnOutput(
            self,
            "RetainedAssetBucket",
            value=f"{self.media_assets_s3_bucket.bucket_name}|{self.media_assets_s3_bucket.bucket_arn}",
            description="Retained Asset Bucket (Name|ARN)",
        )

        CfnOutput(
            self,
            "RetainedIACAssetsBucket",
            value=f"{self.iac_assets_bucket.bucket_name}|{self.iac_assets_bucket.bucket_arn}",
            description="Retained IAC Assets Bucket (Name|ARN)",
        )

    @property
    def pipelines_event_bus(self) -> events.EventBus:
        """
        Returns the EventBridge event bus used for pipeline events.

        Returns:
            events.EventBus: The configured EventBridge event bus
        """

        return self._pipelines_event_bus.event_bus

    @property
    def pipelines_event_bus_name(self) -> str:
        """
        Returns the name of the pipelines event bus.

        Returns:
            str: Name of the EventBridge event bus
        """

        return self._pipelines_event_bus.event_bus_name

    @property
    def asset_table(self) -> dynamodb.ITable:
        """
        Returns the DynamoDB table used for storing media asset metadata.

        Returns:
            dynamodb.ITable: The configured DynamoDB table
        """

        return self._asset_table

    @property
    def pipeline_table(self) -> dynamodb.ITable:
        """
        Returns the DynamoDB table used for storing pipelines.

        Returns:
            dynamodb.ITable: The configured DynamoDB table
        """

        return self._pipeline_table

    @property
    def asset_table_name(self) -> str:
        """
        Returns the name of the asset DynamoDB table.

        Returns:
            str: Name of the DynamoDB table
        """

        return self._asset_table.table_name

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

        return f"{self._asset_table.table_arn}/index/FileHashIndex"

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

        return f"{self._asset_table.table_arn}/index/AssetIDIndex"

    @property
    def asset_table_s3_path_index_name(self) -> str:
        """
        Returns the name of the S3Path GSI on the asset table.

        Returns:
            str: Name of the S3Path global secondary index
        """
        return "S3PathIndex"

    @property
    def asset_table_s3_path_index_arn(self) -> str:
        """
        Returns the ARN of the S3Path GSI on the asset table.
        """
        return f"{self._asset_table.table_arn}/index/S3PathIndex"

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
        Returns the media assets bucket.

        Returns:
            s3.IBucket: S3 bucket object
        """
        return self.media_assets_s3_bucket.bucket

    @property
    def access_logs_bucket(self) -> s3.IBucket:
        """
        Returns the access logs bucket, handling both existing and new bucket cases.

        Returns:
            s3.IBucket: The S3 bucket for access logs
        """
        if isinstance(self._access_logs_bucket, S3Bucket):
            return self._access_logs_bucket.bucket
        return self._access_logs_bucket

    @property
    def access_log_bucket(self) -> s3.IBucket:
        """
        Returns the access log bucket.

        Returns:
            s3.IBucket: S3 bucket object
        """
        return self.access_logs_bucket

    @property
    def s3_vector_cluster(self) -> "S3VectorCluster":
        """
        Returns the S3 Vector cluster.

        Returns:
            S3VectorCluster: The configured S3 Vector cluster
        """
        return self._s3_vector_cluster

    @property
    def s3_vector_bucket_name(self) -> str:
        """
        Returns the name of the S3 Vector bucket.

        Returns:
            str: Name of the S3 Vector bucket
        """
        return self._s3_vector_cluster.bucket_name

    @property
    def s3_vector_bucket_arn(self) -> str:
        """
        Returns the ARN of the S3 Vector bucket.

        Returns:
            str: ARN of the S3 Vector bucket
        """
        return self._s3_vector_cluster.bucket_arn

    @property
    def s3_vector_dimension(self) -> int:
        """
        Returns the vector dimension for S3 Vector indexes.

        Returns:
            int: Vector dimension
        """
        return self._s3_vector_cluster.vector_dimension

    @property
    def s3_vector_indexes(self) -> list:
        """
        Returns the list of S3 Vector indexes.

        Returns:
            list: List of S3 Vector index names
        """
        return self._s3_vector_cluster.indexes

    @property
    def s3_vector_index_name(self) -> str:
        """
        Returns the primary S3 Vector index name.

        Returns:
            str: Primary S3 Vector index name
        """
        indexes = self._s3_vector_cluster.indexes
        return indexes[0] if indexes else "media-vectors"
