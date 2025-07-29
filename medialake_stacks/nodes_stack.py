from dataclasses import dataclass
from datetime import datetime

import aws_cdk as cdk
from aws_cdk import CustomResource, RemovalPolicy
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
    iac_bucket: s3.IBucket


class NodesStack(cdk.NestedStack):
    def __init__(
        self, scope: Construct, construct_id: str, props: NodesStackProps, **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Create S3 bucket for node definitions and templates
        self._pipelines_nodes_bucket = S3Bucket(
            self,
            "NodesBucket",
            S3BucketProps(
                bucket_name=f"{config.resource_prefix}-nodes-templates-{self.account}-{self.region}--{config.environment}",
                destroy_on_delete=True,
            ),
        )

        bucket_deployment = s3deploy.BucketDeployment(
            self,
            "DeployAssets",
            sources=[s3deploy.Source.asset("s3_bucket_assets/pipeline_nodes")],
            destination_bucket=self._pipelines_nodes_bucket.bucket,
            retain_on_delete=False,
        )

        # Create Lambda Layers
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

        # Node Lambda Deployments

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
            runtime="nodejs18.x",
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

        self.debug_input_lambda_deployment = LambdaDeployment(
            self,
            "DebugInputLambdaDeployment",
            destination_bucket=props.iac_bucket.bucket,
            parent_folder="nodes/utility",
            code_path=["lambdas", "nodes", "debug_input"],
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

        self.s3_vector_store_lambda_deployment = LambdaDeployment(
            self,
            "S3VectorStoreLambdaDeployment",
            destination_bucket=props.iac_bucket.bucket,
            parent_folder="nodes/utility",
            code_path=["lambdas", "nodes", "s3_vector_store"],
        )

        # Create DynamoDB table for nodes
        self._pipelines_nodes_table = DynamoDB(
            self,
            "PipelineNodesTable",
            props=DynamoDBProps(
                name=f"{config.resource_prefix}-pipeline-nodes-{config.environment}",
                partition_key_name="pk",
                partition_key_type=dynamodb.AttributeType.STRING,
                sort_key_name="sk",
                sort_key_type=dynamodb.AttributeType.STRING,
                point_in_time_recovery=True,
                global_secondary_indexes=[
                    # GSI-1: Nodes List Index
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
                    # GSI-2: Methods Index
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
                    # GSI-3: Entity Type Index (for unconfigured methods)
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
                    # GSI-4: Categories Index
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
                    # GSI-5: Tags Index
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
                    # Layer ARNs for automatic layer attachment
                    "POWERTOOLS_LAYER_ARN": self.powertools_layer.layer.layer_version_arn,
                    "COMMON_LIBRARIES_LAYER_ARN": self.common_libraries_layer.layer.layer_version_arn,
                    "FFMPEG_LAYER_ARN": self.ffmpeg_layer.layer.layer_version_arn,
                    "PYMEDIAINFO_LAYER_ARN": self.pymediainfo_layer.layer.layer_version_arn,
                    # "JINJA_LAYER_ARN": self.jinja_layer.layer.layer_version_arn,
                    # "OPENSEARCH_LAYER_ARN": self.opensearch_layer.layer.layer_version_arn,
                    "SHORTUUID_LAYER_ARN": self.shortuuid_layer.layer.layer_version_arn,
                    "PYAML_LAYER_ARN": self.pyaml_layer.layer.layer_version_arn,
                    "FFPROBE_LAYER_ARN": self.ffprobe_layer.layer.layer_version_arn,
                    "RESVGCLI_LAYER_ARN": self.resvgcli_layer.layer.layer_version_arn,
                },
            ),
        )

        # Grant Lambda permissions
        self._pipelines_nodes_bucket.bucket.grant_read(
            self._nodes_processor_lambda.function
        )
        self._pipelines_nodes_table.table.grant_write_data(
            self._nodes_processor_lambda.function
        )

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
                "UpdateTimestamp": datetime.now().isoformat(),
            },
            removal_policy=RemovalPolicy.DESTROY,
        )

        self.resource.node.add_dependency(bucket_deployment)

        # Create MediaConvert role and queue
        self.mediaconvert_role = self.create_mediaconvert_role()

        self.proxy_queue = MediaConvert.create_queue(
            self,
            "MediaLakeProxyMediaConvertQueue",
            props=MediaConvertProps(
                description="A MediaLake queue for proxy MediaConvert jobs",
                name="MediaLakeProxyQueue",  # If omitted, one is auto-generated
                pricing_plan="ON_DEMAND",  # Must be ON_DEMAND for CF-based queue creation
                status="ACTIVE",  # Could also be "PAUSED"
                tags=[
                    {"Environment": config.environment},
                    {"Owner": config.resource_prefix},
                ],
            ),
        )

    def create_mediaconvert_role(self):
        mediaconvert_role = iam.Role(
            self,
            "MediaConvertRole",
            assumed_by=iam.ServicePrincipal("mediaconvert.amazonaws.com"),
            role_name=f"{config.resource_prefix}_MediaConvert_Role",
            description="IAM role for MediaConvert",
        )

        mediaconvert_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "s3:GetObject",
                    "s3:PutObject",
                ],
                resources=["arn:aws:s3:::*"],
            )
        )

        mediaconvert_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "kms:Encrypt",
                    "kms:Decrypt",
                    "kms:ReEncrypt*",
                    "kms:GenerateDataKey*",
                    "kms:DescribeKey",
                ],
                resources=["*"],
            )
        )

        mediaconvert_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents",
                ],
                resources=["arn:aws:logs:*:*:*"],
            )
        )

        return mediaconvert_role

    @property
    def pipelines_nodes_table(self) -> dynamodb.TableV2:
        return self._pipelines_nodes_table.table

    @property
    def pipelines_nodes_templates_bucket(self) -> S3Bucket:
        return self._pipelines_nodes_bucket.bucket

    @property
    def mediaconvert_role_arn(self) -> str:
        return self.mediaconvert_role.role_arn

    @property
    def mediaconvert_queue_arn(self) -> str:
        return self.proxy_queue.queue_arn
