from datetime import datetime
from aws_cdk import (
    Stack,
    aws_dynamodb as dynamodb,
    aws_s3_deployment as s3deploy,
    custom_resources as cr,
    RemovalPolicy,
    CustomResource,
)
from constructs import Construct
from medialake_constructs.shared_constructs.s3bucket import S3Bucket, S3BucketProps
from medialake_constructs.shared_constructs.dynamodb import DynamoDB, DynamoDBProps
from medialake_constructs.shared_constructs.lambda_base import Lambda, LambdaConfig
from config import config
import aws_cdk


class NodesStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
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

        s3deploy.BucketDeployment(
            self,
            "DeployAssets",
            sources=[s3deploy.Source.asset("s3_bucket_assets/pipeline_nodes")],
            destination_bucket=self._pipelines_nodes_bucket.bucket,
            retain_on_delete=False,
        )

        # Create DynamoDB table for nodes
        self._pipelines_nodes_table = DynamoDB(
            self,
            "PipelineNodesTable",
            DynamoDBProps(
                name=f"{config.global_prefix}-pipeline-nodes-{config.environment}",
                partition_key_name="nodeId",
                partition_key_type=dynamodb.AttributeType.STRING,
                point_in_time_recovery=True,
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

    @property
    def pipelines_nodes_table(self) -> dynamodb.TableV2:
        return self._pipelines_nodes_table.table

    @property
    def pipelines_nodes_templates_bucket(self) -> S3Bucket:
        return self._pipelines_nodes_bucket.bucket
