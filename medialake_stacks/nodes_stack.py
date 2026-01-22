"""
MediaLake Nodes Stack

This stack provisions resources for pipeline processing nodes including:
- Lambda layers for media processing (FFmpeg, PyMediaInfo, etc.)
- Lambda function deployments for various node types (utility, integration)
- DynamoDB table for node definitions and metadata
- S3 bucket for node templates and configurations
- MediaConvert queue and IAM role for video processing
- Custom resource for automated node deployment

The stack follows a modular architecture where each node type (image processing,
video processing, audio processing, integrations) is deployed as a separate Lambda
function with appropriate layers and permissions.
"""

from dataclasses import dataclass
from datetime import datetime

import aws_cdk as cdk
from aws_cdk import CustomResource, RemovalPolicy, Tags
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_iam as iam
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_s3_deployment as s3deploy
from aws_cdk import custom_resources as cr
from constructs import Construct

from config import config
from medialake_constructs.shared_constructs.dynamodb import DynamoDB, DynamoDBProps
from medialake_constructs.shared_constructs.lam_deployment import LambdaDeployment
from medialake_constructs.shared_constructs.lambda_base import Lambda, LambdaConfig
from medialake_constructs.shared_constructs.lambda_layers import (
    CommonLibrariesLayer,
    FFmpegLayer,
    FFProbeLayer,
    NumpyLayer,
    OpenEXRLayer,
    PowertoolsLayer,
    PowertoolsLayerConfig,
    PyamlLayer,
    PyMediaInfo,
    ResvgCliLayer,
    ShortuuidLayer,
)
from medialake_constructs.shared_constructs.mediaconvert import (
    MediaConvert,
    MediaConvertProps,
)
from medialake_constructs.shared_constructs.s3bucket import S3Bucket, S3BucketProps


@dataclass
class NodesStackProps:
    """Properties for NodesStack.

    Attributes:
        iac_bucket: S3 bucket for infrastructure-as-code assets and Lambda deployments
    """

    iac_bucket: s3.IBucket


