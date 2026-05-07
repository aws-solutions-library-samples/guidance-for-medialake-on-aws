from dataclasses import dataclass
from typing import Optional

from aws_cdk import Duration, RemovalPolicy, Stack
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_lambda_event_sources as lambda_event_sources
from constructs import Construct

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
    max_batch_size: int = 1000
    reserved_concurrency: Optional[int] = 10


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
        # Visibility timeout must be >= Lambda timeout (15 min) + buffer
        self.storage_ingest_connector_dlq = SQSConstruct(
            self,
            "AssetTableStreamDLQ",
            props=SQSProps(
                queue_name="asset-table-stream-dlq",
                visibility_timeout=Duration.minutes(
                    20
                ),  # 15 min Lambda timeout + 5 min buffer
                retention_period=Duration.days(14),
                encryption=False,  # Use SSE-SQS (AWS managed) for consistency with other queues
                enforce_ssl=True,
                max_receive_count=0,  # No DLQ for this queue as it's already a DLQ
                removal_policy=RemovalPolicy.DESTROY,
            ),
        )

        # Create search layer for opensearch-py and requests_aws4auth dependencies
        search_layer = SearchLayer(self, "SearchLayer")

        # Create the asset table stream Lambda
        # Memory set to maximum (10240 MB) to handle bulk operations with large batches
        self._asset_sync_engine_lambda = Lambda(
            self,
            "AssetTableStream",
            LambdaConfig(
                name="asset-table-stream",
                entry="lambdas/back_end/asset_table_stream",
                timeout_minutes=15,
                memory_size=10240,
                vpc=props.vpc,
                security_groups=[props.security_group],
                layers=[search_layer.layer],
                environment_variables={
                    "OS_DOMAIN_REGION": props.opensearch_cluster_region,
                    "OPENSEARCH_ENDPOINT": props.opensearch_cluster_domain_endpoint,
                    "OPENSEARCH_INDEX": props.opensearch_index_name,
                    "SQS_URL": self.storage_ingest_connector_dlq.queue_url,
                    "BULK_BATCH_SIZE": str(props.batch_size),
                    "MAX_BULK_SIZE_MB": "5",
                    "ERROR_THRESHOLD": "0.3",
                    "CIRCUIT_TIMEOUT": "60",
                },
                reserved_concurrent_executions=props.reserved_concurrency,
            ),
        )

        # Add IAM permissions
        self._add_permissions(props)

        # Add DynamoDB stream event source with dynamic batch size
        # Use smaller batch size for normal operations, larger for bulk syncs
        self._asset_sync_engine_lambda.function.add_event_source(
            lambda_event_sources.DynamoEventSource(
                props.asset_table,
                starting_position=lambda_.StartingPosition.LATEST,
                batch_size=props.max_batch_size,
                max_batching_window=Duration.seconds(5),
                retry_attempts=3,
                on_failure=lambda_event_sources.SqsDlq(
                    self.storage_ingest_connector_dlq.queue
                ),
            )
        )

        # Grant stream read permissions
        props.asset_table.grant_stream_read(self._asset_sync_engine_lambda.function)

        # Add explicit queue access policy to prevent public access
        self._add_queue_access_policy()

        # Create DLQ processor Lambda
        self._create_dlq_processor(props, search_layer)

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

    def _add_queue_access_policy(self) -> None:
        """Add explicit access policy to the DLQ to prevent public access."""
        # Allow only the Lambda function to send messages to the queue
        self.storage_ingest_connector_dlq.queue.add_to_resource_policy(
            iam.PolicyStatement(
                sid="AllowLambdaSendMessage",
                effect=iam.Effect.ALLOW,
                principals=[iam.ServicePrincipal("lambda.amazonaws.com")],
                actions=[
                    "sqs:SendMessage",
                    "sqs:GetQueueAttributes",
                    "sqs:GetQueueUrl",
                ],
                resources=[self.storage_ingest_connector_dlq.queue_arn],
                conditions={
                    "ArnEquals": {
                        "aws:SourceArn": self._asset_sync_engine_lambda.function.function_arn
                    }
                },
            )
        )

        # Explicitly deny all actions from any principal outside the account
        self.storage_ingest_connector_dlq.queue.add_to_resource_policy(
            iam.PolicyStatement(
                sid="DenyPublicAccess",
                effect=iam.Effect.DENY,
                principals=[iam.AnyPrincipal()],
                actions=["sqs:*"],
                resources=[self.storage_ingest_connector_dlq.queue_arn],
                conditions={
                    "StringNotEquals": {"aws:PrincipalAccount": self.account_id}
                },
            )
        )

    def _create_dlq_processor(self, props: AssetTableStreamProps, search_layer) -> None:
        """Create Lambda function to reprocess failed messages from DLQ."""

        # Create the DLQ processor Lambda
        self._dlq_processor_lambda = Lambda(
            self,
            "DLQProcessor",
            LambdaConfig(
                name="asset-table-stream-dlq-processor",
                entry="lambdas/back_end/asset_table_stream_dlq_processor",
                timeout_minutes=15,
                memory_size=2048,
                vpc=props.vpc,
                security_groups=(
                    [props.security_group] if props.security_group else None
                ),
                layers=[search_layer.layer],
                environment_variables={
                    "OS_DOMAIN_REGION": props.opensearch_cluster_region,
                    "OPENSEARCH_ENDPOINT": props.opensearch_cluster_domain_endpoint,
                    "OPENSEARCH_INDEX": props.opensearch_index_name,
                },
            ),
        )

        # Add OpenSearch permissions for DLQ processor
        self._dlq_processor_lambda.function.add_to_role_policy(
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

        # Add SQS permissions for reading from DLQ
        self._dlq_processor_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "sqs:ReceiveMessage",
                    "sqs:DeleteMessage",
                    "sqs:GetQueueAttributes",
                    "sqs:GetQueueUrl",
                ],
                resources=[self.storage_ingest_connector_dlq.queue_arn],
            )
        )

        # Add EC2 permissions if using VPC
        if props.vpc:
            self._dlq_processor_lambda.function.add_to_role_policy(
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

        # Add SQS event source (disabled by default - enable manually when needed)
        self._dlq_processor_lambda.function.add_event_source(
            lambda_event_sources.SqsEventSource(
                self.storage_ingest_connector_dlq.queue,
                batch_size=10,  # Small batch size for DLQ processing
                max_batching_window=Duration.minutes(1),
                enabled=False,  # Disabled by default - enable manually when needed
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

    @property
    def dlq_processor(self) -> Lambda:
        """Returns the DLQ processor Lambda function."""
        return self._dlq_processor_lambda
