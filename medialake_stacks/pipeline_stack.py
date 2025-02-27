import json
import os
import glob
from jinja2 import Environment, FileSystemLoader
import time

from aws_cdk import (
    Stack,
    aws_iam as iam,
    aws_s3 as s3,
    aws_lambda as lambda_,
    custom_resources as cr,
    Duration,
)

# from config import config
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
    video_proxy_thumbnail_function_arn: str
    check_mediaconvert_status_function_arn: str


class PipelineStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        props: PipelineStackProps,
        **kwargs,
    ):
        super().__init__(scope, construct_id, **kwargs)

        ## pipelines deploy
        default_pipelines_template_dir = os.path.join(
            os.path.dirname(__file__), "..", "default_pipelines"
        )
        jinja_env = Environment(
            loader=FileSystemLoader(default_pipelines_template_dir), autoescape=True
        )

        # Find all Jinja2 templates in the default_pipelines directory
        template_files = glob.glob(
            os.path.join(default_pipelines_template_dir, "*.jinja2")
        )

        for template_file in template_files:
            timestamp = int(time.time())

            template_name = os.path.basename(template_file)
            pipeline_name = template_name.replace(".jinja2", "")

            template = jinja_env.get_template(template_name)

            rendered_pipeline = template.render(
                trigger_node_function_arn=props.trigger_node_function_arn,
                image_metadata_extractor_function_arn=props.image_metadata_extractor_function_arn,
                image_proxy_function_arn=props.image_proxy_function_arn,
                video_metadata_extractor_function_arn=props.video_metadata_extractor_function_arn,
                video_proxy_thumbnail_function_arn=props.video_proxy_thumbnail_function_arn,
                check_mediaconvert_status_function_arn=props.check_mediaconvert_status_function_arn,
            )
            # print(rendered_pipeline)
            rendered_pipeline = json.loads(rendered_pipeline)

            # Replace check_status: true with the actual function ARN
            for node in rendered_pipeline["definition"]["nodes"]:
                if node.get("data", {}).get("check_status") == True:
                    node["data"][
                        "lambda_arn"
                    ] = props.check_mediaconvert_status_function_arn
                    del node["data"]["check_status"]

            pipeline_json = Stack.of(self).to_json_string(rendered_pipeline)
            pipeline_file_name = f"{pipeline_name}.json"

            deployment = cr.AwsCustomResource(
                self,
                f"Create{pipeline_name.capitalize()}Json",
                on_create=cr.AwsSdkCall(
                    service="S3",
                    action="putObject",
                    parameters={
                        "Bucket": props.iac_assets_bucket.bucket_name,
                        "Key": pipeline_file_name,
                        "Body": pipeline_json,
                        "ContentType": "application/json",
                    },
                    physical_resource_id=cr.PhysicalResourceId.of(
                        f"Create{pipeline_name.capitalize()}Json-{timestamp}"
                    ),
                ),
                on_update=cr.AwsSdkCall(
                    service="S3",
                    action="putObject",
                    parameters={
                        "Bucket": props.iac_assets_bucket.bucket_name,
                        "Key": pipeline_file_name,
                        "Body": pipeline_json,
                        "ContentType": "application/json",
                    },
                    physical_resource_id=cr.PhysicalResourceId.of(
                        f"Create{pipeline_name.capitalize()}Json-{timestamp}"
                    ),
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

            pipeline_data = {
                "httpMethod": "POST",
                "path": "/pipelines",
                "definitionFile": {
                    "bucket": props.iac_assets_bucket.bucket_name,
                    "key": pipeline_file_name,
                },
            }

            invoke_lambda = cr.AwsCustomResource(
                self,
                f"InvokeLambda{pipeline_name.capitalize()}",
                timeout=Duration.minutes(15),
                # service_timeout=Duration.minutes(15),
                on_create=cr.AwsSdkCall(
                    service="Lambda",
                    action="invoke",
                    parameters={
                        "FunctionName": props.post_pipeline_lambda.function_name,
                        "Payload": json.dumps(pipeline_data),
                    },
                    physical_resource_id=cr.PhysicalResourceId.of(
                        f"InvokeLambda{pipeline_name.capitalize()}-{timestamp}"
                    ),
                ),
                on_update=cr.AwsSdkCall(
                    service="Lambda",
                    action="invoke",
                    parameters={
                        "FunctionName": props.post_pipeline_lambda.function_name,
                        "Payload": json.dumps(pipeline_data),
                    },
                    physical_resource_id=cr.PhysicalResourceId.of(
                        f"UpdateLambda{pipeline_name.capitalize()}-{timestamp}"
                    ),
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