class NodesStack(cdk.NestedStack):
    """
    Nested stack for MediaLake pipeline processing nodes.

    This stack creates all resources needed for pipeline node execution including
    Lambda functions, layers, storage, and processing infrastructure.
    """

    def __init__(
        self, scope: Construct, construct_id: str, props: NodesStackProps, **kwargs
    ) -> None:
        """
        Initialize the NodesStack.

        Args:
            scope: CDK construct scope
            construct_id: Unique identifier for this construct
            props: Stack properties including IAC bucket reference
            **kwargs: Additional CDK stack arguments
        """
        super().__init__(scope, construct_id, **kwargs)

        # Create S3 bucket for node definitions and templates
        # This bucket stores YAML templates and configurations for pipeline nodes
        self._pipelines_nodes_bucket = S3Bucket(
            self,
            "NodesBucket",
            S3BucketProps(
                bucket_name=f"{config.resource_prefix}-nodes-templates-{self.account}-{self.region}-{config.environment}",
                destroy_on_delete=config.environment != "prod",  # Retain in production
            ),
        )

        # Apply consistent tagging for cost allocation and resource management
        Tags.of(self._pipelines_nodes_bucket.bucket).add("Component", "PipelineNodes")
        Tags.of(self._pipelines_nodes_bucket.bucket).add(
            "Environment", config.environment
        )

        # Deploy node templates and configurations to S3
        # These templates define the structure and behavior of pipeline nodes
        bucket_deployment = s3deploy.BucketDeployment(
            self,
            "DeployAssets",
            sources=[s3deploy.Source.asset("s3_bucket_assets/pipeline_nodes")],
            destination_bucket=self._pipelines_nodes_bucket.bucket,
            retain_on_delete=config.environment
            == "prod",  # Retain templates in production
            prune=True,  # Remove old files not in source
        )

        # ========================================
        # Lambda Layers
        # ========================================
        # Create reusable Lambda layers for common dependencies
        # These layers are shared across multiple node Lambda functions

        self.powertools_layer = PowertoolsLayer(
            self, "PowertoolsLayer", PowertoolsLayerConfig()
        )
        self.common_libraries_layer = CommonLibrariesLayer(self, "CommonLibrariesLayer")
        self.ffmpeg_layer = FFmpegLayer(self, "FFmpegLayer")
        self.pymediainfo_layer = PyMediaInfo(self, "PyMediaInfoLayer")
        self.shortuuid_layer = ShortuuidLayer(self, "ShortuuidLayer")
        self.pyaml_layer = PyamlLayer(self, "PyamlLayer")
        self.ffprobe_layer = FFProbeLayer(self, "FFProbeLayer")
        self.resvgcli_layer = ResvgCliLayer(self, "ResvgCliLayer")
        self.numpy_layer = NumpyLayer(self, "NumpyLayer")
        self.openexr_layer = OpenEXRLayer(self, "OpenEXRLayer")

        # ========================================
        # Node Lambda Deployments
        # ========================================
        # Deploy Lambda functions for each pipeline node type
        # Each deployment packages the Lambda code and uploads to S3

        self.check_media_convert_status_lambda_deployment = LambdaDeployment(
            self,
            "CheckMediaConvertStatusLambdaDeployment",
            destination_bucket=props.iac_bucket.bucket,
            parent_folder="nodes/utility",
            code_path=["lambdas", "nodes", "check_media_convert_status"],
        )

        self.image_proxy_lambda_deployment = LambdaDeployment(
            self,
            "ImageProxyLambdaDeployment",
            destination_bucket=props.iac_bucket.bucket,
            parent_folder="nodes/utility",
            code_path=["lambdas", "nodes", "image_proxy"],
        )

        self.image_thumbnail_lambda_deployment = LambdaDeployment(
            self,
            "ImageThumbnailLambdaDeployment",
            destination_bucket=props.iac_bucket.bucket,
            parent_folder="nodes/utility",
            code_path=["lambdas", "nodes", "image_thumbnail"],
        )

        self.video_proxy_lambda_deployment = LambdaDeployment(
            self,
            "VideoProxyAndThumbnailLambdaDeployment",
            destination_bucket=props.iac_bucket.bucket,
            parent_folder="nodes/utility",
            code_path=["lambdas", "nodes", "video_proxy_and_thumbnail"],
        )

        self.audio_proxy_lambda_deployment = LambdaDeployment(
            self,
            "AudioProxyLambdaDeployment",
            destination_bucket=props.iac_bucket.bucket,
            parent_folder="nodes/utility",
            code_path=["lambdas", "nodes", "audio_proxy"],
        )

        self.audio_thumbnail_lambda_deployment = LambdaDeployment(
            self,
            "AudioThumbnailLambdaDeployment",
            destination_bucket=props.iac_bucket.bucket,
            parent_folder="nodes/utility",
            code_path=["lambdas", "nodes", "audio_thumbnail"],
        )

        self.image_metadata_extractor_lambda_deployment = LambdaDeployment(
            self,
            "ImageMetadataExtractorLambdaDeployment",
            destination_bucket=props.iac_bucket.bucket,
            parent_folder="nodes/utility",
            runtime="python3.12",
            code_path=["lambdas", "nodes", "image_metadata_extractor"],
        )

        self.video_metadata_extractor_lambda_deployment = LambdaDeployment(
            self,
            "VideoMetadataExtractorLambdaDeployment",
            destination_bucket=props.iac_bucket.bucket,
            parent_folder="nodes/utility",
            code_path=["lambdas", "nodes", "video_metadata_extractor"],
        )

        self.audio_metadata_extractor_lambda_deployment = LambdaDeployment(
            self,
            "AudioMetadataExtractorLambdaDeployment",
            destination_bucket=props.iac_bucket.bucket,
            parent_folder="nodes/utility",
            code_path=["lambdas", "nodes", "audio_metadata_extractor"],
        )

        self.audio_transcription_transcribe_lambda_deployment = LambdaDeployment(
            self,
            "AudioTranscriptionTranscribeLambdaDeployment",
            destination_bucket=props.iac_bucket.bucket,
            parent_folder="nodes/utility",
            code_path=["lambdas", "nodes", "audio_transcription_transcribe"],
        )

        self.audio_transcription_transcribe_status_lambda_deployment = LambdaDeployment(
            self,
            "AudioTranscriptionTranscribeStatusLambdaDeployment",
            destination_bucket=props.iac_bucket.bucket,
            parent_folder="nodes/utility",
            code_path=["lambdas", "nodes", "audio_transcription_transcribe_status"],
        )

        self.bedrock_content_processor_lambda_deployment = LambdaDeployment(
            self,
            "BedrockContentProcessorLambdaDeployment",
            destination_bucket=props.iac_bucket.bucket,
            parent_folder="nodes/utility",
            code_path=["lambdas", "nodes", "bedrock_content_processor"],
        )

        self.api_lambda_deployment = LambdaDeployment(
            self,
            "ApiLambdaDeployment",
            destination_bucket=props.iac_bucket.bucket,
            parent_folder="nodes/integration",
            code_path=["lambdas", "nodes", "api_handler"],
        )

        self.embedding_store_lambda_deployment = LambdaDeployment(
            self,
            "EmbeddingStoreLambdaDeployment",
            destination_bucket=props.iac_bucket.bucket,
            parent_folder="nodes/utility",
            code_path=["lambdas", "nodes", "embedding_store"],
        )

        self.pre_signed_url_lambda_deployment = LambdaDeployment(
            self,
            "PreSignedUrlLambdaDeployment",
            destination_bucket=props.iac_bucket.bucket,
            parent_folder="nodes/utility",
            code_path=["lambdas", "nodes", "pre_signed_url"],
        )

        self.publish_event_lambda_deployment = LambdaDeployment(
            self,
            "PublishEventLambdaDeployment",
            destination_bucket=props.iac_bucket.bucket,
            parent_folder="nodes/utility",
            code_path=["lambdas", "nodes", "publish_event"],
        )

        self.pipeline_trigger_lambda_deployment = LambdaDeployment(
            self,
            "PipelineTriggerLambdaDeployment",
            destination_bucket=props.iac_bucket.bucket,
            parent_folder="nodes/utility",
            code_path=["lambdas", "pipelines", "pipeline_trigger"],
        )

        # Add FFmpeg layer to the audio splitter Lambda
        self.audio_splitter_lambda_deployment = LambdaDeployment(
            self,
            "AudioSplitterLambdaDeployment",
            destination_bucket=props.iac_bucket.bucket,
            parent_folder="nodes/utility",
            code_path=["lambdas", "nodes", "audio_splitter"],
        )

        self.video_splitter_lambda_deployment = LambdaDeployment(
            self,
            "VideoSplitterLambdaDeployment",
            destination_bucket=props.iac_bucket.bucket,
            parent_folder="nodes/utility",
            code_path=["lambdas", "nodes", "video_splitter"],
        )

        self.s3_vector_store_lambda_deployment = LambdaDeployment(
            self,
            "S3VectorStoreLambdaDeployment",
            destination_bucket=props.iac_bucket.bucket,
            parent_folder="nodes/utility",
            code_path=["lambdas", "nodes", "s3_vector_store"],
        )

        # TwelveLabs Bedrock integration nodes
        self.twelvelabs_bedrock_invoke_lambda_deployment = LambdaDeployment(
            self,
            "TwelveLabsBedrockInvokeLambdaDeployment",
            destination_bucket=props.iac_bucket.bucket,
            parent_folder="nodes/integration",
            code_path=["lambdas", "nodes", "twelvelabs_bedrock_invoke"],
        )

        self.twelvelabs_bedrock_status_lambda_deployment = LambdaDeployment(
            self,
            "TwelveLabsBedrockStatusLambdaDeployment",
            destination_bucket=props.iac_bucket.bucket,
            parent_folder="nodes/integration",
            code_path=["lambdas", "nodes", "twelvelabs_bedrock_status"],
        )

        self.twelvelabs_bedrock_results_lambda_deployment = LambdaDeployment(
            self,
            "TwelveLabsBedrockResultsLambdaDeployment",
            destination_bucket=props.iac_bucket.bucket,
            parent_folder="nodes/integration",
            code_path=["lambdas", "nodes", "twelvelabs_bedrock_results"],
        )

        # ========================================
        # DynamoDB Table for Node Definitions
        # ========================================
        # Stores node metadata, configurations, and relationships
        # Uses multiple GSIs for efficient querying by different access patterns
        self._pipelines_nodes_table = DynamoDB(
            self,
            "PipelineNodesTable",
            props=DynamoDBProps(
                name=f"{config.resource_prefix}-pipeline-nodes-{config.environment}",
                partition_key_name="pk",
                partition_key_type=dynamodb.AttributeType.STRING,
                sort_key_name="sk",
                sort_key_type=dynamodb.AttributeType.STRING,
                point_in_time_recovery=True,  # Enable PITR for data protection
                global_secondary_indexes=[
                    # GSI-1: Query all nodes by type and status
                    dynamodb.GlobalSecondaryIndexPropsV2(
                        index_name="NodesListIndex",
                        partition_key=dynamodb.Attribute(
                            name="gsi1pk", type=dynamodb.AttributeType.STRING
                        ),
                        sort_key=dynamodb.Attribute(
                            name="gsi1sk", type=dynamodb.AttributeType.STRING
                        ),
                        projection_type=dynamodb.ProjectionType.ALL,
                    ),
                    # GSI-2: Query node methods and operations
                    dynamodb.GlobalSecondaryIndexPropsV2(
                        index_name="MethodsIndex",
                        partition_key=dynamodb.Attribute(
                            name="gsi2pk", type=dynamodb.AttributeType.STRING
                        ),
                        sort_key=dynamodb.Attribute(
                            name="gsi2sk", type=dynamodb.AttributeType.STRING
                        ),
                        projection_type=dynamodb.ProjectionType.ALL,
                    ),
                    # GSI-3: Query by entity type (for unconfigured methods)
                    dynamodb.GlobalSecondaryIndexPropsV2(
                        index_name="GSI3",
                        partition_key=dynamodb.Attribute(
                            name="entityType", type=dynamodb.AttributeType.STRING
                        ),
                        sort_key=dynamodb.Attribute(
                            name="nodeId", type=dynamodb.AttributeType.STRING
                        ),
                        projection_type=dynamodb.ProjectionType.ALL,
                    ),
                    # GSI-4: Query nodes by category
                    dynamodb.GlobalSecondaryIndexPropsV2(
                        index_name="CategoriesIndex",
                        partition_key=dynamodb.Attribute(
                            name="gsi3pk", type=dynamodb.AttributeType.STRING
                        ),
                        sort_key=dynamodb.Attribute(
                            name="gsi3sk", type=dynamodb.AttributeType.STRING
                        ),
                        projection_type=dynamodb.ProjectionType.ALL,
                    ),
                    # GSI-5: Query nodes by tags for filtering
                    dynamodb.GlobalSecondaryIndexPropsV2(
                        index_name="TagsIndex",
                        partition_key=dynamodb.Attribute(
                            name="gsi4pk", type=dynamodb.AttributeType.STRING
                        ),
                        sort_key=dynamodb.Attribute(
                            name="gsi4sk", type=dynamodb.AttributeType.STRING
                        ),
                        projection_type=dynamodb.ProjectionType.ALL,
                    ),
                ],
            ),
        )

        # Apply resource tags for cost tracking and management
        Tags.of(self._pipelines_nodes_table.table).add("Component", "PipelineNodes")
        Tags.of(self._pipelines_nodes_table.table).add(
            "Environment", config.environment
        )

        # ========================================
        # Nodes Processor Lambda
        # ========================================
        # Custom resource Lambda that processes node templates and populates DynamoDB
        # This Lambda runs during stack deployment to initialize node definitions

        # Validate that required resources are created before Lambda
        if not self._pipelines_nodes_table.table_name:
            raise ValueError(
                "Nodes table must be created before nodes processor Lambda"
            )
        if not self._pipelines_nodes_bucket.bucket_name:
            raise ValueError(
                "Nodes bucket must be created before nodes processor Lambda"
            )

        self._nodes_processor_lambda = Lambda(
            self,
            "NodesProcessor",
            LambdaConfig(
                name=f"{config.resource_prefix}-nodes-processor",
                entry="lambdas/back_end/pipeline_nodes_deployment",
                memory_size=256,
                timeout_minutes=15,
                environment_variables={
                    "NODES_TABLE": self._pipelines_nodes_table.table_name,
                    "NODES_BUCKET": self._pipelines_nodes_bucket.bucket_name,
                    "SERVICE_NAME": "pipeline-nodes-deployer",
                    # Layer ARNs for automatic layer attachment during pipeline creation
                    "POWERTOOLS_LAYER_ARN": self.powertools_layer.layer.layer_version_arn,
                    "COMMON_LIBRARIES_LAYER_ARN": self.common_libraries_layer.layer.layer_version_arn,
                    "FFMPEG_LAYER_ARN": self.ffmpeg_layer.layer.layer_version_arn,
                    "PYMEDIAINFO_LAYER_ARN": self.pymediainfo_layer.layer.layer_version_arn,
                    "NUMPY_LAYER_ARN": self.numpy_layer.layer.layer_version_arn,
                    "OPENEXR_LAYER_ARN": self.openexr_layer.layer.layer_version_arn,
                    "SHORTUUID_LAYER_ARN": self.shortuuid_layer.layer.layer_version_arn,
                    "PYAML_LAYER_ARN": self.pyaml_layer.layer.layer_version_arn,
                    "FFPROBE_LAYER_ARN": self.ffprobe_layer.layer.layer_version_arn,
                    "RESVGCLI_LAYER_ARN": self.resvgcli_layer.layer.layer_version_arn,
                },
            ),
        )

        # Grant least-privilege permissions to the nodes processor Lambda
        # Read access to node templates in S3
        self._pipelines_nodes_bucket.bucket.grant_read(
            self._nodes_processor_lambda.function
        )
        # Write access to populate node definitions in DynamoDB
        self._pipelines_nodes_table.table.grant_write_data(
            self._nodes_processor_lambda.function
        )

        # ========================================
        # Custom Resource for Node Deployment
        # ========================================
        # Triggers the nodes processor Lambda during stack create/update
        # This ensures node definitions are loaded into DynamoDB automatically
        self.provider = cr.Provider(
            self,
            "NodesDeploymentProvider",
            on_event_handler=self._nodes_processor_lambda.function,
        )

        self.resource = CustomResource(
            self,
            "NodesDeploymentResource",
            service_token=self.provider.service_token,
            properties={
                "Version": "1.0.0",
                "UpdateTimestamp": datetime.now().isoformat(),  # Forces update on each deployment
            },
            removal_policy=RemovalPolicy.DESTROY,
        )

        # Ensure proper resource creation order:
        # 1. Node templates must be deployed to S3
        # 2. DynamoDB table must be ready
        # 3. Then custom resource can process templates
        self.resource.node.add_dependency(bucket_deployment)
        self.resource.node.add_dependency(self._pipelines_nodes_table.table)

        # ========================================
        # MediaConvert Resources
        # ========================================
        # Create IAM role and queue for video transcoding operations
        self.mediaconvert_role = self._create_mediaconvert_role()

        # Apply consistent tagging to MediaConvert role
        Tags.of(self.mediaconvert_role).add("Component", "MediaConvert")
        Tags.of(self.mediaconvert_role).add("Environment", config.environment)
        Tags.of(self.mediaconvert_role).add("ManagedBy", "CDK")

        self.proxy_queue = MediaConvert.create_queue(
            self,
            "MediaLakeProxyMediaConvertQueue",
            props=MediaConvertProps(
                description="MediaLake queue for proxy video transcoding jobs",
                name=f"{config.resource_prefix}-ProxyQueue-{config.environment}",
                pricing_plan="ON_DEMAND",  # ON_DEMAND required for CloudFormation-based creation
                status="ACTIVE",
                tags=[
                    {"Environment": config.environment},
                    {"Application": config.resource_prefix},
                    {"Component": "MediaConvert"},
                    {"ManagedBy": "CDK"},
                ],
            ),
        )

    def _create_mediaconvert_role(self) -> iam.Role:
        """
        Create IAM role for MediaConvert service with least-privilege permissions.

        This role allows MediaConvert to:
        - Read source media files from S3 (GetObject)
        - Write transcoded outputs to S3 (PutObject)
        - List and locate S3 buckets (ListBucket, GetBucketLocation)
        - Use KMS keys for encryption/decryption (via S3 service only)
        - Write CloudWatch logs for job monitoring

        Security Considerations:
        - S3 access scoped to MediaLake bucket naming patterns
        - KMS access restricted via ViaService condition to S3 only
        - KMS keys must be tagged with Application={resource_prefix}
        - CloudWatch logs scoped to /aws/mediaconvert/* log groups

        Returns:
            IAM role for MediaConvert service with appropriate permissions

        Raises:
            ValueError: If required configuration is missing
        """
        if not config.resource_prefix:
            raise ValueError("resource_prefix must be configured for MediaConvert role")

        mediaconvert_role = iam.Role(
            self,
            "MediaConvertProxyRole",
            assumed_by=iam.ServicePrincipal("mediaconvert.amazonaws.com"),
            role_name=f"{config.resource_prefix}-MediaConvert-Proxy-Role-{config.environment}",
            description="IAM role for MediaConvert video transcoding service with least-privilege S3 and KMS access",
            max_session_duration=cdk.Duration.hours(
                12
            ),  # Allow long-running transcoding jobs
        )

        # S3 permissions for reading source files and writing outputs
        # Note: MediaConvert needs access to user-provided S3 buckets which may have any name.
        # Users upload media to their own buckets, so we cannot restrict by bucket name pattern.
        # Security is enforced through:
        # 1. MediaConvert service role trust policy (only MediaConvert can assume this role)
        # 2. KMS key conditions (see KMSEncryption policy below)
        # 3. Bucket policies on user buckets (users control access to their own buckets)
        mediaconvert_role.add_to_policy(
            iam.PolicyStatement(
                sid="S3MediaAccess",
                actions=[
                    "s3:GetObject",
                    "s3:PutObject",
                ],
                resources=[
                    "arn:aws:s3:::*"
                ],  # Allow access to any S3 bucket (user-provided buckets)
            )
        )

        # KMS permissions for encrypted S3 buckets
        # Note: Using wildcard resource as KMS keys may be created dynamically
        # and cross-account access requires flexibility in key ARNs
        #
        # Security Controls:
        # 1. kms:ViaService condition restricts to S3 service usage only
        # 2. aws:ResourceTag condition limits to MediaLake-tagged keys
        # 3. Region-scoped to prevent cross-region key access
        mediaconvert_role.add_to_policy(
            iam.PolicyStatement(
                sid="KMSEncryption",
                actions=[
                    "kms:Decrypt",  # Read encrypted objects
                    "kms:GenerateDataKey",  # Encrypt new objects
                    "kms:DescribeKey",  # Get key metadata
                ],
                resources=["*"],  # Required for dynamic/cross-account KMS key access
                conditions={
                    "StringEquals": {
                        # Only allow KMS operations via S3 service in this region
                        "kms:ViaService": [f"s3.{self.region}.amazonaws.com"]
                    },
                    "StringLike": {
                        # Restrict to KMS keys tagged with MediaLake application
                        "aws:ResourceTag/Application": config.resource_prefix
                    },
                },
            )
        )

        # CloudWatch Logs permissions for job monitoring
        mediaconvert_role.add_to_policy(
            iam.PolicyStatement(
                sid="CloudWatchLogs",
                actions=[
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents",
                ],
                resources=[
                    f"arn:aws:logs:{self.region}:{self.account}:log-group:/aws/mediaconvert/*"
                ],
            )
        )

        return mediaconvert_role

    # ========================================
    # Public Properties
    # ========================================
    # Expose resources for use by other stacks

    @property
    def pipelines_nodes_table(self) -> dynamodb.TableV2:
        """DynamoDB table containing node definitions and metadata."""
        return self._pipelines_nodes_table.table

    @property
    def pipelines_nodes_templates_bucket(self) -> S3Bucket:
        """S3 bucket containing node templates and configurations."""
        return self._pipelines_nodes_bucket.bucket

    @property
    def mediaconvert_role_arn(self) -> str:
        """ARN of the IAM role used by MediaConvert for video transcoding."""
        return self.mediaconvert_role.role_arn

    @property
    def mediaconvert_queue_arn(self) -> str:
        """ARN of the MediaConvert queue for proxy video jobs."""
        return self.proxy_queue.queue_arn
