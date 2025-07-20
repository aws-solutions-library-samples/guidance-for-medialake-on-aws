from dataclasses import dataclass

import aws_cdk as cdk
from aws_cdk import CfnOutput, Duration, RemovalPolicy
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_events as events
from aws_cdk import aws_events_targets as events_targets
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_lambda_event_sources as lambda_event_sources
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_sqs as sqs
from constructs import Construct

from config import config
from constants import DynamoDB as DynamoDBConstants
from constants import DynamoDBPermissions, EnvVars
from medialake_constructs.shared_constructs.dynamodb import (
    DynamoDB as DynamoDBConstruct,
)
from medialake_constructs.shared_constructs.dynamodb import (
    DynamoDBProps,
)
from medialake_constructs.shared_constructs.lambda_base import Lambda, LambdaConfig


@dataclass
class AssetSyncStackProps:
    asset_table: dynamodb.TableV2
    pipelines_event_bus: events.EventBus


class AssetSyncStack(cdk.NestedStack):
    def __init__(
        self, scope: Construct, construct_id: str, props: AssetSyncStackProps, **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Create DynamoDB tables - reusing existing constructs
        self._asset_sync_job_table = DynamoDBConstruct(
            self,
            "AssetSyncJobTable",
            props=DynamoDBProps(
                name=DynamoDBConstants.asset_sync_job_table_name(),
                partition_key_name="jobId",
                partition_key_type=dynamodb.AttributeType.STRING,
            ),
        )

        # self._asset_sync_chunk_table = DynamoDBConstruct(
        #     self,
        #     "AssetSyncChunkTable",
        #     props=DynamoDBProps(
        #         name=DynamoDBConstants.asset_sync_chunk_table_name(),
        #         partition_key_name="jobId",
        #         partition_key_type=dynamodb.AttributeType.STRING,
        #         sort_key_name="chunkId",
        #         sort_key_type=dynamodb.AttributeType.STRING,
        #     ),
        # )

        self._asset_sync_error_table = DynamoDBConstruct(
            self,
            "AssetSyncErrorTable",
            props=DynamoDBProps(
                name=DynamoDBConstants.asset_sync_error_table_name(),
                partition_key_name="errorId",
                partition_key_type=dynamodb.AttributeType.STRING,
            ),
        )

        # Create S3 bucket for manifests and results
        self.results_bucket = self._create_results_bucket()

        # SQS Queues
        # queues = self._create_queues()
        # self.processor_queue = queues["processor_queue"]
        # self.dlq = queues["dlq"]

        # SNS topic for status notifications
        # self.status_topic = self._create_status_topic()

        # Create IAM role for S3 batch operations
        self.batch_operations_role = iam.Role(
            self,
            "AssetSyncBatchOperationsRole",
            assumed_by=iam.ServicePrincipal("batchoperations.s3.amazonaws.com"),
        )

        # Add S3 Full Access managed policy
        self.batch_operations_role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name("AmazonS3FullAccess")
        )

        # Grant necessary permissions to the batch operations role
        self.batch_operations_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "s3:GetObject",
                    "s3:PutObject",
                    "s3:GetObjectTagging",
                    "s3:PutObjectTagging",
                    "s3:GetBucketLocation",
                    "s3:PutObject",
                    "s3:PutInventoryConfiguration",
                    "s3:GetInventory",
                    "s3:GetInventoryConfiguration",
                    "s3:GetBucketInventory",
                    "s3:PutJobTagging",
                    "s3:GetJobTagging",
                    "s3:GetJob",
                    "s3:GetJobStatus",
                    "s3:GetJobOutput",
                    "s3:GetJobOutputLocation",
                ],
                resources=["*"],
            )
        )

        # Lambda invocation permissions for batch operations
        self.batch_operations_role.add_to_policy(
            iam.PolicyStatement(
                actions=["lambda:InvokeFunction"],
                resources=["*"],
            )
        )

        # Common environment variables
        common_env = {
            "POWERTOOLS_SERVICE_NAME": "asset-sync",
            "POWERTOOLS_METRICS_NAMESPACE": "MediaLake/AssetSync",
            "LOG_LEVEL": "INFO",
            # "STATUS_TOPIC_ARN": self.status_topic.topic_arn,
        }

        # Engine-specific environment variables
        engine_env = {
            **common_env,
            EnvVars.JOB_TABLE_NAME: self._asset_sync_job_table.table.table_name,
            EnvVars.ERROR_TABLE_NAME: self._asset_sync_error_table.table.table_name,
            # EnvVars.PROCESSOR_QUEUE_URL: self.processor_queue.queue_url,
            EnvVars.RESULTS_BUCKET_NAME: self.results_bucket.bucket_name,
            EnvVars.BATCH_OPERATIONS_ROLE_ARN: self.batch_operations_role.role_arn,
            EnvVars.CONNECTOR_TABLE_NAME: DynamoDBConstants.connector_table_name(),
        }

        # Processor-specific environment variables
        processor_env = {
            **common_env,
            "ASSETS_TABLE_NAME": props.asset_table.table_name,
            EnvVars.JOB_TABLE_NAME: self._asset_sync_job_table.table.table_name,
        }

        # Create the Asset Sync Engine Lambda
        self._asset_sync_engine_lambda = Lambda(
            self,
            "AssetSyncEngineLambda",
            LambdaConfig(
                name="asset-sync-engine",
                entry="lambdas/back_end/asset_sync/engine",
                memory_size=10240,
                timeout_minutes=15,
                environment_variables=engine_env,
            ),
        )

        ## Create the Asset Sync Processor Lambda
        self._asset_sync_processor_lambda = Lambda(
            self,
            "AssetSyncProcessorLambda",
            LambdaConfig(
                name="asset-sync-processor",
                entry="lambdas/back_end/asset_sync/processor",
                memory_size=10240,
                timeout_minutes=15,
                environment_variables=processor_env,
            ),
        )

        # Job event processor-specific environment variables
        job_event_processor_env = {
            **common_env,
            EnvVars.JOB_TABLE_NAME: self._asset_sync_job_table.table.table_name,
        }

        # Create the Asset Sync Job Event Processor Lambda
        self._asset_sync_job_event_processor_lambda = Lambda(
            self,
            "AssetSyncJobEventProcessorLambda",
            LambdaConfig(
                name="asset-sync-job-event-processor",
                entry="lambdas/back_end/asset_sync/job_event_processor",
                memory_size=1024,
                timeout_minutes=15,
                environment_variables=job_event_processor_env,
            ),
        )

        # Update the engine with the processor ARN
        self._asset_sync_engine_lambda.function.add_environment(
            EnvVars.PROCESSOR_FUNCTION_ARN,
            self._asset_sync_processor_lambda.function.function_arn,
        )

        # Add SQS event source to processor lambda
        # self._asset_sync_processor_lambda.function.add_event_source(
        #     lambda_event_sources.SqsEventSource(
        #         self.processor_queue,
        #         batch_size=10,
        #         max_batching_window=Duration.seconds(30),
        #         report_batch_item_failures=True,
        #     )
        # )

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

        # Add S3 inventory configuration permission to batch operations role
        # Using "*" for resources because asset sync needs permission to set inventory configuration
        # on the source bucket, which can be any S3 bucket that users want to sync from
        self.batch_operations_role.add_to_policy(
            iam.PolicyStatement(
                actions=["s3:PutInventoryConfiguration"],
                resources=["*"],
                effect=iam.Effect.ALLOW,
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

        # CfnOutput(
        #     self,
        #     "AssetSyncProcessorQueueUrl",
        #     value=self.processor_queue.queue_url,
        #     description="Asset Sync Processor Queue URL",
        # )

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

    def _setup_event_sources(self) -> None:
        """Set up event sources for Lambda functions"""
        # Create SQS queue for S3 job events
        self.asset_sync_events_queue = sqs.Queue(
            self,
            "AssetSyncSQSQueue",
            queue_name="AssetSyncSQSQueue",
            visibility_timeout=Duration.minutes(15),
            encryption=sqs.QueueEncryption.SQS_MANAGED,
            dead_letter_queue=sqs.DeadLetterQueue(
                max_receive_count=3,
                queue=sqs.Queue(
                    self,
                    "AssetSyncEventsDLQ",
                    retention_period=Duration.days(14),
                    encryption=sqs.QueueEncryption.SQS_MANAGED,
                ),
            ),
        )

        # Create EventBridge rule on default event bus for S3 CloudTrail events
        s3_job_events_rule = events.Rule(
            self,
            "S3JobEventsRule",
            event_bus=events.EventBus.from_event_bus_name(
                self, "DefaultEventBus", "default"
            ),
            event_pattern=events.EventPattern(
                source=["aws.s3"],
                detail_type=["AWS Service Event via CloudTrail"],
                detail={
                    "eventSource": ["s3.amazonaws.com"],
                    "eventName": ["JobCreated", "JobStatusChanged"],
                },
            ),
        )

        # Send S3 job events to SQS queue
        s3_job_events_rule.add_target(
            events_targets.SqsQueue(
                self.asset_sync_events_queue,
                message=events.RuleTargetInput.from_object(
                    {
                        "source": events.RuleTargetInput.from_event_path("$.source"),
                        "detail-type": events.RuleTargetInput.from_event_path(
                            "$.detail-type"
                        ),
                        "detail": events.RuleTargetInput.from_event_path("$.detail"),
                        "time": events.RuleTargetInput.from_event_path("$.time"),
                        "region": events.RuleTargetInput.from_event_path("$.region"),
                        "account": events.RuleTargetInput.from_event_path("$.account"),
                    }
                ),
            )
        )

        # Add SQS event source to job event processor lambda
        self._asset_sync_job_event_processor_lambda.function.add_event_source(
            lambda_event_sources.SqsEventSource(
                self.asset_sync_events_queue,
                batch_size=10,
                max_batching_window=Duration.seconds(30),
                report_batch_item_failures=True,
            )
        )

    def _grant_permissions(self, props: AssetSyncStackProps) -> None:
        """Grant necessary permissions to Lambda functions"""
        # Job table permissions

        self._asset_sync_job_table.table.grant_read_write_data(
            self._asset_sync_engine_lambda.function
        )
        self._asset_sync_job_table.table.grant_read_write_data(
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

        # Asset table permissions
        props.asset_table.grant_read_data(self._asset_sync_engine_lambda.function)
        props.asset_table.grant_read_write_data(
            self._asset_sync_processor_lambda.function
        )

        # Connector table permissions - using table ARN from constants
        # This grants the Asset Sync Engine Lambda read-only access to the Connector table
        # without creating a circular dependency between stacks. The table name is resolved
        # using shared constants, ensuring consistency across all stacks.
        self._asset_sync_engine_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=DynamoDBPermissions.READ_ONLY,
                resources=[
                    DynamoDBConstants.connector_table_arn(self.region, self.account)
                ],
            )
        )

        # Pipelines event bus permissions
        props.pipelines_event_bus.grant_put_events_to(
            self._asset_sync_processor_lambda.function
        )

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
                    "s3:GetBucketInventoryConfiguration",
                    "s3:GetBucketInventory",
                    "s3:PutJobTagging",
                    "s3:GetJobTagging",
                    "s3:GetJob",
                    "s3:GetJobStatus",
                    "s3:GetJobOutput",
                    "s3:GetJobOutputLocation",
                    "s3:GetJobReport",
                    "s3:GetJobReportLocation",
                    "s3:GetJobReportStatus",
                    "s3:GetJobReportOutput",
                    "s3:GetJobReportOutputLocation",
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

        # Add SQS permissions for engine to send messages to connector queues only
        self._asset_sync_engine_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "sqs:SendMessage",
                    "sqs:GetQueueAttributes",
                    "sqs:GetQueueUrl",
                ],
                resources=[f"arn:aws:sqs:*:*:{config.resource_prefix}_connector_*"],
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
                    "s3:ListBucket",
                    "s3:PutJobTagging",
                ],
                resources=["*"],
            )
        )

        # Add KMS permissions for processor to access SSE-KMS encrypted S3 buckets
        self._asset_sync_processor_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "kms:Decrypt",
                    "kms:DescribeKey",
                    "kms:GenerateDataKey",
                ],
                resources=["*"],
            )
        )

        # Add SQS permissions for processor to send messages to any queue
        self._asset_sync_processor_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "sqs:SendMessage",
                    "sqs:GetQueueAttributes",
                    "sqs:GetQueueUrl",
                ],
                resources=["*"],
            )
        )

        # Job table permissions for job event processor
        self._asset_sync_job_table.table.grant_read_write_data(
            self._asset_sync_job_event_processor_lambda.function
        )

        # SQS queue permissions for job event processor
        self.asset_sync_events_queue.grant_consume_messages(
            self._asset_sync_job_event_processor_lambda.function
        )

    def _create_results_bucket(self) -> s3.Bucket:
        """Create S3 bucket for manifests and results"""
        self._results_bucket = s3.Bucket(
            self,
            "ResultsBucket",
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            lifecycle_rules=[
                s3.LifecycleRule(expiration=Duration.days(7), prefix="job-results/"),
                s3.LifecycleRule(expiration=Duration.days(7), prefix="job-manifests/"),
                s3.LifecycleRule(expiration=Duration.days(7), prefix="job-chunks/"),
                s3.LifecycleRule(expiration=Duration.days(30), prefix="job-reports/"),
            ],
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            enforce_ssl=True,
        )
        return self._results_bucket

    @property
    def asset_sync_job_table(self) -> dynamodb.TableV2:
        return self._asset_sync_job_table.table

    # @property
    # def asset_sync_chunk_table(self) -> dynamodb.TableV2:
    #     return self._asset_sync_chunk_table.table
    @property
    def asset_sync_error_table(self) -> dynamodb.TableV2:
        return self._asset_sync_error_table.table

    @property
    def asset_sync_engine_lambda(self) -> lambda_.Function:
        return self._asset_sync_engine_lambda.function

    @property
    def asset_sync_processor_lambda(self) -> lambda_.Function:
        return self._asset_sync_processor_lambda.function

    @property
    def asset_sync_job_event_processor_lambda(self) -> lambda_.Function:
        return self._asset_sync_job_event_processor_lambda.function
