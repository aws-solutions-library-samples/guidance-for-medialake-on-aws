import json
import os
import tempfile
import shutil

from aws_cdk import (
    Stack,
    aws_dynamodb as dynamodb,
    aws_iam as iam,
    aws_s3 as s3,
    aws_lambda as lambda_,
    aws_s3_deployment as s3deploy,
    custom_resources as cr,
)

from constructs import Construct
from dataclasses import dataclass

# Local imports
from config import config
from medialake_constructs.shared_constructs.dynamodb import DynamoDB, DynamoDBProps

from medialake_constructs.shared_constructs.s3bucket import S3Bucket, S3BucketProps


@dataclass
class PipelineStackProps:
    iac_assets_bucket: s3.IBucket
    post_pipeline_lambda: lambda_.Function
    trigger_node_lambda: lambda_.Function
    image_metadata_extractor_lambda: lambda_.Function
    image_proxy_lambda: lambda_.Function
    video_metadata_extractor_lambda: lambda_.Function
    video_proxy_lambda: lambda_.Function
    video_thumbnail_lambda: lambda_.Function


class PipelineStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        props: PipelineStackProps,
        **kwargs,
    ):
        super().__init__(scope, construct_id, **kwargs)

        self.pipeline_data = {
            "httpMethod": "POST",
            "path": "/pipelines",
            "Definition": "default_image_pipeline.json",
        }

        default_image_pipeline = {
            "definition": {
                "nodes": [
                    {
                        "id": "dndnode_0",
                        "type": "custom",
                        "position": {"x": 154, "y": 273},
                        "data": {
                            "id": props.trigger_node_lambda.function_arn,
                            "type": "trigger",
                            "label": "Image Asset",
                            "icon": {
                                "key": None,
                                "ref": None,
                                "props": {"size": 20},
                                "_owner": None,
                            },
                            "inputTypes": ["image"],
                            "outputTypes": ["image"],
                        },
                        "width": 60,
                        "height": 55,
                        "positionAbsolute": {"x": 154, "y": 273},
                    },
                    {
                        "id": "dndnode_2",
                        "type": "custom",
                        "position": {"x": 187, "y": 380},
                        "data": {
                            "id": props.image_metadata_extractor_lambda.function_arn,
                            "type": "imagemetadata",
                            "label": "Image Metadata",
                            "icon": {
                                "key": None,
                                "ref": None,
                                "props": {"size": 20},
                                "_owner": None,
                            },
                            "inputTypes": ["image"],
                            "outputTypes": ["image"],
                        },
                        "width": 60,
                        "height": 55,
                        "positionAbsolute": {"x": 187, "y": 380},
                    },
                    {
                        "id": "dndnode_3",
                        "type": "custom",
                        "position": {"x": 196, "y": 467},
                        "data": {
                            "id": props.image_proxy_lambda.function_arn,
                            "type": "imageproxy",
                            "label": "Image Proxy",
                            "icon": {
                                "key": None,
                                "ref": None,
                                "props": {"size": 20},
                                "_owner": None,
                            },
                            "inputTypes": ["image"],
                            "outputTypes": ["image"],
                        },
                        "width": 60,
                        "height": 55,
                        "selected": True,
                        "positionAbsolute": {"x": 196, "y": 467},
                        "dragging": False,
                    },
                    {
                        "id": "dndnode_4",
                        "type": "custom",
                        "position": {"x": 216, "y": 582},
                        "data": {
                            "id": props.image_proxy_lambda.function_arn,
                            "type": "imagethumbnail",
                            "label": "Image Thumbnail",
                            "icon": {
                                "key": None,
                                "ref": None,
                                "props": {"size": 20},
                                "_owner": None,
                            },
                            "inputTypes": ["image"],
                            "outputTypes": ["image"],
                        },
                        "width": 60,
                        "height": 55,
                        "positionAbsolute": {"x": 216, "y": 582},
                    },
                ],
                "edges": [
                    {
                        "source": "dndnode_0",
                        "sourceHandle": None,
                        "target": "dndnode_2",
                        "targetHandle": None,
                        "type": "custom",
                        "data": {"text": "to Image Metadata"},
                        "id": "reactflow__edge-dndnode_0-dndnode_2",
                    },
                    {
                        "source": "dndnode_2",
                        "sourceHandle": None,
                        "target": "dndnode_3",
                        "targetHandle": None,
                        "type": "custom",
                        "data": {"text": "to Image Proxy"},
                        "id": "reactflow__edge-dndnode_2-dndnode_3",
                    },
                    {
                        "source": "dndnode_3",
                        "sourceHandle": None,
                        "target": "dndnode_4",
                        "targetHandle": None,
                        "type": "custom",
                        "data": {"text": "to Image Thumbnail"},
                        "id": "reactflow__edge-dndnode_3-dndnode_4",
                    },
                ],
                "viewport": {
                    "x": -130.31858746589876,
                    "y": -141.11180335713357,
                    "zoom": 0.9460576467255969,
                },
            }
        }

        with tempfile.TemporaryDirectory() as tmpdirname:
            # Write JSON string to a file in the temporary directory
            temp_file_path = os.path.join(tmpdirname, "default_image_pipeline.json")
            with open(temp_file_path, "w") as temp_file:
                json.dump(default_image_pipeline, temp_file)

            # Deploy the temporary directory containing the JSON file
            s3deploy.BucketDeployment(
                self,
                "DeployJsonDefaultImagePipeline",
                sources=[s3deploy.Source.asset(tmpdirname)],
                destination_bucket=props.iac_assets_bucket.bucket,
                # destination_key_prefix="optional/prefix/",
            )

        # os.remove(temp_file_path)

        invoke_lambda = cr.AwsCustomResource(
            self,
            "InvokeLambda",
            on_create=cr.AwsSdkCall(
                service="Lambda",
                action="invoke",
                parameters={
                    "FunctionName": props.post_pipeline_lambda.function_name,
                    "Payload": json.dumps(self.pipeline_data),
                },
                physical_resource_id=cr.PhysicalResourceId.of("InvokeLambda"),
            ),
            policy=cr.AwsCustomResourcePolicy.from_statements(
                [
                    iam.PolicyStatement(
                        actions=["lambda:InvokeFunction"],
                        resources=[props.post_pipeline_lambda.function_arn],
                    )
                ]
            ),
        )
