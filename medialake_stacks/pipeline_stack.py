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
    aws_apigateway as apigateway,
    aws_cognito as cognito,
    aws_dynamodb as dynamodb,
    aws_ec2 as ec2,
    Fn,
    aws_events as events,
    aws_secretsmanager as secretsmanager
)
from medialake_constructs.api_gateway.api_gateway_pipelines import (
    ApiGatewayPipelinesConstruct,
    ApiGatewayPipelinesProps,
)
from medialake_stacks.pipelines_executions_stack import (
    PipelinesExecutionsStack,
    PipelinesExecutionsStackProps,
)
# from config import config
from constructs import Construct
from dataclasses import dataclass


@dataclass
class PipelineStackProps:
    iac_assets_bucket: s3.IBucket
    trigger_node_function_arn: str
    image_metadata_extractor_function_arn: str
    image_proxy_function_arn: str
    video_metadata_extractor_function_arn: str
    video_proxy_thumbnail_function_arn: str
    audio_metadata_extractor_function_arn: str
    audio_proxy_thumbnail_function_arn: str
    check_mediaconvert_status_function_arn: str
    cognito_user_pool: cognito.UserPool
    cognito_app_client: cognito.UserPoolClient
    asset_table: dynamodb.TableV2
    connector_table: dynamodb.TableV2
    node_table: dynamodb.TableV2
    pipeline_table: dynamodb.TableV2
    image_proxy_lambda: lambda_.Function
    image_metadata_extractor_lambda: lambda_.Function
    iac_assets_bucket: s3.IBucket
    external_payload_bucket: s3.IBucket
    pipelines_nodes_templates_bucket: s3.IBucket
    open_search_endpoint: str
    vpc: ec2.Vpc
    security_group: ec2.SecurityGroup
    ingest_event_bus: events.EventBus
    media_assets_bucket: s3.IBucket
    x_origin_verify_secret: secretsmanager.Secret
    collection_endpoint: str


class PipelineStack(Stack):
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
        
        api = apigateway.RestApi.from_rest_api_attributes(self, "PipelineStackApi",
            rest_api_id=api_id,
            root_resource_id=root_resource_id
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
                image_proxy_lambda=props.image_proxy_lambda,
                image_metadata_extractor_lambda=props.image_metadata_extractor_lambda,
                iac_assets_bucket=props.iac_assets_bucket,
                external_payload_bucket=props.external_payload_bucket,
                pipelines_nodes_templates_bucket=props.pipelines_nodes_templates_bucket,
                open_search_endpoint=props.collection_endpoint,
                vpc=props.vpc,
                security_group=props.security_group,
                ingest_event_bus=props.ingest_event_bus,
                media_assets_bucket=props.media_assets_bucket,
                get_pipelines_executions_lambda=self._pipelines_executions_stack.get_pipelines_executions_lambda,
                post_retry_pipelines_executions_lambda=self._pipelines_executions_stack.post_retry_pipelines_executions_lambda,
            ),
        )
        
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
                audio_metadata_extractor_function_arn=props.audio_metadata_extractor_function_arn,
                audio_proxy_thumbnail_function_arn=props.audio_proxy_thumbnail_function_arn,
                check_mediaconvert_status_function_arn=props.check_mediaconvert_status_function_arn,
            )
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
                on_create=cr.AwsSdkCall(
                    service="Lambda",
                    action="invoke",
                    parameters={
                        "FunctionName": self._pipelines_api.post_pipelines_handler.function_name,
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
                        "FunctionName": self._pipelines_api.post_pipelines_handler.function_name,
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
                            resources=[self._pipelines_api.post_pipelines_handler.function_arn],
                        )
                    ]
                ),
            )

            invoke_lambda.node.add_dependency(deployment)
            

    @property
    def post_pipelinesv2_async_handler(self) -> lambda_.Function:
        return self._pipelines_api.post_pipelinesv2_async_handler