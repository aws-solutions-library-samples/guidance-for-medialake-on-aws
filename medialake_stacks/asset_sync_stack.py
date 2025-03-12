from dataclasses import dataclass
from typing import Optional, Dict, Any

from aws_cdk import (
    Duration,
    Stack,
    CfnOutput,
    aws_dynamodb as dynamodb,
    aws_lambda as lambda_,
    aws_lambda_event_sources as lambda_events,
    aws_lambda_event_sources as lambda_event_sources,
    aws_logs as logs,
    aws_events as events,
    aws_events_targets as events_targets,
    aws_sqs as sqs,
    aws_sns as sns,
    aws_sns_subscriptions as sns_subs,
    aws_s3 as s3,
    aws_cloudwatch as cloudwatch,
    aws_cloudwatch_actions as cloudwatch_actions,
    aws_secretsmanager as secretsmanager,
    aws_stepfunctions as sfn,
    aws_stepfunctions_tasks as sfn_tasks,
    aws_iam as iam,
    aws_apigateway as apigateway,
    RemovalPolicy,
)
from constructs import Construct
from medialake_constructs.shared_constructs.dynamodb import DynamoDB, DynamoDBProps
from medialake_constructs.shared_constructs.lambda_base import Lambda, LambdaConfig
from dataclasses import dataclass
from config import config


@dataclass
class AssetSyncStackProps:
    asset_table: dynamodb.TableV2
    ingest_event_bus: events.EventBus


