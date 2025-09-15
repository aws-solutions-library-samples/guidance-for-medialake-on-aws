from dataclasses import dataclass
from typing import Optional

from aws_cdk import Duration, RemovalPolicy, Stack
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_lambda_event_sources as lambda_event_sources
from constructs import Construct

from config import config
from medialake_constructs.shared_constructs.lambda_base import Lambda, LambdaConfig
from medialake_constructs.shared_constructs.lambda_layers import SearchLayer
from medialake_constructs.sqs import SQSConstruct, SQSProps


@dataclass
class AssetTableStreamProps:
    asset_table: dynamodb.ITable
    opensearch_cluster_domain_endpoint: str
    opensearch_cluster_domain_arn: str
    opensearch_cluster_region: str
    opensearch_index_name: str
    vpc: Optional[ec2.Vpc] = None
    security_group: Optional[ec2.SecurityGroup] = None
    batch_size: int = 100


class AssetTableStream(Construct):
    """
    Construct for handling DynamoDB stream events from the asset table.

    Creates a Lambda function that processes DynamoDB stream events and syncs
    data to OpenSearch, with proper IAM permissions and error handling via DLQ.
    """

    def __init__(
        self,
        scope: Construct,
        id: str,
        props: AssetTableStreamProps,
    ) -> None:
        super().__init__(scope, id)

        # Determine the current stack
        stack = Stack.of(self)
        self.region = stack.region
        self.account_id = stack.account

        # Create DLQ for failed stream processing
        self.storage_ingest_connector_dlq = SQSConstruct(
            self,
            "AssetTableStreamDLQ",
            props=SQSProps(
                queue_name="asset-table-stream-dlq",
                visibility_timeout=Duration.seconds(60),
                retention_period=Duration.days(14),
                encryption=True,
                enforce_ssl=True,
                max_receive_count=0,  # No DLQ for this queue as it's already a DLQ
                removal_policy=(
                    RemovalPolicy.RETAIN
                    if config.environment == "prod" and config.should_retain_tables
                    else RemovalPolicy.DESTROY
                ),
            ),
        )

        # Create search layer for opensearch-py and requests_aws4auth dependencies
        search_layer = SearchLayer(self, "SearchLayer")

        # Create the asset table stream Lambda
        self._asset_sync_engine_lambda = Lambda(
            self,
            "AssetTableStream",
            LambdaConfig(
                name="asset-table-stream",
                entry="lambdas/back_end/asset_table_stream",
                timeout_minutes=15,
                vpc=props.vpc,
                security_groups=[props.security_group],
                layers=[search_layer.layer],
                environment_variables={
                    "OS_DOMAIN_REGION": props.opensearch_cluster_region,
                    "OPENSEARCH_ENDPOINT": props.opensearch_cluster_domain_endpoint,
                    "OPENSEARCH_INDEX": props.opensearch_index_name,
                    "SQS_URL": self.storage_ingest_connector_dlq.queue_url,
                },
            ),
        )

        # Add IAM permissions
        self._add_permissions(props)

        # Add DynamoDB stream event source
        self._asset_sync_engine_lambda.function.add_event_source(
            lambda_event_sources.DynamoEventSource(
                props.asset_table,
                starting_position=lambda_.StartingPosition.LATEST,
                batch_size=props.batch_size,
            )
        )

        # Grant stream read permissions
        props.asset_table.grant_stream_read(self._asset_sync_engine_lambda.function)

    def _add_permissions(self, props: AssetTableStreamProps) -> None:
        """Add IAM permissions to the Lambda function."""

        # OpenSearch permissions
        self._asset_sync_engine_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "es:ESHttpHead",
                    "es:ESHttpPost",
                    "es:ESHttpGet",
                    "es:ESHttpPut",
                ],
                resources=[f"{props.opensearch_cluster_domain_arn}/*"],
            )
        )

        # DynamoDB Stream permissions
        self._asset_sync_engine_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "dynamodb:GetShardIterator",
                    "dynamodb:DescribeStream",
                    "dynamodb:ListStreams",
                    "dynamodb:GetRecords",
                ],
                resources=[f"{props.asset_table.table_arn}/stream/*"],
            )
        )

        # SQS permissions for DLQ
        self._asset_sync_engine_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "sqs:SendMessage",
                    "sqs:GetQueueAttributes",
                    "sqs:GetQueueUrl",
                ],
                resources=[self.storage_ingest_connector_dlq.queue_arn],
            )
        )

        # KMS permissions for SQS queue encryption
        if self.storage_ingest_connector_dlq.encryption_key:
            self._asset_sync_engine_lambda.function.add_to_role_policy(
                iam.PolicyStatement(
                    actions=[
                        "kms:Encrypt",
                        "kms:Decrypt",
                        "kms:ReEncrypt*",
                        "kms:GenerateDataKey*",
                        "kms:DescribeKey",
                    ],
                    resources=[
                        self.storage_ingest_connector_dlq.encryption_key.key_arn
                    ],
                )
            )

        # EC2 permissions for VPC Lambda functions
        if props.vpc:
            self._asset_sync_engine_lambda.function.add_to_role_policy(
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "ec2:CreateNetworkInterface",
                        "ec2:DescribeNetworkInterfaces",
                        "ec2:DeleteNetworkInterface",
                    ],
                    resources=["*"],
                )
            )

    @property
    def lambda_function(self) -> Lambda:
        """Returns the asset table stream Lambda function."""
        return self._asset_sync_engine_lambda

    @property
    def dlq(self) -> SQSConstruct:
        """Returns the dead letter queue for failed stream processing."""
        return self.storage_ingest_connector_dlq
