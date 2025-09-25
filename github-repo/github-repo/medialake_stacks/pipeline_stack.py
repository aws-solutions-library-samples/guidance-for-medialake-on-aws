import glob
import json
import os

# from jinja2 import Environment, FileSystemLoader
import time
from dataclasses import dataclass

import aws_cdk as cdk
from aws_cdk import Duration, Fn
from aws_cdk import aws_apigateway as apigateway
from aws_cdk import aws_cognito as cognito
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_events as events
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_secretsmanager as secretsmanager
from aws_cdk import custom_resources as cr

# from config import config
from constructs import Construct

from medialake_constructs.api_gateway.api_gateway_pipelines import (
    ApiGatewayPipelinesConstruct,
    ApiGatewayPipelinesProps,
)
from medialake_stacks.pipelines_executions_stack import (
    PipelinesExecutionsStack,
    PipelinesExecutionsStackProps,
)


@dataclass
class PipelineStackProps:
    iac_assets_bucket: s3.IBucket
    # trigger_node_function_arn: str
    # image_metadata_extractor_function_arn: str
    # image_proxy_function_arn: str
    # video_metadata_extractor_function_arn: str
    # video_proxy_thumbnail_function_arn: str
    # audio_metadata_extractor_function_arn: str
    # audio_proxy_thumbnail_function_arn: str
    # check_media_convert_status_function_arn: str
    cognito_user_pool: cognito.UserPool
    cognito_app_client: cognito.UserPoolClient
    asset_table: dynamodb.TableV2
    connector_table: dynamodb.TableV2
    node_table: dynamodb.TableV2
    pipeline_table: dynamodb.TableV2
    integrations_table: dynamodb.TableV2
    # image_proxy_lambda: lambda_.Function
    # image_metadata_extractor_lambda: lambda_.Function
    iac_assets_bucket: s3.IBucket
    external_payload_bucket: s3.IBucket
    pipelines_nodes_templates_bucket: s3.IBucket
    open_search_endpoint: str
    vpc: ec2.Vpc
    security_group: ec2.SecurityGroup
    pipelines_event_bus: events.EventBus
    media_assets_bucket: s3.IBucket
    x_origin_verify_secret: secretsmanager.Secret
    collection_endpoint: str
    mediaconvert_queue_arn: str
    mediaconvert_role_arn: str
    # S3 Vector configuration
    s3_vector_bucket_name: str
    s3_vector_index_name: str = "media-vectors"
    s3_vector_dimension: int = 1024


