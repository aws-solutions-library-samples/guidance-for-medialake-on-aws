from aws_cdk import (
    Stack,
    aws_dynamodb as dynamodb,
    aws_lambda as lambda_,
    aws_iam as iam,
    custom_resources as cr,
)

from constructs import Construct
from dataclasses import dataclass

# Local imports
from medialake_constructs.shared_constructs.dynamodb import DynamoDB, DynamoDBProps
from medialake_constructs.shared_constructs.lambda_base import (
    Lambda,
    LambdaConfig,
)

import uuid


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
                name=f"medialake_pipeline_nodes_table",
                partition_key_name="id",
                partition_key_type=dynamodb.AttributeType.STRING,
            ),
        )

        self._image_metadata_extractor_lambda = Lambda(
            self,
            "ImageMetadataExtractorNode",
            config=LambdaConfig(
                name="image_metadata_extractor_node",
                runtime=lambda_.Runtime.NODEJS_18_X,
                timeout_minutes=15,
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
                name="image_proxy_node",
                timeout_minutes=15,
                entry="lambdas/nodes/image_proxy",
                environment_variables={
                    "MEDIALAKE_ASSET_TABLE": props.asset_table.table_arn,
                },
            ),
        )

        # Store the Lambda ARNs in the DynamoDB tables
        self.store_lambda_arns_in_dynamodb()

    def store_lambda_arns_in_dynamodb(self):
        # Helper function to create DynamoDB put item AwsSdkCall
        def create_put_item_call(table_name, item):
            return cr.AwsSdkCall(
                service="DynamoDB",
                action="putItem",
                parameters={"TableName": table_name, "Item": item},
                physical_resource_id=cr.PhysicalResourceId.of(table_name + "_insert"),
            )

        # Create DynamoDB put item operations
        self._image_metadata_extractor_item = {
            "id": {"S": str(uuid.uuid4())},
            "name": {"S": "image_metadata_extractor"},
            "arn": {"S": self._image_metadata_extractor_lambda.function_arn},
        }

        self._image_proxy_item = {
            "id": {"S": str(uuid.uuid4())},
            "name": {"S": "image_proxy"},
            "arn": {"S": self._image_proxy_lambda.function_arn},
        }

        cr.AwsCustomResource(
            self,
            "PutImageMetadataExtractorLambdaArn",
            on_create=create_put_item_call(
                self._pipeline_nodes_table.table_name,
                self._image_metadata_extractor_item,
            ),
            policy=cr.AwsCustomResourcePolicy.from_statements(
                [
                    iam.PolicyStatement(
                        effect=iam.Effect.ALLOW,
                        actions=["dynamodb:PutItem"],
                        resources=[self._pipeline_nodes_table.table_arn],
                    )
                ]
            ),
        )

        cr.AwsCustomResource(
            self,
            "PutImageProxyLambdaArn",
            on_create=create_put_item_call(
                self._pipeline_nodes_table.table_name, self._image_proxy_item
            ),
            policy=cr.AwsCustomResourcePolicy.from_statements(
                [
                    iam.PolicyStatement(
                        effect=iam.Effect.ALLOW,
                        actions=["dynamodb:PutItem"],
                        resources=[self._pipeline_nodes_table.table_arn],
                    )
                ]
            ),
        )

    @property
    def image_metadata_extractor(self) -> dict:
        return self._image_metadata_extractor_item

    @property
    def image_proxy_item(self) -> dict:
        return self._image_proxy_item

    @property
    def pipelne_nodes_table(self) -> dynamodb.TableV2:
        return self._pipeline_nodes_table
