from datetime import datetime
from aws_cdk import (
    Stack,
    aws_dynamodb as dynamodb,
    aws_s3 as s3,
    aws_s3_deployment as s3deploy,
    custom_resources as cr,
    aws_iam as iam,
    RemovalPolicy,
    CustomResource,
)
import time
import os
import zipfile
import tempfile
import base64
from constructs import Construct
from dataclasses import dataclass
from medialake_constructs.shared_constructs.lam_deployment import LambdaDeployment
from medialake_constructs.shared_constructs.s3bucket import S3Bucket, S3BucketProps
from medialake_constructs.shared_constructs.dynamodb import DynamoDB, DynamoDBProps
from medialake_constructs.shared_constructs.lambda_base import Lambda, LambdaConfig
from config import config


@dataclass
class NodesStackProps:
    iac_bucket: s3.IBucket


class NodesStack(Stack):
    def __init__(
        self, scope: Construct, construct_id: str, props: NodesStackProps, **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Create S3 bucket for node definitions and templates
        self._pipelines_nodes_bucket = S3Bucket(
            self,
            "NodesBucket",
            S3BucketProps(
                bucket_name=f"{config.global_prefix}-nodes-templates-{self.account}-{self.region}--{config.environment}",
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

        # Node Lambda Deployments
        # self.image_metadata_extractor_lambda_deployment = LambdaDeployment(
        #     self,
        #     "ImageMetadataExtractorLambdaDeployment",
        #     destination_bucket=props.iac_bucket.bucket,
        #     parent_folder="nodes",
        #     code_path=["lambdas", "nodes", "image_metadata_extractor"],
        # )
        self.image_metadata_extractor_lambda_deployment = LambdaDeployment(
            self,
            "ImageMetadataExtractorLambdaDeployment",
            destination_bucket=props.iac_bucket.bucket,
            parent_folder="nodes/utility",
            code_path=["lambdas", "nodes", "image_metadata_extractor"],
        )
        self.video_metadata_extractor_lambda_deployment = LambdaDeployment(
            self,
            "VideoMetadataExtractorLambdaDeployment",
            destination_bucket=props.iac_bucket.bucket,
            parent_folder="nodes/utility",
            code_path=["lambdas", "nodes", "video_metadata_extractor"],
        )

        self.api_lambda_deployment = LambdaDeployment(
            self,
            "ApiLambdaDeployment",
            destination_bucket=props.iac_bucket.bucket,
            parent_folder="nodes/integration",
            code_path=["lambdas", "nodes", "api_handler"],
        )

        self.pre_signed_url_lambda_deployment = LambdaDeployment(
            self,
            "PreSignedUrlLambdaDeployment",
            destination_bucket=props.iac_bucket.bucket,
            parent_folder="nodes/utility",
            code_path=["lambdas", "nodes", "pre_signed_url"],
        )

        # Create DynamoDB table for nodes
        self._pipelines_nodes_table = DynamoDB(
            self,
            "PipelineNodesTable",
            props=DynamoDBProps(
                name=f"{config.global_prefix}-pipeline-nodes-{config.environment}",
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
                name=f"{config.global_prefix}-nodes-processor",
                entry="lambdas/nodes/pipeline_nodes_deployment",
                memory_size=256,
                timeout_minutes=15,
                environment_variables={
                    "NODES_TABLE": self._pipelines_nodes_table.table_name,
                    "NODES_BUCKET": self._pipelines_nodes_bucket.bucket_name,
                    "SERVICE_NAME": "pipeline-nodes-deployer",
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

    @property
    def pipelines_nodes_table(self) -> dynamodb.TableV2:
        return self._pipelines_nodes_table.table

    @property
    def pipelines_nodes_templates_bucket(self) -> S3Bucket:
        return self._pipelines_nodes_bucket.bucket