class PipelineStack(cdk.NestedStack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        props: PipelineStackProps,
        **kwargs,
    ):
        super().__init__(scope, construct_id, **kwargs)

        api_id = Fn.import_value("MediaLakeApiGatewayCore-ApiGatewayId")
        root_resource_id = Fn.import_value("MediaLakeApiGatewayCore-RootResourceId")

        api = apigateway.RestApi.from_rest_api_attributes(
            self,
            "PipelineStackApi",
            rest_api_id=api_id,
            root_resource_id=root_resource_id,
        )

        self._api_authorizer = apigateway.CognitoUserPoolsAuthorizer(
            self,
            "PipelineStackApiAuthorizer",
            identity_source="method.request.header.Authorization",
            cognito_user_pools=[props.cognito_user_pool],
        )

        self._pipelines_executions_stack = PipelinesExecutionsStack(
            self,
            "PipelinesExecutions",
            props=PipelinesExecutionsStackProps(
                x_origin_verify_secret=props.x_origin_verify_secret,
            ),
        )

        self._pipelines_api = ApiGatewayPipelinesConstruct(
            self,
            "PipelinesApiGateway",
            props=ApiGatewayPipelinesProps(
                api_resource=api.root,
                cognito_authorizer=self._api_authorizer,
                x_origin_verify_secret=props.x_origin_verify_secret,
                asset_table=props.asset_table,
                connector_table=props.connector_table,
                node_table=props.node_table,
                pipeline_table=props.pipeline_table,
                integrations_table=props.integrations_table,
                mediaconvert_queue_arn=props.mediaconvert_queue_arn,
                mediaconvert_role_arn=props.mediaconvert_role_arn,
                iac_assets_bucket=props.iac_assets_bucket,
                external_payload_bucket=props.external_payload_bucket,
                pipelines_nodes_templates_bucket=props.pipelines_nodes_templates_bucket,
                open_search_endpoint=props.collection_endpoint,
                vpc=props.vpc,
                security_group=props.security_group,
                pipelines_event_bus=props.pipelines_event_bus,
                media_assets_bucket=props.media_assets_bucket,
                get_pipelines_executions_lambda=self._pipelines_executions_stack.get_pipelines_executions_lambda,
                post_retry_pipelines_executions_lambda=self._pipelines_executions_stack.post_retry_pipelines_executions_lambda,
                # S3 Vector configuration
                s3_vector_bucket_name=props.s3_vector_bucket_name,
                s3_vector_index_name=props.s3_vector_index_name,
                s3_vector_dimension=props.s3_vector_dimension,
            ),
        )

        ## pipelines deploy
        # Get all JSON files from the pipeline library directory
        pipeline_library_dir = os.path.join(
            os.path.dirname(__file__),
            "..",
            "s3_bucket_assets",
            "pipeline_library",
            "default",
        )

        pipeline_files = glob.glob(os.path.join(pipeline_library_dir, "*.json"))

        for pipeline_file in pipeline_files:
            timestamp = int(time.time())

            # Get the filename without path
            pipeline_filename = os.path.basename(pipeline_file)

            # Read the file content
            with open(pipeline_file, "r") as file:
                pipeline_content = file.read()

            # Parse the JSON to extract the pipeline name
            pipeline_data_json = json.loads(pipeline_content)
            pipeline_name = pipeline_data_json.get(
                "name", os.path.splitext(pipeline_filename)[0]
            )

            # Upload the pipeline definition to the deployment bucket
            deployment = cr.AwsCustomResource(
                self,
                f"Create{pipeline_name.replace(' ', '')}Json",
                on_create=cr.AwsSdkCall(
                    service="S3",
                    action="putObject",
                    parameters={
                        "Bucket": props.iac_assets_bucket.bucket_name,
                        "Key": f"pipeline_library/{pipeline_filename}",
                        "Body": pipeline_content,
                        "ContentType": "application/json",
                    },
                    physical_resource_id=cr.PhysicalResourceId.of(
                        f"Create{pipeline_name.replace(' ', '')}Json-{timestamp}"
                    ),
                ),
                on_update=cr.AwsSdkCall(
                    service="S3",
                    action="putObject",
                    parameters={
                        "Bucket": props.iac_assets_bucket.bucket_name,
                        "Key": f"pipeline_library/{pipeline_filename}",
                        "Body": pipeline_content,
                        "ContentType": "application/json",
                    },
                    physical_resource_id=cr.PhysicalResourceId.of(
                        f"Create{pipeline_name.replace(' ', '')}Json-{timestamp}"
                    ),
                ),
                policy=cr.AwsCustomResourcePolicy.from_statements(
                    [
                        iam.PolicyStatement(
                            actions=[
                                "s3:GetObject",
                                "s3:PutObject",
                                "s3:CopyObject",
                                "s3:ListBucket",
                            ],
                            resources=[
                                f"{props.iac_assets_bucket.bucket_arn}",
                                f"{props.iac_assets_bucket.bucket_arn}/*",
                            ],
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

            # Invoke the post_pipeline Lambda to create the pipeline
            lambda_payload = {
                "httpMethod": "POST",
                "path": "/pipelines",
                "definitionFile": {
                    "bucket": props.iac_assets_bucket.bucket_name,
                    "key": f"pipeline_library/{pipeline_filename}",
                },
                "loadFromS3": True,
            }

            invoke_lambda = cr.AwsCustomResource(
                self,
                f"InvokeLambda{pipeline_name.replace(' ', '')}",
                timeout=Duration.minutes(15),
                on_create=cr.AwsSdkCall(
                    service="Lambda",
                    action="invoke",
                    parameters={
                        "FunctionName": self._pipelines_api.post_pipelines_handler.function_name,
                        "Payload": json.dumps(lambda_payload),
                    },
                    physical_resource_id=cr.PhysicalResourceId.of(
                        f"InvokeLambda{pipeline_name.replace(' ', '')}-{timestamp}"
                    ),
                ),
                on_update=cr.AwsSdkCall(
                    service="Lambda",
                    action="invoke",
                    parameters={
                        "FunctionName": self._pipelines_api.post_pipelines_handler.function_name,
                        "Payload": json.dumps(lambda_payload),
                    },
                    physical_resource_id=cr.PhysicalResourceId.of(
                        f"UpdateLambda{pipeline_name.replace(' ', '')}-{timestamp}"
                    ),
                ),
                policy=cr.AwsCustomResourcePolicy.from_statements(
                    [
                        iam.PolicyStatement(
                            actions=["lambda:InvokeFunction"],
                            resources=[
                                self._pipelines_api.post_pipelines_handler.function_arn
                            ],
                        )
                    ]
                ),
            )

            # invoke_lambda.node.add_dependency(deployment)

    @property
    def post_pipelines_async_handler(self) -> lambda_.Function:
        return self._pipelines_api.post_pipelines_async_handler
