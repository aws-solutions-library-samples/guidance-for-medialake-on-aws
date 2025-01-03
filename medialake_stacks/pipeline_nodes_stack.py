from aws_cdk import (
    Stack,
    aws_dynamodb as dynamodb,
    aws_lambda as lambda_,
    aws_iam as iam,
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
)


@dataclass
class PipelineNodesStackProps:
    asset_table: dynamodb.TableV2


class PipelineNodesStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        props: PipelineNodesStackProps,
        **kwargs,
    ):
        super().__init__(scope, construct_id, **kwargs)

        self._pipeline_nodes_table = DynamoDB(
            self,
            "PipelineNodesTable",
            props=DynamoDBProps(
                name=f"{config.global_prefix}_pipeline_nodes_table",
                partition_key_name="id",
                partition_key_type=dynamodb.AttributeType.STRING,
            ),
        )

        ffprobe_layer = FFProbeLayer(self, "FFProbeLayer")
        pymediainfo_layer = PyMediaInfo(self, "PyMediaInfoLayer")
        layer_objects = [ffprobe_layer.layer, pymediainfo_layer.layer]

        self._trigger_node_lambda = Lambda(
            self,
            "TriggerNode",
            config=LambdaConfig(
                name=f"{config.global_prefix}_trigger_node",
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
                name=f"{config.global_prefix}_video_metadata_extractor_node",
                timeout_minutes=15,
                memory_size=10240,
                architecture=lambda_.Architecture.ARM_64,
                entry="lambdas/nodes/video_metadata_extractor",
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
                name=f"{config.global_prefix}_image_metadata_extractor_node",
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
                name=f"{config.global_prefix}_image_proxy_node",
                memory_size=10240,
                timeout_minutes=15,
                entry="lambdas/nodes/image_proxy",
                environment_variables={
                    "MEDIALAKE_ASSET_TABLE": props.asset_table.table_arn,
                },
            ),
        )

        self._video_proxy_lambda = Lambda(
            self,
            "VideoProxyNode",
            config=LambdaConfig(
                name=f"{config.global_prefix}_video_proxy_node",
                timeout_minutes=15,
                entry="lambdas/nodes/video_proxy",
                environment_variables={
                    "MEDIALAKE_ASSET_TABLE": props.asset_table.table_arn,
                },
            ),
        )

        self._video_thumbnail_lambda = Lambda(
            self,
            "VideoThumbnailNode",
            config=LambdaConfig(
                name=f"{config.global_prefix}_video_thumbnail_node",
                timeout_minutes=15,
                entry="lambdas/nodes/video_thumbnail",
                environment_variables={
                    "MEDIALAKE_ASSET_TABLE": props.asset_table.table_arn,
                },
            ),
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
                        "arn": {"S": self._video_proxy_lambda.function_arn},
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
                        "name": {"S": "video_thumbnail"},
                        "arn": {"S": self._video_thumbnail_lambda.function_arn},
                        "description": {
                            "S": "Generates thumbnail images from video files"
                        },
                        "props": {
                            "M": {
                                "derived_representation": {
                                    "M": {
                                        "thumbnail": {
                                            "M": {
                                                "format": {
                                                    "M": {
                                                        "type": {"S": "string"},
                                                        "default": {"S": "WEBP"},
                                                        "description": {
                                                            "S": "Output format for the thumbnail image"
                                                        },
                                                    }
                                                },
                                                "image_spec": {
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
                                                                            "S": "Width of the thumbnail image"
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
                                                                            "S": "Height of the thumbnail image"
                                                                        },
                                                                    }
                                                                },
                                                            }
                                                        }
                                                    }
                                                },
                                            }
                                        },
                                        "timecode": {
                                            "M": {
                                                "type": {"S": "string"},
                                                "description": {
                                                    "S": "Timecode for thumbnail extraction (e.g., '00:00:30:00')"
                                                },
                                                "optional": {"BOOL": True},
                                            }
                                        },
                                        "percentage": {
                                            "M": {
                                                "type": {"S": "number"},
                                                "description": {
                                                    "S": "Percentage of video duration for thumbnail extraction (e.g., 25 for 25%)"
                                                },
                                                "default": {"N": "25"},
                                                "optional": {"BOOL": True},
                                            }
                                        },
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
    def video_proxy_lambda(self) -> lambda_.Function:
        return self._video_proxy_lambda

    @property
    def video_proxy_function_arn(self) -> str:
        return self._video_proxy_lambda.function_arn

    @property
    def video_thumbnail_lambda(self) -> lambda_.Function:
        return self._video_thumbnail_lambda

    @property
    def video_thumbnail_function_arn(self) -> str:
        return self._video_thumbnail_lambda.function_arn

    @property
    def pipelne_nodes_table(self) -> dynamodb.TableV2:
        return self._pipeline_nodes_table