class AssetSyncStack(Stack):
    def __init__(
        self, scope: Construct, construct_id: str, props: AssetSyncStackProps, **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self._asset_sync_job_table = DynamoDB(
            self,
            "AssetSyncJobTable",
            props=DynamoDBProps(
                name="AssetSyncJobTable",
                partition_key_name="jobId",
                partition_key_type=dynamodb.AttributeType.STRING,
            ),
        )

        self._asset_sync_partition_table = DynamoDB(
            self,
            "AssetSyncPartitionTable",
            props=DynamoDBProps(
                name=f"{config.resource_prefix}-asset-sync-partition-table",
                partition_key_name="jobId",
                partition_key_type=dynamodb.AttributeType.STRING,
                sort_key_name="partitionId",
                sort_key_type=dynamodb.AttributeType.STRING,
            ),
        )

        self._asset_sync_partition_table.table.add_global_secondary_index(
            index_name="status-index",
            partition_key=dynamodb.Attribute(
                name="jobId", type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="status", type=dynamodb.AttributeType.STRING
            ),
            projection_type=dynamodb.ProjectionType.ALL,
        )

        self._asset_sync_error_table = DynamoDB(
            self,
            "AssetSyncErrorTable",
            props=DynamoDBProps(
                name=f"{config.resource_prefix}-asset-sync-error-table",
                partition_key_name="jobId",
                partition_key_type=dynamodb.AttributeType.STRING,
                sort_key_name="errorId",
                sort_key_type=dynamodb.AttributeType.STRING,
            ),
        )

        # SQS Queues
        self.dlq = sqs.Queue(
            self,
            "AssetSyncDLQ",
            retention_period=Duration.days(14),
            encryption=sqs.QueueEncryption.SQS_MANAGED,
        )
        self.status_topic = self._create_status_topic()

        # Create SQS Queues for each processing stage
        queues = self._create_queues()
        self.scanner_queue = queues["scanner_queue"]
        self.query_queue = queues["query_queue"]
        self.processing_queue = queues["processing_queue"]
        self.dlq = queues["dlq"]

        self.processing_queue = sqs.Queue(
            self,
            "AssetSyncProcessingQueue",
            visibility_timeout=Duration.minutes(15),
            dead_letter_queue=sqs.DeadLetterQueue(max_receive_count=3, queue=self.dlq),
            encryption=sqs.QueueEncryption.SQS_MANAGED,
        )

        # CloudWatch Log Group for centralized logging
        self.log_group = logs.LogGroup(
            self,
            "AssetSyncLogGroup",
            retention=logs.RetentionDays.TWO_WEEKS,
            removal_policy=RemovalPolicy.DESTROY,
        )

        # Create S3 bucket for intermediate results
        self.results_bucket = self._create_results_bucket()


        # Common Lambda configuration
        asset_sync_lambda_env = {
            "ASSETS_TABLE_NAME": props.asset_table.table_name,
            "JOB_TABLE_NAME": self._asset_sync_job_table.table_name,
            "LOG_GROUP_NAME": self.log_group.log_group_name,
            "PROCESSING_QUEUE_URL": self.processing_queue.queue_url,
            "PARTITION_TABLE_NAME": self._asset_sync_partition_table.table.table_name,
            "ERROR_TABLE_NAME": self._asset_sync_error_table.table.table_name,
            "DLQ_URL": self.dlq.queue_url,
            "INGEST_EVENT_BUS_NAME": props.ingest_event_bus.event_bus_name,
            "SCANNER_QUEUE_URL": self.scanner_queue.queue_url,
            "QUERY_QUEUE_URL": self.query_queue.queue_url,
            "PROCESSING_QUEUE_URL": self.processing_queue.queue_url,
            "DLQ_URL": self.dlq.queue_url,
            "STATUS_TOPIC_ARN": self.status_topic.topic_arn,
            "POWERTOOLS_SERVICE_NAME": "asset-management",
            "POWERTOOLS_METRICS_NAMESPACE": "AssetManagement",
            "LOG_LEVEL": "INFO",
            "RESULTS_BUCKET_NAME": self.results_bucket.bucket_name,
        }

        self._initialize_job_lambda = Lambda(
            self,
            "InitializeJobLambda",
            LambdaConfig(
                name=f"{config.resource_prefix}-initialize-job-{config.environment}",
                entry="lambdas/back_end/asset_sync/initialize_job",
                environment_variables=asset_sync_lambda_env,
            ),
        )

        self._scanner_lambda = Lambda(
            self,
            "ScannerLambda",
            LambdaConfig(
                name=f"{config.resource_prefix}-scanner-{config.environment}",
                entry="lambdas/back_end/asset_sync/scanner",
                environment_variables=asset_sync_lambda_env,
                memory_size=1024,
                timeout_minutes=15,
            ),
        )

        self._query_lambda = Lambda(
            self,
            "QueryLambda",
            LambdaConfig(
                name=f"{config.resource_prefix}-query-{config.environment}",
                entry="lambdas/back_end/asset_sync/query",
                environment_variables=asset_sync_lambda_env,
                memory_size=1024,
                timeout_minutes=15,
            ),
        )

        self._batch_processor_lambda = Lambda(
            self,
            "BatchProcessorLambda",
            LambdaConfig(
                name=f"{config.resource_prefix}-batch-processor-{config.environment}",
                entry="lambdas/back_end/asset_sync/batch_processor",
                environment_variables=asset_sync_lambda_env,
                memory_size=1024,
                timeout_minutes=15,
            ),
        )

        self._processor_lambda = Lambda(
            self,
            "ProcessorLambda",
            LambdaConfig(
                name=f"{config.resource_prefix}-processor-{config.environment}",
                entry="lambdas/back_end/asset_sync/processor",
                environment_variables=asset_sync_lambda_env,
                memory_size=1024,
                timeout_minutes=15,
            ),
        )

        self._dlq_processor_lambda = Lambda(
            self,
            "DLQProcessorLambda",
            LambdaConfig(
                name=f"{config.resource_prefix}-dlq-processor-{config.environment}",
                entry="lambdas/back_end/asset_sync/dlq_processor",
                environment_variables=asset_sync_lambda_env,
                memory_size=1024,
                timeout_minutes=15,
            ),
        )

        self._job_status_lambda = Lambda(
            self,
            "JobStatusLambda",
            LambdaConfig(
                name=f"{config.resource_prefix}-job-status-{config.environment}",
                entry="lambdas/back_end/asset_sync/job_status",
                environment_variables=asset_sync_lambda_env,
                memory_size=1024,
                timeout_minutes=15,
            ),
        )

        self._aggregator_lambda = Lambda(
            self,
            "AggregatorLambda",
            LambdaConfig(
                name=f"{config.resource_prefix}-aggregator-{config.environment}",
                entry="lambdas/back_end/asset_sync/aggregator",
                environment_variables=asset_sync_lambda_env,
                memory_size=1024,
                timeout_minutes=15,
            ),
        )

        self._worker_lambda = Lambda(
            self,
            "WorkerLambda",
            LambdaConfig(
                name=f"{config.resource_prefix}-worker-{config.environment}",
                entry="lambdas/back_end/asset_sync/worker",
                environment_variables=asset_sync_lambda_env,
                memory_size=1024,
                timeout_minutes=15,
            ),
        )

        self._partition_discovery_lambda = Lambda(
            self,
            "PartitionDiscoveryLambda",
            LambdaConfig(
                name=f"{config.resource_prefix}-partition-discovery-{config.environment}",
                entry="lambdas/back_end/asset_sync/partition_discovery",
                memory_size=1024,
                timeout_minutes=15,
                environment_variables=asset_sync_lambda_env,
            ),
        )

        # Add SQS event source to worker lambda
        self._worker_lambda.function.add_event_source(
            lambda_event_sources.SqsEventSource(
                self.processing_queue,
                batch_size=10,
                max_batching_window=Duration.seconds(30),
                report_batch_item_failures=True,
            )
        )

        # Set up Lambda Event Sources
        self._setup_event_sources()

        # Grant permissions
        self._grant_permissions()

        # Grant permissions
        self._asset_sync_job_table.table.grant_read_write_data(
            self._initialize_job_lambda.function
        )
        self._asset_sync_job_table.table.grant_read_write_data(
            self._scanner_lambda.function
        )
        self._asset_sync_job_table.table.grant_read_write_data(
            self._query_lambda.function
        )
        self._asset_sync_job_table.table.grant_read_write_data(
            self._batch_processor_lambda.function
        )
        self._asset_sync_job_table.table.grant_read_write_data(
            self._worker_lambda.function
        )
        self._asset_sync_job_table.table.grant_read_data(
            self._job_status_lambda.function
        )

        props.asset_table.grant_read_data(self._query_lambda.function)
        props.asset_table.grant_read_write_data(self._worker_lambda.function)
        self._asset_sync_job_table.table.grant_read_write_data(
            self._worker_lambda.function
        )

        self.processing_queue.grant_send_messages(self._batch_processor_lambda.function)
        self.processing_queue.grant_consume_messages(self._worker_lambda.function)
        self.dlq.grant_send_messages(self._worker_lambda.function)

        # Add S3 cross-region permissions to scanner lambda
        self._scanner_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "s3:ListBucket",
                    "s3:GetObject",
                    "s3:GetObjectTagging",
                    "s3:PutObjectTagging",
                ],
                resources=["*"],
            )
        )

        # Add S3 permissions to worker lambda
        self._worker_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "s3:GetObject",
                    "s3:GetObjectTagging",
                    "s3:PutObjectTagging",
                    "s3:PutObject",
                ],
                resources=["*"],
            )
        )

        props.ingest_event_bus.grant_put_events_to(self._worker_lambda.function)
        props.asset_table.grant_read_write_data(self._worker_lambda.function)

        # Step Functions Definition - using error handling and retries
        initialize_job_task = sfn_tasks.LambdaInvoke(
            self,
            "InitializeJob",
            lambda_function=self._initialize_job_lambda.function,
            retry_on_service_exceptions=True,
            result_path="$.jobInfo",
            result_selector={
                "jobId.$": "$.Payload.jobId",
                "concurrencyLimit.$": "$.Payload.concurrencyLimit",
                "batchSize.$": "$.Payload.batchSize",
                "bucketName.$": "$.Payload.bucketName",
            },
        )

        scanner_task = sfn_tasks.LambdaInvoke(
            self,
            "ScanS3",
            lambda_function=self._scanner_lambda.function,
            retry_on_service_exceptions=True,
            result_path="$.scanResult",
            # payload=sfn.TaskInput.from_object({
            #     "jobId.$": "$.jobInfo.jobId",
            #     "bucketName.$": "$.jobInfo.bucketName",
            #     "batchSize.$": "$.jobInfo.batchSize",
            #     "continuationToken.$": "$.continuationToken"
            # })
        )

        query_task = sfn_tasks.LambdaInvoke(
            self,
            "QueryAssets",
            lambda_function=self._query_lambda.function,
            retry_on_service_exceptions=True,
            result_path="$.queryResult",
            payload=sfn.TaskInput.from_object(
                {
                    "jobId.$": "$.jobInfo.jobId",
                    "bucketName.$": "$.jobInfo.bucketName",
                    "scanResult.$": "$.scanResult.Payload",
                }
            ),
        )

        process_batch_task = sfn_tasks.LambdaInvoke(
            self,
            "ProcessBatch",
            lambda_function=self._batch_processor_lambda.function,
            retry_on_service_exceptions=True,
            result_path="$.processResult",
            payload=sfn.TaskInput.from_object(
                {
                    "jobId.$": "$.jobInfo.jobId",
                    "bucketName.$": "$.jobInfo.bucketName",
                    "concurrencyLimit.$": "$.jobInfo.concurrencyLimit",
                    "queryResult.$": "$.queryResult.Payload",
                }
            ),
        )

        # Check if there's more data to scan
        check_more_data = sfn.Choice(self, "MoreDataToScan")

        # Define success and complete states
        job_complete = sfn.Succeed(self, "JobComplete")

        # Define the Step Function workflow
        self.state_machine = sfn.StateMachine(
            self,
            "AssetResyncStateMachine",
            definition_body=sfn.DefinitionBody.from_chainable(
                initialize_job_task.next(
                    scanner_task.next(
                        query_task.next(
                            process_batch_task.next(
                                check_more_data.when(
                                    sfn.Condition.boolean_equals(
                                        "$.scanResult.Payload.isTruncated", True
                                    ),
                                    scanner_task,
                                ).otherwise(job_complete)
                            )
                        )
                    )
                )
            ),
            timeout=Duration.hours(24),
            logs=sfn.LogOptions(
                destination=self.log_group,
                level=sfn.LogLevel.ALL,
                include_execution_data=True,
            ),
            tracing_enabled=True,
        )

        self._storage_sync_post_lambda = Lambda(
            self,
            "StorageSyncPostLambda",
            LambdaConfig(
                name=f"{config.resource_prefix}-storage-sync-post-{config.environment}",
                entry="lambdas/api/storage/s3/sync/post_sync",
                memory_size=1024,
                timeout_minutes=15,
                environment_variables={
                    **asset_sync_lambda_env,
                    "STATE_MACHINE_ARN": self.state_machine.state_machine_arn,
                },
            ),
        )

        # Asset Table permissions
        props.asset_table.grant_read_data(self._query_lambda.function)
        props.asset_table.grant_read_write_data(self._processor_lambda.function)

    def _create_status_topic(self) -> sns.Topic:
        return sns.Topic(
            self,
            "AssetSyncStatusTopic",
            topic_name=f"{config.resource_prefix}-asset-sync-status-topic",
        )

    def _create_queues(self) -> Dict[str, sqs.Queue]:
        """Create SQS queues for each processing stage"""
        # Dead Letter Queue
        dlq = sqs.Queue(
            self,
            "AssetDLQ",
            retention_period=Duration.days(14),
            encryption=sqs.QueueEncryption.SQS_MANAGED,
            visibility_timeout=Duration.minutes(15),
        )

        # Scanner Queue - Standard for high throughput
        scanner_queue = sqs.Queue(
            self,
            "ScannerQueue",
            visibility_timeout=Duration.minutes(15),
            encryption=sqs.QueueEncryption.SQS_MANAGED,
            dead_letter_queue=sqs.DeadLetterQueue(max_receive_count=3, queue=dlq),
        )
        # Query Queue - Standard for high throughput
        query_queue = sqs.Queue(
            self,
            "QueryQueue",
            visibility_timeout=Duration.minutes(15),
            encryption=sqs.QueueEncryption.SQS_MANAGED,
            dead_letter_queue=sqs.DeadLetterQueue(max_receive_count=3, queue=dlq),
        )

        # Processing Queue - High throughput FIFO
        processing_queue = sqs.Queue(
            self,
            "ProcessingQueue.fifo",
            # fifo=True,
            # content_based_deduplication=True,
            visibility_timeout=Duration.minutes(15),
            encryption=sqs.QueueEncryption.SQS_MANAGED,
            dead_letter_queue=sqs.DeadLetterQueue(max_receive_count=3, queue=dlq),
        )

        return {
            "scanner_queue": scanner_queue,
            "query_queue": query_queue,
            "processing_queue": processing_queue,
            "dlq": dlq,
        }

    def _get_lambda_environment(self) -> Dict[str, str]:
        """Get common Lambda environment variables"""
        return {
            "POWERTOOLS_SERVICE_NAME": "asset-management",
            "POWERTOOLS_METRICS_NAMESPACE": "AssetManagement",
            "LOG_LEVEL": "INFO",
            # "ASSETS_TABLE_NAME": self._asset_table.table.table_name,
            "JOB_TABLE_NAME": self._asset_sync_job_table.table.table_name,
            "PARTITION_TABLE_NAME": self._asset_sync_partition_table.table.table_name,
            "ERROR_TABLE_NAME": self._asset_sync_error_table.table.table_name,
            "RESULTS_BUCKET_NAME": self.results_bucket.bucket_name,
            "SCANNER_QUEUE_URL": self.scanner_queue.queue_url,
            "QUERY_QUEUE_URL": self.query_queue.queue_url,
            "PROCESSING_QUEUE_URL": self.processing_queue.queue_url,
            "DLQ_URL": self.dlq.queue_url,
            "STATUS_TOPIC_ARN": self.status_topic.topic_arn,
        }

    def _setup_event_sources(self) -> None:
        """Set up event sources for Lambda functions"""
        # SQS Event Sources
        self._scanner_lambda.function.add_event_source(
            lambda_events.SqsEventSource(
                self.scanner_queue,
                batch_size=10,
                max_batching_window=Duration.seconds(0),  # Process immediately
                report_batch_item_failures=True,
            )
        )

        self._query_lambda.function.add_event_source(
            lambda_events.SqsEventSource(
                self.query_queue,
                batch_size=10,
                max_batching_window=Duration.seconds(0),  # Process immediately
                report_batch_item_failures=True,
            )
        )

        self._processor_lambda.function.add_event_source(
            lambda_events.SqsEventSource(
                self.processing_queue,
                batch_size=10,
                max_batching_window=Duration.seconds(0),  # Process immediately
                report_batch_item_failures=True,
            )
        )

        self._dlq_processor_lambda.function.add_event_source(
            lambda_events.SqsEventSource(
                self.dlq,
                batch_size=10,
                max_batching_window=Duration.seconds(30),  # Allow batching for DLQ
                report_batch_item_failures=True,
            )
        )

        # SNS Subscription for aggregator
        self.status_topic.add_subscription(
            sns_subs.LambdaSubscription(self._aggregator_lambda.function)
        )

        # Schedule for aggregator to run periodically
        # Using CloudWatch Events Rule
        aggregator_rule = events.Rule(
            self, "AggregatorRule", schedule=events.Schedule.rate(Duration.minutes(1))
        )
        aggregator_rule.add_target(
            events_targets.LambdaFunction(self._aggregator_lambda.function)
        )

    def _grant_permissions(self) -> None:
        """Grant necessary permissions to Lambda functions"""
        # Job Table permissions
        self._asset_sync_job_table.table.grant_read_write_data(
            self._initialize_job_lambda.function
        )
        self._asset_sync_job_table.table.grant_read_write_data(
            self._scanner_lambda.function
        )
        self._asset_sync_job_table.table.grant_read_write_data(
            self._query_lambda.function
        )
        self._asset_sync_job_table.table.grant_read_write_data(
            self._batch_processor_lambda.function
        )
        self._asset_sync_job_table.table.grant_read_write_data(
            self._worker_lambda.function
        )
        self._asset_sync_job_table.table.grant_read_data(
            self._job_status_lambda.function
        )

        # Partition Table permissions
        self._asset_sync_partition_table.table.grant_read_write_data(
            self._partition_discovery_lambda.function
        )
        self._asset_sync_partition_table.table.grant_read_write_data(
            self._scanner_lambda.function
        )
        self._asset_sync_partition_table.table.grant_read_write_data(
            self._query_lambda.function
        )
        self._asset_sync_partition_table.table.grant_read_write_data(
            self._processor_lambda.function
        )
        self._asset_sync_partition_table.table.grant_read_write_data(
            self._aggregator_lambda.function
        )

        # Error Table permissions
        self._asset_sync_error_table.table.grant_read_write_data(
            self._partition_discovery_lambda.function
        )
        self._asset_sync_error_table.table.grant_read_write_data(
            self._scanner_lambda.function
        )
        self._asset_sync_error_table.table.grant_read_write_data(
            self._query_lambda.function
        )
        self._asset_sync_error_table.table.grant_read_write_data(
            self._processor_lambda.function
        )
        self._asset_sync_error_table.table.grant_read_write_data(
            self._dlq_processor_lambda.function
        )
        self._asset_sync_error_table.table.grant_read_data(
            self._job_status_lambda.function
        )

        # Results Bucket permissions
        self.results_bucket.grant_read_write(self._partition_discovery_lambda.function)
        self.results_bucket.grant_read_write(self._scanner_lambda.function)
        self.results_bucket.grant_read_write(self._query_lambda.function)
        self.results_bucket.grant_read_write(self._processor_lambda.function)

        # Queue permissions
        self.scanner_queue.grant_send_messages(
            self._partition_discovery_lambda.function
        )
        self.query_queue.grant_send_messages(self._scanner_lambda.function)
        self.processing_queue.grant_send_messages(self._query_lambda.function)

        # SNS permissions
        self.status_topic.grant_publish(self._partition_discovery_lambda.function)
        self.status_topic.grant_publish(self._scanner_lambda.function)
        self.status_topic.grant_publish(self._query_lambda.function)
        self.status_topic.grant_publish(self._processor_lambda.function)
        self.status_topic.grant_publish(self._dlq_processor_lambda.function)

        # S3 cross-region permissions
        self._partition_discovery_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=["s3:ListBucket", "s3:GetBucketLocation", "s3:GetObject"],
                resources=["*"],
            )
        )

        self._scanner_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=["s3:ListBucket", "s3:GetObject", "s3:GetObjectTagging"],
                resources=["*"],
            )
        )

        self._processor_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "s3:GetObject",
                    "s3:GetObjectTagging",
                    "s3:PutObjectTagging",
                    "s3:PutObject",
                    "s3:CopyObject",
                ],
                resources=["*"],
            )
        )

    def _create_results_bucket(self) -> s3.Bucket:
        """Create S3 bucket for intermediate results"""
        return s3.Bucket(
            self,
            "ResultsBucket",
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            lifecycle_rules=[
                s3.LifecycleRule(expiration=Duration.days(7), prefix="job-results/")
            ],
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            enforce_ssl=True,
        )

    @property
    def asset_sync_job_table(self) -> dynamodb.TableV2:
        return self._asset_sync_job_table.table

    @property
    def asset_sync_state_machine(self) -> sfn.StateMachine:
        return self.state_machine