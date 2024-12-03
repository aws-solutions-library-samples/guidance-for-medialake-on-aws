import json
from aws_cdk import (
    Stack,
    Environment,
    aws_events as events,
    aws_dynamodb as dynamodb,
    aws_lambda as lambda_,
    aws_iam as iam,
    aws_logs as logs,
    aws_s3 as s3,
    CfnResource,
    aws_ec2 as ec2,
    custom_resources as cr,
    CustomResource,
    Duration,
    RemovalPolicy,
)
from aws_cdk import aws_lambda_event_sources as eventsources
from constructs import Construct

# Local imports
from config import config
from medialake_constructs.shared_constructs.s3bucket import S3Bucket, S3Config
from medialake_constructs.shared_constructs.eventbridge import EventBus, EventBusConfig
from medialake_constructs.vpc import CustomVpc, CustomVpcProps
from medialake_constructs.shared_constructs.opensearch_managed_cluster import (
    OpenSearchCluster,
    OpenSearchClusterProps,
)

from medialake_constructs.shared_constructs.dynamodb import DynamoDB, DynamoDBProps
from medialake_constructs.shared_constructs.lambda_base import (
    Lambda,
    LambdaConfig,
)

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

        # Use the generated name for your Lambda function
        self._vpc = CustomVpc(
            self,
            "MediaLakeVPC",
            props=CustomVpcProps(
                vpc_name=f"{config.global_prefix}-vpc-{self.region}-{config.environment}"
            ),
        )

        # slr = iam.CfnServiceLinkedRole(self, "OpenSearchServiceLinkedRole",
        #     aws_service_name="opensearch.amazonaws.com"
        # )

        # service_linked_role = CfnResource(
        #     self,
        #     "OpenSearchServiceLinkedRole",
        #     type="AWS::IAM::ServiceLinkedRole",
        #     properties={
        #         "AWSServiceName": "es.amazonaws.com",
        #         "Description": "Service-linked role for OpenSearch Service"
        #     }
        # )

        self._security_group = ec2.SecurityGroup(
            self,
            "MediaLakeSecurityGroup",
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

        # Create CloudWatch logs for Ingestion Pipeline
        ingestion_log_group = logs.LogGroup(
            self,
            "IngestionPipelineLogGroup",
            log_group_name=f"/aws/vendedlogs/MediaLakeOpenSearchIngestion-{config.environment}-{self.region}-{config.account_id}",
            removal_policy=RemovalPolicy.DESTROY,
            retention=logs.RetentionDays.ONE_DAY,
        )

        self._opensearch_cluster = OpenSearchCluster(
            self,
            "MediaLakeOpenSearch",
            props=OpenSearchClusterProps(
                domain_name=f"{config.global_prefix}-os-{self.region}-{config.environment}",
                vpc=self._vpc.vpc,
                collection_indexes=["media"],
                security_group=self.security_group,
                master_password=config.opensearch_master_password,
                master_username=config.opensearch_master_username,
            ),
        )

        self.media_assets_bucket = S3Bucket(
            self,
            "MediaAssets",
            s3_config=S3Config(
                bucket_name=f"{config.global_prefix}-asset-bucket-{config.account_id}-{region}-{config.environment}",
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
        self.iac_assets_bucket = S3Bucket(
            self,
            "IACAssets",
            s3_config=S3Config(
                bucket_name=f"{config.global_prefix}-iac-assets-{config.account_id}-{self.region}-{config.environment}".lower(),
            ),
        )

        # Create S3 Bucket for DynamoDB Exports
        self._ddb_export_bucket = S3Bucket(
            self,
            "DynamodbExportBucket",
            s3_config=S3Config(
                bucket_name=f"{config.global_prefix}-ddb-export-{config.account_id}-{self.region}-{config.environment}".lower(),
            ),
        )

        # Create EventBus with retention policy
        ingest_event_bus_config = EventBusConfig(
            bus_name=f"{config.global_prefix}-ingest-{self.region}-{config.environment}",
            description="event bus",
            log_all=True,
        )

        self._ingest_event_bus = EventBus(
            self, "IngestEventBus", props=ingest_event_bus_config
        )

        self._asset_table = DynamoDB(
            self,
            "MediaLakeAssetTable",
            props=DynamoDBProps(
                name="medialake-asset-table",
                partition_key_name="InventoryID",
                partition_key_type=dynamodb.AttributeType.STRING,
                pipeline_name="medialake-dynamodb-etl-pipeline",
                # pipeline_role=self._opensearch_cluster.pipeline_role,
                ddb_export_bucket=self._ddb_export_bucket,
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

        # OS ingest pipeline

        ingestion_pipeline_lambda = Lambda(
            self,
            "AssetTableIngestionPipeline",
            config=LambdaConfig(
                name=f"{config.global_prefix}",
                timeout_minutes=15,
                entry="lambdas/back_end/asset_table_ingestion_pipline",
                environment_variables={
                    "TABLE_ARN": self._asset_table.table_arn,
                    "BUCKET_NAME": self._ddb_export_bucket.bucket.bucket_name,
                    "COLLECTION_ENDPOINT": self._opensearch_cluster.domain_endpoint,
                    "INDEX_NAME": "media",
                    "REGION": self.region,
                    "LOG_GROUP_NAME": ingestion_log_group.log_group_name,
                    "PIPELINE_NAME": f"{config.global_prefix}-etl-pipeline",
                    "SUBNET_IDS_PIPELINE": json.dumps(
                        self._vpc.vpc.select_subnets(
                            subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
                        ).subnet_ids
                    ),
                    "SECURITY_GROUP_IDS": json.dumps(
                        [self._security_group.security_group_id]
                    ),
                },
            ),
        )

        ddb_pipeline_cr_role = ingestion_pipeline_lambda.lambda_role

        pipeline_role = iam.Role(
            self,
            "IngestionRole",
            assumed_by=iam.ServicePrincipal("osis-pipelines.amazonaws.com"),
        )
        # es permissions
        pipeline_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["es:ESHttp*"],
                resources=[f"{self._opensearch_cluster.domain_arn}/*"],
            )
        )

        pipeline_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["es:DescribeDomain"],
                resources=[f"arn:aws:es:*:{self.account}:domain/*"],
            )
        )

        pipeline_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "dynamodb:DescribeTable",
                    "dynamodb:DescribeContinuousBackups",
                    "dynamodb:ExportTableToPointInTime",
                    "dynamodb:DescribeStream",
                ],
                resources=[
                    self._asset_table.table_arn,
                ],
            )
        )
        pipeline_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "dynamodb:GetRecords",
                    "dynamodb:GetShardIterator",
                    "dynamodb:DescribeStream",
                ],
                resources=[f"{self._asset_table.table_arn}/stream/*"],
            )
        )
        pipeline_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["dynamodb:DescribeExport"],
                resources=[f"{self._asset_table.table_arn}/export/*"],
            )
        )

        pipeline_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "s3:GetObject",
                    "s3:PutObject",
                    "s3:DeleteObject",
                    "s3:DeleteObjectVersion",
                    "s3:ListBucket",
                    "s3:DeleteBucket",
                ],
                resources=[
                    self._ddb_export_bucket.bucket.bucket_arn,
                    f"{self._ddb_export_bucket.bucket.bucket_arn}/*",
                ],
            )
        )

        ingestion_pipeline_lambda.function.add_environment(
            "PIPELINE_ROLE_ARN", pipeline_role.role_arn
        )

        # osis permission
        ddb_pipeline_cr_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "osis:CreatePipeline",
                    "osis:ValidatePipeline",
                ],
                resources=[
                    f"arn:aws:osis:{self.region}:{self.account}:pipeline/{config.global_prefix}-etl-pipeline"
                ],
            )
        )

        ddb_pipeline_cr_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "iam:PassRole",
                    "iam:CreateRole",
                    "iam:AttachRolePolicy",
                    "iam:DetachRolePolicy",
                    "iam:GetRole",
                    "iam:DeleteRole",
                ],
                resources=[pipeline_role.role_arn],
            )
        )

        ddb_pipeline_cr_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "logs:CreateLogDelivery",
                    "logs:PutResourcePolicy",
                    "logs:UpdateLogDelivery",
                    "logs:DeleteLogDelivery",
                    "logs:DescribeResourcePolicies",
                    "logs:GetLogDelivery",
                    "logs:ListLogDeliveries",
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents",
                    "logs:DescribeLogGroups",
                ],
                resources=["*"],
            )
        )

        ddb_pipeline_cr_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["iam:ListPolicies"],
                resources=["*"],
            )
        )

        ddb_pipeline_cr_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "iam:CreatePolicy",
                    "iam:DeletePolicy",
                ],
                conditions={
                    "StringEquals": {
                        "iam:PolicyName": [
                            "IngestionPipelinePolicy",
                            "DynamoDBIngestionPolicy",
                        ]
                    }
                },
                resources=["*"],
            )
        )

        ddb_pipeline_cr_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "s3:GetObject",
                    "s3:ListObjects",
                    "s3:DeleteObject",
                    "s3:DeleteObjectVersion",
                    "s3:ListBucket",
                    "s3:DeleteBucket",
                ],
                resources=[
                    self._ddb_export_bucket.bucket.bucket_arn,
                    f"{self._ddb_export_bucket.bucket.bucket_arn}/*",
                ],
            )
        )

        ddb_pipeline_cr_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "ec2:CreateVpcEndpoint",
                    "ec2:DeleteVpcEndpoints",
                    "ec2:ListVpcEndpoints",
                    "ec2:DescribeVpcEndpoints",
                    "ec2:DescribeVpcs",
                    "ec2:DescribeSubnets",
                    "ec2:DescribeSecurityGroups",
                    "ec2:CreateTags",
                    "ec2:DeleteTags",
                    "route53:AssociateVPCWithHostedZone",
                    "route53:DisassociateVPCFromHostedZone",
                ],
                resources=["*"],
            )
        )

        ddb_pipeline_cr_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["osis:Ingest"],
                resources=[
                    f"arn:aws:osis:{self.region}:{self.account}:pipeline/{config.global_prefix}-etl-pipeline"
                ],
            )
        )

        ingestion_pipeline_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "iam:*",
                    "osis:*",
                    "opensearch:*",
                    "dynamodb:*",
                    "s3:*",
                    "ec2:*",
                ],
                resources=["*"],
            )
        )

        # Define Custom Resource for Ingestion Pipeline
        ingestion_provider = cr.Provider(
            self,
            "IngestionProvider",
            on_event_handler=ingestion_pipeline_lambda.function,
        )
        ingestion_custom_resource = CustomResource(
            self,
            "CreateIngestionPipeline",
            service_token=ingestion_provider.service_token,
            properties={
                "PipelineName": "medialake-asset-pipeline",  # Replace as needed
                "TableArn": self._asset_table.table_arn,
                "BucketName": self._ddb_export_bucket.bucket.bucket_arn,
                "CollectionEndpoint": self._opensearch_cluster.domain_endpoint,
                "PipelineRoleArn": pipeline_role.role_arn,
                "Region": self.region,
                "LogGroupName": ingestion_log_group.log_group_name,
                "SubnetIdsPipeline": json.dumps(
                    self._vpc.vpc.select_subnets(
                        subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
                    ).subnet_ids
                ),
                "SecurityGroupIds": json.dumps(
                    [self._security_group.security_group_id]
                ),
            },
        )
        # Ensure the ingestion pipeline is created after the DynamoDB table is populated
        ingestion_custom_resource.node.add_dependency(self._asset_table)
        ingestion_custom_resource.node.add_dependency(pipeline_role)

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
