from aws_cdk import (
    Stack,
    aws_dynamodb as dynamodb,
    aws_lambda as lambda_,
    aws_iam as iam,
    aws_s3 as s3,
    custom_resources as cr,
)

from constructs import Construct
from dataclasses import dataclass
import uuid

# Local imports
from config import config
from medialake_constructs.shared_constructs.dynamodb import DynamoDB, DynamoDBProps
from medialake_constructs.shared_constructs.lambda_base import (
    Lambda,
    LambdaConfig,
)
from medialake_constructs.shared_constructs.lambda_layers import (
    FFProbeLayer,
    PyMediaInfo,
    CairoSvgLayer
)

from medialake_constructs.shared_constructs.mediaconvert import (
    MediaConvert,
    MediaConvertProps,
)


@dataclass
class PipelineNodesStackProps:
    asset_table: dynamodb.TableV2
    media_assets_bucket: s3.IBucket


class PipelineNodesStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        props: PipelineNodesStackProps,
        **kwargs,
    ):
        super().__init__(scope, construct_id, **kwargs)

        self.mediaconvert_role = self.create_mediaconvert_role()

        if config.db.use_existing_tables:
            self._pipeline_nodes_table = dynamodb.Table.from_table_arn(
                self,
                "ImportedPipelineNodesTable",
                config.db.pipeline_nodes_table_arn,
            )
        else:
            pipeline_nodes_table = DynamoDB(
                self,
                "PipelineNodesTable",
                props=DynamoDBProps(
                    name=f"{config.resource_prefix}_pipeline_nodes_table",
                    partition_key_name="id",
                    partition_key_type=dynamodb.AttributeType.STRING,
                ),
            )
            self._pipeline_nodes_table = pipeline_nodes_table.table

        proxy_queue = MediaConvert.create_queue(
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

        ffprobe_layer = FFProbeLayer(self, "FFProbeLayer")
        pymediainfo_layer = PyMediaInfo(self, "PyMediaInfoLayer")

        layer_objects = [ffprobe_layer.layer, pymediainfo_layer.layer]

        cairosvg_layer = CairoSvgLayer(self, "CairoSvgLayer")

        image_proxy_layer_objects = [cairosvg_layer.layer]

        self._trigger_node_lambda = Lambda(
            self,
            "TriggerNode",
            config=LambdaConfig(
                name=f"{config.resource_prefix}_trigger_node",
                timeout_minutes=5,
                entry="lambdas/nodes/trigger",
                environment_variables={
                    "MEDIALAKE_ASSET_TABLE": props.asset_table.table_arn,
                    "PIPELINE_NODES_TABLE": self._pipeline_nodes_table.table_name,
                },
            ),
        )

        self._video_metadata_extractor_lambda = Lambda(
            self,
            "VideoMetadataExtractorNode",
            config=LambdaConfig(
                name=f"video_metadata_extractor_node",
                timeout_minutes=15,
                memory_size=10240,
                architecture=lambda_.Architecture.X86_64,
                entry="lambdas/nodes/video_metadata_extractor",
                layers=layer_objects,
                environment_variables={
                    "MEDIALAKE_ASSET_TABLE": props.asset_table.table_arn,
                },
            ),
        )

        self._audio_metadata_extractor_lambda = Lambda(
            self,
            "AudioMetadataExtractorNode",
            config=LambdaConfig(
                name="audio_metadata_extractor_node",
                timeout_minutes=15,
                memory_size=10240,
                architecture=lambda_.Architecture.X86_64,
                entry="lambdas/nodes/audio_metadata_extractor",
                layers=layer_objects,
                environment_variables={
                    "MEDIALAKE_ASSET_TABLE": props.asset_table.table_arn,
                },
            ),
        )

        self._image_metadata_extractor_lambda = Lambda(
            self,
            "ImageMetadataExtractorNode",
            config=LambdaConfig(
                name=f"image_metadata_extractor_node",
                runtime=lambda_.Runtime.NODEJS_18_X,
                timeout_minutes=15,
                memory_size=10240,
                architecture=lambda_.Architecture.ARM_64,
                entry="lambdas/nodes/image_metadata_extractor",
                environment_variables={
                    "MEDIALAKE_ASSET_TABLE": props.asset_table.table_arn,
                },
            ),
        )

        self._image_proxy_lambda = Lambda(
            self,
            "ImageProxyNode",
            config=LambdaConfig(
                name=f"image_proxy_node",
                memory_size=10240,
                timeout_minutes=15,
                entry="lambdas/nodes/image_proxy",
                layers=image_proxy_layer_objects,
                environment_variables={
                    "MEDIALAKE_ASSET_TABLE": props.asset_table.table_arn,
                },
            ),
        )

        self._video_proxy_thumbnail_lambda = Lambda(
            self,
            "VideoProxyThumbnailNode",
            config=LambdaConfig(
                name=f"video_proxy_thumbnail_node",
                timeout_minutes=15,
                entry="lambdas/nodes/video_proxy_video_thumbnail",
                environment_variables={
                    "MEDIALAKE_ASSET_TABLE": props.asset_table.table_arn,
                    "MEDIACONVERT_ROLE_ARN": self.mediaconvert_role.role_arn,
                    "MEDIACONVERT_QUEUE": proxy_queue.queue_arn,
                },
            ),
        )

        self._audio_proxy_thumbnail_lambda = Lambda(
            self,
            "AudioProxyThumbnailNode",
            config=LambdaConfig(
                name="audio_proxy_thumbnail_node",
                timeout_minutes=15,
                entry="lambdas/nodes/audio_proxy_audio_thumbnail",
                environment_variables={
                    "MEDIALAKE_ASSET_TABLE": props.asset_table.table_arn,
                    "MEDIACONVERT_ROLE_ARN": self.mediaconvert_role.role_arn,
                    "MEDIACONVERT_QUEUE": proxy_queue.queue_arn,
                },
            ),
        )

        self._check_mediaconvert_status = Lambda(
            self,
            "CheckMediaconvertStatusNode",
            config=LambdaConfig(
                name=f"{config.resource_prefix}_check_mediaconvert_status_node",
                timeout_minutes=15,
                entry="lambdas/nodes/check_mediaconvert_status",
                environment_variables={
                    "MEDIALAKE_ASSET_TABLE": props.asset_table.table_arn,
                    "MEDIACONVERT_ROLE_ARN": self.mediaconvert_role.role_arn,
                    "MEDIACONVERT_QUEUE": proxy_queue.queue_arn,
                },
            ),
        )

        self._check_mediaconvert_status.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "mediaconvert:GetJob",
                    "mediaconvert:ListJobs",
                ],
                resources=[proxy_queue.queue_arn],
            )
        )

        self._video_proxy_thumbnail_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "mediaconvert:CreateJob",
                    "mediaconvert:GetJob",
                    "mediaconvert:ListJobs",
                ],
                resources=[proxy_queue.queue_arn],
            )
        )

        self._audio_proxy_thumbnail_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "mediaconvert:CreateJob",
                    "mediaconvert:GetJob",
                    "mediaconvert:ListJobs",
                ],
                resources=[proxy_queue.queue_arn],
            )
        )

        self._check_mediaconvert_status.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "mediaconvert:ListJobs",
                ],
                resources=[proxy_queue.queue_arn],
            )
        )

        self._check_mediaconvert_status.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "mediaconvert:GetJob",
                ],
                resources=[
                    f"arn:aws:mediaconvert:{Stack.of(self).region}:{Stack.of(self).account}:jobs/*",
                ],
            )
        )

        self._video_proxy_thumbnail_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "mediaconvert:DescribeEndpoints",
                ],
                resources=[
                    f"arn:aws:mediaconvert:{Stack.of(self).region}:{Stack.of(self).account}:endpoints/*",
                ],
            )
        )
        self._audio_proxy_thumbnail_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "mediaconvert:DescribeEndpoints",
                ],
                resources=[
                    f"arn:aws:mediaconvert:{Stack.of(self).region}:{Stack.of(self).account}:endpoints/*",
                ],
            )
        )
        self._video_proxy_thumbnail_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=["iam:PassRole"],
                resources=[self.mediaconvert_role.role_arn],
            )
        )

        self._audio_proxy_thumbnail_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=["iam:PassRole"],
                resources=[self.mediaconvert_role.role_arn],
            )
        )

        # Store the Lambda ARNs in the DynamoDB table via a single BatchWriteItem
        self.store_lambda_arns_in_dynamodb()

    def store_lambda_arns_in_dynamodb(self):
        """
        Uses a single BatchWriteItem call to store all pipeline-node definitions
        in the table. This replaces multiple separate custom resources with one.
        """

        # Helper to generate a unique ID for each item
        def unique_id():
            return {"S": str(uuid.uuid4())}

        # List of items you want to insert into the pipeline-nodes table
        items = [
            {
                "PutRequest": {
                    "Item": {
                        "id": unique_id(),
                        "name": {"S": "trigger_node"},
                        "arn": {"S": self._trigger_node_lambda.function_arn},
                        "description": {
                            "S": "Configurable file type and metadata filter"
                        },
                        "props": {
                            "M": {
                                "file_type": {
                                    "M": {
                                        "type": {"S": "string"},
                                        "description": {
                                            "S": "File type to filter (e.g., 'image', 'video')"
                                        },
                                        "required": {"BOOL": True},
                                    }
                                },
                                "metadata_filters": {
                                    "M": {
                                        "type": {"S": "map"},
                                        "description": {
                                            "S": "Metadata filters to apply"
                                        },
                                        "required": {"BOOL": False},
                                    }
                                },
                            }
                        },
                    }
                }
            },
            {
                "PutRequest": {
                    "Item": {
                        "id": unique_id(),
                        "name": {"S": "image_metadata_extractor"},
                        "arn": {
                            "S": self._image_metadata_extractor_lambda.function_arn
                        },
                        "description": {"S": "Extracts metadata from image files"},
                    }
                }
            },
            {
                "PutRequest": {
                    "Item": {
                        "id": unique_id(),
                        "name": {"S": "image_proxy"},
                        "arn": {"S": self._image_proxy_lambda.function_arn},
                        "description": {"S": "Generates proxy versions of image files"},
                        "props": {
                            "M": {
                                "derived_representation": {
                                    "M": {
                                        "proxy": {
                                            "M": {
                                                "resolution": {
                                                    "M": {
                                                        "width": {
                                                            "M": {
                                                                "type": {
                                                                    "S": "integer"
                                                                },
                                                                "default": {
                                                                    "N": "1280"
                                                                },
                                                                "description": {
                                                                    "S": "Width of the proxy image"
                                                                },
                                                            }
                                                        },
                                                        "height": {
                                                            "M": {
                                                                "type": {
                                                                    "S": "integer"
                                                                },
                                                                "default": {"N": "720"},
                                                                "description": {
                                                                    "S": "Height of the proxy image"
                                                                },
                                                            }
                                                        },
                                                    }
                                                }
                                            }
                                        },
                                        "thumbnail": {
                                            "M": {
                                                "resolution": {
                                                    "M": {
                                                        "width": {
                                                            "M": {
                                                                "type": {
                                                                    "S": "integer"
                                                                },
                                                                "default": {"N": "320"},
                                                                "description": {
                                                                    "S": "Width of the thumbnail image"
                                                                },
                                                            }
                                                        },
                                                        "height": {
                                                            "M": {
                                                                "type": {
                                                                    "S": "integer"
                                                                },
                                                                "default": {"N": "180"},
                                                                "description": {
                                                                    "S": "Height of the thumbnail image"
                                                                },
                                                            }
                                                        },
                                                    }
                                                }
                                            }
                                        },
                                    }
                                }
                            }
                        },
                    }
                }
            },
            {
                "PutRequest": {
                    "Item": {
                        "id": unique_id(),
                        "name": {"S": "video_metadata_extractor"},
                        "arn": {
                            "S": self._video_metadata_extractor_lambda.function_arn
                        },
                        "description": {"S": "Extracts metadata from video files"},
                    }
                }
            },
            {
                "PutRequest": {
                    "Item": {
                        "id": unique_id(),
                        "name": {"S": "video_proxy"},
                        "arn": {"S": self._video_proxy_thumbnail_lambda.function_arn},
                        "description": {"S": "Generates proxy versions of video files"},
                        "props": {
                            "M": {
                                "derived_representation": {
                                    "M": {
                                        "proxy": {
                                            "M": {
                                                "format": {
                                                    "M": {
                                                        "type": {"S": "string"},
                                                        "default": {"S": "MP4"},
                                                        "description": {
                                                            "S": "Output format for the proxy video"
                                                        },
                                                    }
                                                },
                                                "video_spec": {
                                                    "M": {
                                                        "resolution": {
                                                            "M": {
                                                                "width": {
                                                                    "M": {
                                                                        "type": {
                                                                            "S": "integer"
                                                                        },
                                                                        "default": {
                                                                            "N": "640"
                                                                        },
                                                                        "description": {
                                                                            "S": "Width of the proxy video"
                                                                        },
                                                                    }
                                                                },
                                                                "height": {
                                                                    "M": {
                                                                        "type": {
                                                                            "S": "integer"
                                                                        },
                                                                        "default": {
                                                                            "N": "360"
                                                                        },
                                                                        "description": {
                                                                            "S": "Height of the proxy video"
                                                                        },
                                                                    }
                                                                },
                                                            }
                                                        },
                                                        "codec": {
                                                            "M": {
                                                                "type": {"S": "string"},
                                                                "default": {
                                                                    "S": "H_264"
                                                                },
                                                                "description": {
                                                                    "S": "Video codec for the proxy"
                                                                },
                                                            }
                                                        },
                                                    }
                                                },
                                                "audio_spec": {
                                                    "M": {
                                                        "codec": {
                                                            "M": {
                                                                "type": {"S": "string"},
                                                                "default": {"S": "AAC"},
                                                                "description": {
                                                                    "S": "Audio codec for the proxy"
                                                                },
                                                            }
                                                        },
                                                        "bitrate": {
                                                            "M": {
                                                                "type": {
                                                                    "S": "integer"
                                                                },
                                                                "default": {
                                                                    "N": "96000"
                                                                },
                                                                "description": {
                                                                    "S": "Audio bitrate in bits per second"
                                                                },
                                                            }
                                                        },
                                                        "sample_rate": {
                                                            "M": {
                                                                "type": {
                                                                    "S": "integer"
                                                                },
                                                                "default": {
                                                                    "N": "48000"
                                                                },
                                                                "description": {
                                                                    "S": "Audio sample rate in Hz"
                                                                },
                                                            }
                                                        },
                                                    }
                                                },
                                            }
                                        }
                                    }
                                }
                            }
                        },
                    }
                }
            },
            {
                "PutRequest": {
                    "Item": {
                        "id": unique_id(),
                        "name": {"S": "audio_metadata_extractor"},
                        "arn": {
                            "S": self._audio_metadata_extractor_lambda.function_arn
                        },
                        "description": {"S": "Extracts metadata from audio files"},
                    }
                }
            },
            {
                "PutRequest": {
                    "Item": {
                        "id": unique_id(),
                        "name": {"S": "audio_proxy"},
                        "arn": {"S": self._audio_proxy_thumbnail_lambda.function_arn},
                        "description": {"S": "Generates proxy versions of audio files"},
                        "props": {
                            "M": {
                                "derived_representation": {
                                    "M": {
                                        "proxy": {
                                            "M": {
                                                "format": {
                                                    "M": {
                                                        "type": {"S": "string"},
                                                        "default": {"S": "MP3"},
                                                        "description": {
                                                            "S": "Output format for the proxy audio"
                                                        },
                                                    }
                                                },
                                                "audio_spec": {
                                                    "M": {
                                                        "codec": {
                                                            "M": {
                                                                "type": {"S": "string"},
                                                                "default": {"S": "MP3"},
                                                                "description": {
                                                                    "S": "Audio codec for the proxy"
                                                                },
                                                            }
                                                        },
                                                        "bitrate": {
                                                            "M": {
                                                                "type": {
                                                                    "S": "integer"
                                                                },
                                                                "default": {
                                                                    "N": "128000"
                                                                },
                                                                "description": {
                                                                    "S": "Audio bitrate in bits per second"
                                                                },
                                                            }
                                                        },
                                                        "sample_rate": {
                                                            "M": {
                                                                "type": {
                                                                    "S": "integer"
                                                                },
                                                                "default": {
                                                                    "N": "44100"
                                                                },
                                                                "description": {
                                                                    "S": "Audio sample rate in Hz"
                                                                },
                                                            }
                                                        },
                                                    }
                                                },
                                            }
                                        }
                                    }
                                }
                            }
                        },
                    }
                }
            },
            {
                "PutRequest": {
                    "Item": {
                        "id": unique_id(),
                        "name": {"S": "check_mediaconvert_status"},
                        "arn": {"S": self._check_mediaconvert_status.function_arn},
                        "description": {"S": "Checks the status of MediaConvert jobs"},
                    }
                }
            },
            {
                "PutRequest": {
                    "Item": {
                        "id": unique_id(),
                        "name": {"S": "choice"},
                        "description": {"S": "A Choice state"},
                        "props": {
                            "M": {
                                "choices": {
                                    "M": {
                                        "type": {"S": "array"},
                                        "items": {
                                            "M": {
                                                "variable": {"S": "string"},
                                                "condition": {"S": "string"},
                                                "value": {"S": "string"},
                                                "next": {"S": "string"},
                                            }
                                        },
                                        "description": {"S": "Array of choice rules"},
                                    },
                                    "default": {"S": "string"},
                                }
                            }
                        },
                    }
                }
            },
            {
                "PutRequest": {
                    "Item": {
                        "id": unique_id(),
                        "name": {"S": "wait"},
                        "description": {"S": "A Wait state"},
                        "props": {
                            "M": {
                                "seconds": {
                                    "M": {
                                        "type": {"S": "integer"},
                                        "description": {
                                            "S": "Number of seconds to wait"
                                        },
                                        "default": {"N": "60"},
                                    }
                                }
                            }
                        },
                    }
                }
            },
            {
                "PutRequest": {
                    "Item": {
                        "id": unique_id(),
                        "name": {"S": "succeed"},
                        "description": {"S": "A Succeed state"},
                    }
                }
            },
            {
                "PutRequest": {
                    "Item": {
                        "id": unique_id(),
                        "name": {"S": "fail"},
                        "description": {"S": "A Fail state"},
                        "props": {
                            "M": {
                                "cause": {
                                    "M": {
                                        "type": {"S": "string"},
                                        "description": {"S": "Reason for the failure"},
                                        "default": {"S": "Pipeline execution failed"},
                                    }
                                }
                            }
                        },
                    }
                }
            },
        ]

        # Create a single custom resource that calls BatchWriteItem
        cr.AwsCustomResource(
            self,
            "BatchWritePipelineNodes",
            on_create=cr.AwsSdkCall(
                service="DynamoDB",
                action="batchWriteItem",
                parameters={
                    "RequestItems": {self._pipeline_nodes_table.table_name: items}
                },
                # PhysicalResourceId must be unique and change if anything in 'items' changes.
                # A simple approach is to generate a new UUID each time, or derive a hash from the items.
                physical_resource_id=cr.PhysicalResourceId.of(
                    f"BatchWritePipelineNodes-{uuid.uuid4()}"
                ),
            ),
            policy=cr.AwsCustomResourcePolicy.from_statements(
                [
                    iam.PolicyStatement(
                        effect=iam.Effect.ALLOW,
                        actions=["dynamodb:BatchWriteItem"],
                        resources=[self._pipeline_nodes_table.table_arn],
                    )
                ]
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
    def trigger_node_lambda(self) -> lambda_.Function:
        return self._trigger_node_lambda

    @property
    def trigger_node_function_arn(self) -> str:
        return self._trigger_node_lambda.function_arn

    @property
    def image_metadata_extractor_lambda(self) -> lambda_.Function:
        return self._image_metadata_extractor_lambda

    @property
    def image_metadata_extractor_function_arn(self) -> str:
        return self._image_metadata_extractor_lambda.function_arn

    @property
    def image_proxy_lambda(self) -> lambda_.Function:
        return self._image_proxy_lambda

    @property
    def image_proxy_function_arn(self) -> str:
        return self._image_proxy_lambda.function_arn

    @property
    def video_metadata_extractor_lambda(self) -> lambda_.Function:
        return self._video_metadata_extractor_lambda

    @property
    def video_metadata_extractor_function_arn(self) -> str:
        return self._video_metadata_extractor_lambda.function_arn

    @property
    def video_proxy_thumbnail_function_arn(self) -> str:
        return self._video_proxy_thumbnail_lambda.function_arn

    @property
    def check_mediaconvert_status_lambda(self) -> lambda_.Function:
        return self._check_mediaconvert_status

    @property
    def check_mediaconvert_status_function_arn(self) -> str:
        return self._check_mediaconvert_status.function_arn

    @property
    def audio_metadata_extractor_lambda(self) -> lambda_.Function:
        return self._audio_metadata_extractor_lambda

    @property
    def audio_metadata_extractor_function_arn(self) -> str:
        return self._audio_metadata_extractor_lambda.function_arn

    @property
    def audio_proxy_thumbnail_lambda(self) -> lambda_.Function:
        return self._audio_proxy_thumbnail_lambda

    @property
    def audio_proxy_thumbnail_function_arn(self) -> str:
        return self._audio_proxy_thumbnail_lambda.function_arn

    @property
    def pipelne_nodes_table(self) -> dynamodb.ITable:
        return self._pipeline_nodes_table

    def get_functions(self) -> list[lambda_.Function]:
        """Return all Lambda functions in this stack that need warming."""
        return [
            self._trigger_node_lambda.function,
            self._video_metadata_extractor_lambda.function,
            self._image_metadata_extractor_lambda.function,
            self._image_proxy_lambda.function,
            self._video_proxy_thumbnail_lambda.function,
            self._check_mediaconvert_status.function,
            self._audio_metadata_extractor_lambda.function,
            self._audio_proxy_thumbnail_lambda.function,
        ]
