import json
import os
from jinja2 import Environment, FileSystemLoader

from aws_cdk import (
    Stack,
    aws_iam as iam,
    aws_s3 as s3,
    aws_lambda as lambda_,
    custom_resources as cr,
)

from constructs import Construct
from dataclasses import dataclass


@dataclass
class PipelineStackProps:
    iac_assets_bucket: s3.IBucket
    post_pipeline_lambda: lambda_.Function
    trigger_node_function_arn: str
    image_metadata_extractor_function_arn: str
    image_proxy_function_arn: str
    video_metadata_extractor_function_arn: str
    video_proxy_function_arn: str
    video_thumbnail_function_arn: str


class PipelineStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        props: PipelineStackProps,
        **kwargs,
    ):
        super().__init__(scope, construct_id, **kwargs)
        default_pipelines_template_dir = os.path.join(
            os.path.dirname(__file__), "..", "default_pipelines"
        )
        jinja_env = Environment(loader=FileSystemLoader(default_pipelines_template_dir))
        default_image_pipeline_template = jinja_env.get_template(
            "default_image_pipeline.jinja2"
        )

        # default_image_pipeline = {
        #     "name": "Default Image Pipeline",
        #     "type": "Ingest Triggered",
        #     "system": True,
        #     "definition": {
        #         "nodes": [
        #             {
        #                 "id": "dndnode_0",
        #                 "type": "custom",
        #                 "position": {"x": 154, "y": 273},
        #                 "data": {
        #                     "id": props.trigger_node_function_arn,
        #                     "type": "trigger",
        #                     "label": "Image Asset",
        #                     "icon": {
        #                         "key": None,
        #                         "ref": None,
        #                         "props": {"size": 20},
        #                         "_owner": None,
        #                     },
        #                     "inputTypes": ["image"],
        #                     "outputTypes": ["image"],
        #                 },
        #                 "width": 60,
        #                 "height": 55,
        #                 "positionAbsolute": {"x": 154, "y": 273},
        #             },
        #             {
        #                 "id": "dndnode_2",
        #                 "type": "custom",
        #                 "position": {"x": 187, "y": 380},
        #                 "data": {
        #                     "id": props.image_metadata_extractor_function_arn,
        #                     "type": "imagemetadata",
        #                     "label": "Image Metadata",
        #                     "icon": {
        #                         "key": None,
        #                         "ref": None,
        #                         "props": {"size": 20},
        #                         "_owner": None,
        #                     },
        #                     "inputTypes": ["image"],
        #                     "outputTypes": ["image"],
        #                 },
        #                 "width": 60,
        #                 "height": 55,
        #                 "positionAbsolute": {"x": 187, "y": 380},
        #             },
        #             {
        #                 "id": "dndnode_3",
        #                 "type": "custom",
        #                 "position": {"x": 196, "y": 467},
        #                 "data": {
        #                     "id": props.image_proxy_function_arn,
        #                     "type": "imageproxy",
        #                     "label": "Image Proxy",
        #                     "icon": {
        #                         "key": None,
        #                         "ref": None,
        #                         "props": {"size": 20},
        #                         "_owner": None,
        #                     },
        #                     "inputTypes": ["image"],
        #                     "outputTypes": ["image"],
        #                 },
        #                 "width": 60,
        #                 "height": 55,
        #                 "selected": True,
        #                 "positionAbsolute": {"x": 196, "y": 467},
        #                 "dragging": False,
        #             },
        #             {
        #                 "id": "dndnode_4",
        #                 "type": "custom",
        #                 "position": {"x": 216, "y": 582},
        #                 "data": {
        #                     "id": props.image_proxy_function_arn,
        #                     "type": "imagethumbnail",
        #                     "label": "Image Thumbnail",
        #                     "icon": {
        #                         "key": None,
        #                         "ref": None,
        #                         "props": {"size": 20},
        #                         "_owner": None,
        #                     },
        #                     "inputTypes": ["image"],
        #                     "outputTypes": ["image"],
        #                 },
        #                 "width": 60,
        #                 "height": 55,
        #                 "positionAbsolute": {"x": 216, "y": 582},
        #             },
        #         ],
        #         "edges": [
        #             {
        #                 "source": "dndnode_0",
        #                 "sourceHandle": None,
        #                 "target": "dndnode_2",
        #                 "targetHandle": None,
        #                 "type": "custom",
        #                 "data": {"text": "to Image Metadata"},
        #                 "id": "reactflow__edge-dndnode_0-dndnode_2",
        #             },
        #             {
        #                 "source": "dndnode_2",
        #                 "sourceHandle": None,
        #                 "target": "dndnode_3",
        #                 "targetHandle": None,
        #                 "type": "custom",
        #                 "data": {"text": "to Image Proxy"},
        #                 "id": "reactflow__edge-dndnode_2-dndnode_3",
        #             },
        #             {
        #                 "source": "dndnode_3",
        #                 "sourceHandle": None,
        #                 "target": "dndnode_4",
        #                 "targetHandle": None,
        #                 "type": "custom",
        #                 "data": {"text": "to Image Thumbnail"},
        #                 "id": "reactflow__edge-dndnode_3-dndnode_4",
        #             },
        #         ],
        #         "viewport": {
        #             "x": -130.31858746589876,
        #             "y": -141.11180335713357,
        #             "zoom": 0.9460576467255969,
        #         },
        #     },
        # }

        default_image_pipeline = default_image_pipeline_template.render(
            trigger_node_function_arn=props.trigger_node_function_arn,
            image_metadata_extractor_function_arn=props.image_metadata_extractor_function_arn,
            image_proxy_function_arn=props.image_proxy_function_arn,
            image_thumbnail_function_arn=props.image_proxy_function_arn,  # Note: This should probably be a separate thumbnail function ARN
        )
        default_image_pipeline = json.loads(default_image_pipeline)

        pipeline_json = Stack.of(self).to_json_string(default_image_pipeline)

        pipeline_file_name = "default_image_pipeline.json"

        # s3_kms_key = kms.Key.from_lookup(self, "S3KMSKey", alias_name="aws/s3")

        deployment = cr.AwsCustomResource(
            self,
            "CreatePipelineJson",
            on_create=cr.AwsSdkCall(
                service="S3",
                action="putObject",
                parameters={
                    "Bucket": props.iac_assets_bucket.bucket_name,
                    "Key": "default_image_pipeline.json",
                    "Body": pipeline_json,
                    "ContentType": "application/json",
                },
                physical_resource_id=cr.PhysicalResourceId.of("CreatePipelineJson"),
            ),
            policy=cr.AwsCustomResourcePolicy.from_statements(
                [
                    iam.PolicyStatement(
                        actions=["s3:PutObject"],
                        resources=[f"{props.iac_assets_bucket.bucket_arn}/*"],
                    ),
                    iam.PolicyStatement(
                        actions=[
                            "kms:Encrypt",
                            "kms:Decrypt",
                            "kms:ReEncrypt*",
                            "kms:GenerateDataKey*",
                            "kms:DescribeKey",
                        ],
                        resources=[
                            props.iac_assets_bucket.bucket.encryption_key.key_arn
                        ],
                    ),
                ]
            ),
        )

        self.pipeline_data = {
            "httpMethod": "POST",
            "path": "/pipelines",
            "definitionFile": {
                "bucket": props.iac_assets_bucket.bucket_name,
                "key": pipeline_file_name,
            },
        }

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

        invoke_lambda.node.add_dependency(deployment)
