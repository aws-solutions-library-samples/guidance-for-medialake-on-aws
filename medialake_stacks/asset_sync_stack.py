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
    aws_stepfunctions as sfn,
    aws_iam as iam,
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

        # Create DynamoDB tables - reusing existing constructs
        self._asset_sync_job_table = DynamoDB(
            self,
            "AssetSyncJobTable",
            props=DynamoDBProps(
                name="AssetSyncJobTable",
                partition_key_name="jobId",
                partition_key_type=dynamodb.AttributeType.STRING,
            ),
        )

        self._asset_sync_chunk_table = DynamoDB(
            self,
            "AssetSyncChunkTable",
            props=DynamoDBProps(
                name=f"{config.resource_prefix}-asset-sync-chunk-table",
                partition_key_name="jobId",
                partition_key_type=dynamodb.AttributeType.STRING,
                sort_key_name="chunkId",
                sort_key_type=dynamodb.AttributeType.STRING,
            ),
        )

        self._asset_sync_error_table = DynamoDB(
            self,
            "AssetSyncErrorTable",
            props=DynamoDBProps(
                name=f"{config.resource_prefix}-asset-sync-error-table",
                partition_key_name="errorId",
                partition_key_type=dynamodb.AttributeType.STRING,
            ),
        )

        # Create S3 bucket for manifests and results
        self.results_bucket = self._create_results_bucket()

        # SQS Queues
        queues = self._create_queues()
        self.processor_queue = queues["processor_queue"]
        self.dlq = queues["dlq"]
        
        # SNS topic for status notifications
        self.status_topic = self._create_status_topic()

        # Create IAM role for S3 batch operations
        self.batch_operations_role = iam.Role(
            self,
            "AssetSyncBatchOperationsRole",
            assumed_by=iam.ServicePrincipal("batchoperations.s3.amazonaws.com"),
        )
        
        # Grant necessary permissions to the batch operations role
        self.batch_operations_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "s3:GetObject",
                    "s3:GetObjectTagging",
                    "s3:PutObjectTagging",
                    "s3:PutObjectVersionTagging",
                    "s3:GetBucketLocation",
                    "s3:PutObject",
                ],
                resources=["*"],  # Should be restricted in production
            )
        )
        
        # Lambda invocation permissions for batch operations
        self.batch_operations_role.add_to_policy(
            iam.PolicyStatement(
                actions=["lambda:InvokeFunction"],
                resources=["*"],
            )
        )

        # Common Lambda environment variables
        asset_sync_lambda_env = {
            "ASSETS_TABLE_NAME": props.asset_table.table_name,
            "JOB_TABLE_NAME": self._asset_sync_job_table.table.table_name,
            "CHUNK_TABLE_NAME": self._asset_sync_chunk_table.table.table_name,
            "ERROR_TABLE_NAME": self._asset_sync_error_table.table.table_name,
            "PROCESSOR_QUEUE_URL": self.processor_queue.queue_url,
            "DLQ_URL": self.dlq.queue_url,
            "INGEST_EVENT_BUS_NAME": props.ingest_event_bus.event_bus_name,
            "STATUS_TOPIC_ARN": self.status_topic.topic_arn,
            "POWERTOOLS_SERVICE_NAME": "asset-management",
            "POWERTOOLS_METRICS_NAMESPACE": "AssetManagement",
            "LOG_LEVEL": "INFO",
            "RESULTS_BUCKET_NAME": self.results_bucket.bucket_name,
            "BATCH_OPERATIONS_ROLE_ARN": self.batch_operations_role.role_arn,
        }

        # Create Lambda functions using existing construct
        self._storage_sync_post_lambda = Lambda(
            self,
            "StorageSyncPostLambda",
            LambdaConfig(
                name="storage-sync-post",
                entry="lambdas/api/storage/s3/sync/post_sync",
                memory_size=1024,
                timeout_minutes=15,
                environment_variables=asset_sync_lambda_env,
            ),
        )

        # Create the Asset Sync Engine Lambda
        self._asset_sync_engine_lambda = Lambda(
            self,
            "AssetSyncEngineLambda",
            LambdaConfig(
                name="asset-sync-engine",
                entry="lambdas/back_end/asset_sync/engine",
                memory_size=10240,
                timeout_minutes=15,
                environment_variables=asset_sync_lambda_env,
            ),
        )

        # Create the Asset Sync Processor Lambda
        self._asset_sync_processor_lambda = Lambda(
            self,
            "AssetSyncProcessorLambda",
            LambdaConfig(
                name="asset-sync-processor",
                entry="lambdas/back_end/asset_sync/processor",
                memory_size=10240,
                timeout_minutes=15,
                environment_variables={
                    **asset_sync_lambda_env,
                    "PROCESSOR_FUNCTION_ARN": "",  # Will update after creation
                },
            ),
        )

        # Update the engine with the processor ARN
        self._asset_sync_engine_lambda.function.add_environment(
            "PROCESSOR_FUNCTION_ARN", 
            self._asset_sync_processor_lambda.function.function_arn
        )

        # Add SQS event source to processor lambda
        self._asset_sync_processor_lambda.function.add_event_source(
            lambda_event_sources.SqsEventSource(
                self.processor_queue,
                batch_size=10,
                max_batching_window=Duration.seconds(30),
                report_batch_item_failures=True,
            )
        )
        
        # Add permission for S3 batch operations to invoke processor
        self._asset_sync_processor_lambda.function.add_permission(
            "AllowS3BatchOperations",
            principal=iam.ServicePrincipal("batchoperations.s3.amazonaws.com"),
            action="lambda:InvokeFunction",
        )

        # Update batch operations role with specific Lambda ARN
        self.batch_operations_role.add_to_policy(
            iam.PolicyStatement(
                actions=["lambda:InvokeFunction"],
                resources=[self._asset_sync_processor_lambda.function.function_arn],
            )
        )

        # Setup event source for starting sync jobs
        self._setup_event_sources()

        # Grant necessary permissions
        self._grant_permissions(props)

        # Outputs
        CfnOutput(
            self,
            "AssetSyncJobTableName",
            value=self._asset_sync_job_table.table.table_name,
            description="Asset Sync Job Table",
        )
        
        CfnOutput(
            self,
            "AssetSyncResultsBucketName",
            value=self.results_bucket.bucket_name,
            description="Asset Sync Results Bucket",
        )
        
        CfnOutput(
            self,
            "AssetSyncProcessorQueueUrl",
            value=self.processor_queue.queue_url,
            description="Asset Sync Processor Queue URL",
        )
        
        CfnOutput(
            self,
            "AssetSyncEngineLambdaArn",
            value=self._asset_sync_engine_lambda.function.function_arn,
            description="Asset Sync Engine Lambda ARN",
        )
        
        CfnOutput(
            self,
            "AssetSyncProcessorLambdaArn",
            value=self._asset_sync_processor_lambda.function.function_arn,
            description="Asset Sync Processor Lambda ARN",
        )

    def _create_status_topic(self) -> sns.Topic:
        return sns.Topic(
            self,
            "AssetSyncStatusTopic",
            topic_name=f"{config.resource_prefix}-asset-sync-status-topic",
        )

    def _create_queues(self) -> Dict[str, sqs.Queue]:
        """Create SQS queues for processing"""
        # Dead Letter Queue
        dlq = sqs.Queue(
            self,
            "AssetSyncDLQ",
            retention_period=Duration.days(14),
            encryption=sqs.QueueEncryption.SQS_MANAGED,
            visibility_timeout=Duration.minutes(15),
        )

        # Processor Queue - High throughput
        processor_queue = sqs.Queue(
            self,
            "ProcessorQueue",
            visibility_timeout=Duration.minutes(15),
            encryption=sqs.QueueEncryption.SQS_MANAGED,
            dead_letter_queue=sqs.DeadLetterQueue(max_receive_count=3, queue=dlq),
        )

        return {
            "processor_queue": processor_queue,
            "dlq": dlq,
        }

    def _setup_event_sources(self) -> None:
        """Set up event sources for Lambda functions"""
        # Create EventBridge rule to detect S3 batch job completion
        batch_job_complete_rule = events.Rule(
            self,
            "BatchJobCompleteRule",
            event_pattern=events.EventPattern(
                source=["aws.s3"],
                detail_type=["S3 Batch Operations Job State Change"],
                detail={
                    "status": ["Complete", "Failed", "Cancelled"],
                },
            ),
        )
        
        batch_job_complete_rule.add_target(
            events_targets.LambdaFunction(self._asset_sync_engine_lambda.function)
        )

        # Create scheduled rule to check for stuck jobs
        stuck_jobs_rule = events.Rule(
            self,
            "StuckJobsCheckRule",
            schedule=events.Schedule.rate(Duration.minutes(5)),
        )
        
        stuck_jobs_rule.add_target(
            events_targets.LambdaFunction(
                self._asset_sync_engine_lambda.function,
                event=events.RuleTargetInput.from_object({"CHECK_STUCK_JOBS": True})
            )
        )

    def _grant_permissions(self, props: AssetSyncStackProps) -> None:
        """Grant necessary permissions to Lambda functions"""
        # Job table permissions
        self._asset_sync_job_table.table.grant_read_write_data(
            self._storage_sync_post_lambda.function
        )
        self._asset_sync_job_table.table.grant_read_write_data(
            self._asset_sync_engine_lambda.function
        )
        self._asset_sync_job_table.table.grant_read_write_data(
            self._asset_sync_processor_lambda.function
        )

        # Chunk table permissions
        self._asset_sync_chunk_table.table.grant_read_write_data(
            self._asset_sync_engine_lambda.function
        )
        self._asset_sync_chunk_table.table.grant_read_write_data(
            self._asset_sync_processor_lambda.function
        )

        # Error table permissions
        self._asset_sync_error_table.table.grant_read_write_data(
            self._asset_sync_engine_lambda.function
        )
        self._asset_sync_error_table.table.grant_read_write_data(
            self._asset_sync_processor_lambda.function
        )

        # Results bucket permissions
        self.results_bucket.grant_read_write(self._asset_sync_engine_lambda.function)
        self.results_bucket.grant_read_write(self._asset_sync_processor_lambda.function)

        # Queue permissions
        self.processor_queue.grant_send_messages(self._asset_sync_engine_lambda.function)
        self.processor_queue.grant_consume_messages(self._asset_sync_processor_lambda.function)

        # SNS permissions
        self.status_topic.grant_publish(self._asset_sync_engine_lambda.function)
        self.status_topic.grant_publish(self._asset_sync_processor_lambda.function)

        # Asset table permissions
        props.asset_table.grant_read_data(self._asset_sync_engine_lambda.function)
        props.asset_table.grant_read_write_data(self._asset_sync_processor_lambda.function)

        # Ingest event bus permissions
        props.ingest_event_bus.grant_put_events_to(self._asset_sync_processor_lambda.function)

        # S3 cross-region permissions for engine
        self._asset_sync_engine_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "s3:ListBucket",
                    "s3:GetObject",
                    "s3:GetObjectTagging",
                    "s3:PutObject",
                    "s3:PutBucketInventoryConfiguration",
                    "s3:GetBucketLocation",
                ],
                resources=["*"],
            )
        )

        # Add S3 control permissions for batch operations
        self._asset_sync_engine_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "s3control:CreateJob",
                    "s3control:DescribeJob",
                    "s3control:UpdateJobPriority",
                    "s3control:UpdateJobStatus",
                    "s3:CreateJob",
                    "s3:GetBucketLocation",
                    "s3:UpdateJobStatus",
                    "s3control:ListJobs",
                    "s3control:GetJobTagging",
                    "s3control:PutJobTagging",
                    "s3control:GetJob",
                    "s3control:GetJobStatus",
                    "s3control:GetJobOutput",
                    "s3control:GetJobOutputLocation",
                    "s3control:GetJobProgress",
                    "s3control:GetJobReport",
                    "s3control:GetJobReportLocation",
                    "s3control:GetJobReportStatus",
                    "s3control:GetJobReportOutput",
                    "s3control:GetJobReportOutputLocation",
                    
                ],
                resources=["*"],
            )
        )

        # Add STS permission to get caller identity
        self._asset_sync_engine_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=["sts:GetCallerIdentity"],
                resources=["*"],
            )
        )

        # Add IAM PassRole permission for batch operations
        self._asset_sync_engine_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=["iam:PassRole"],
                resources=[self.batch_operations_role.role_arn],
            )
        )

        # S3 permissions for processor
        self._asset_sync_processor_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "s3:GetObject",
                    "s3:GetObjectTagging",
                    "s3:PutObjectTagging",
                    "s3:PutObject",
                    "s3:CopyObject",
                    "s3:GetBucketLocation",
                ],
                resources=["*"],
            )
        )

    def _create_results_bucket(self) -> s3.Bucket:
        """Create S3 bucket for manifests and results"""
        self._results_bucket = s3.Bucket(
            self,
            "ResultsBucket",
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            lifecycle_rules=[
                s3.LifecycleRule(
                    expiration=Duration.days(7),
                    prefix="job-results/"
                ),
                s3.LifecycleRule(
                    expiration=Duration.days(7),
                    prefix="job-manifests/"
                ),
                s3.LifecycleRule(
                    expiration=Duration.days(7),
                    prefix="job-chunks/"
                ),
                s3.LifecycleRule(
                    expiration=Duration.days(30),
                    prefix="job-reports/"
                ),
            ],
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            enforce_ssl=True,
        )
        return self._results_bucket

    @property
    def asset_sync_job_table(self) -> dynamodb.TableV2:
        return self._asset_sync_job_table.table
    @property
    def asset_sync_chunk_table(self) -> dynamodb.TableV2:
        return self._asset_sync_chunk_table.table
    @property
    def asset_sync_error_table(self) -> dynamodb.TableV2:
        return self._asset_sync_error_table.table
    # @property
    # def results_bucket(self) -> s3.Bucket:
    #     return self._results_bucket
    @property
    def asset_sync_engine_lambda(self) -> lambda_.Function:
        return self._asset_sync_engine_lambda.function
    @property
    def asset_sync_processor_lambda(self) -> lambda_.Function:
        return self._asset_sync_processor_lambda.function
    @property
    def storage_sync_post_lambda(self) -> lambda_.Function:
        return self._storage_sync_post_lambda.function
    