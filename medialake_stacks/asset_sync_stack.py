from dataclasses import dataclass
from typing import Any

from aws_cdk import (
    Duration,
    Stack,
    CfnOutput,
    aws_dynamodb as dynamodb,
    aws_lambda as lambda_,
    aws_lambda_event_sources as lambda_event_sources,
    aws_logs as logs,
    aws_sqs as sqs,
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
    api_resource: apigateway.IResource
    x_origin_verify_secret: secretsmanager.Secret
    cognito_authorizer: apigateway.IAuthorizer



class AssetSyncStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, props: AssetSyncStackProps, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)


        self.asset_sync_job_table = DynamoDB(
            self,
            "AssetSyncJobTable",
            props=DynamoDBProps(
                name="AssetSyncJobTable",
                partition_key_name="jobId",
                partition_key_type=dynamodb.AttributeType.STRING,
            )
        )
        
        storage_resource = props.api_resource.root.add_resource("storage")
        sync_resource = storage_resource.add_resource("sync")
        job_resource = sync_resource.add_resource("{jobId}")


        # SQS Queues
        self.dlq = sqs.Queue(
            self,
            "AssetSyncDLQ",
            retention_period=Duration.days(14),
            encryption=sqs.QueueEncryption.SQS_MANAGED,
        )

        self.processing_queue = sqs.Queue(
            self,
            "AssetSyncProcessingQueue",
            visibility_timeout=Duration.minutes(15),
            dead_letter_queue=sqs.DeadLetterQueue(
                max_receive_count=3,
                queue=self.dlq
            ),
            encryption=sqs.QueueEncryption.SQS_MANAGED,
        )

        # CloudWatch Log Group for centralized logging
        self.log_group = logs.LogGroup(
            self,
            "AssetSyncLogGroup",
            retention=logs.RetentionDays.TWO_WEEKS,
            removal_policy=RemovalPolicy.DESTROY
        )


        # Lambda Layer for shared code
        shared_layer = lambda_.LayerVersion(
            self,
            "SharedLayer",
            code=lambda_.Code.from_asset("lambdas/layers/asset_sync_shared"),
            compatible_runtimes=[lambda_.Runtime.PYTHON_3_9],
            description="Shared utility functions for asset management",
        )

        # Common Lambda configuration
        asset_sync_lambda_env = {
            "ASSETS_TABLE_NAME": props.asset_table.table_name,
            "JOB_TABLE_NAME": self.asset_sync_job_table.table_name,
            "LOG_GROUP_NAME": self.log_group.log_group_name,
            "PROCESSING_QUEUE_URL": self.processing_queue.queue_url,
            "DLQ_URL": self.dlq.queue_url,
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
            ),
        )

        self._query_lambda = Lambda(
            self,
            "QueryLambda",
            LambdaConfig(
                name=f"{config.resource_prefix}-query-{config.environment}",
                entry="lambdas/back_end/asset_sync/query",
                environment_variables=asset_sync_lambda_env,
            ),
        )

        self._batch_processor_lambda = Lambda(
            self,
            "BatchProcessorLambda",
            LambdaConfig(
                name=f"{config.resource_prefix}-batch-processor-{config.environment}",
                entry="lambdas/back_end/asset_sync/batch_processor",
                environment_variables=asset_sync_lambda_env,
            ),
        )
        
        self._worker_lambda = Lambda(
            self,
            "WorkerLambda",
            LambdaConfig(
                name=f"{config.resource_prefix}-worker-{config.environment}",
                entry="lambdas/back_end/asset_sync/worker",
                environment_variables=asset_sync_lambda_env,
            ),
        )
        
        self._job_status_lambda = Lambda(
            self,
            "JobStatusLambda",
            LambdaConfig(
                name=f"{config.resource_prefix}-job-status-{config.environment}",
                entry="lambdas/back_end/asset_sync/job_status",
                environment_variables=asset_sync_lambda_env,
            ),
        )

        # Add SQS event source to worker lambda
        self._worker_lambda.function.add_event_source(
            lambda_event_sources.SqsEventSource(
                self.processing_queue,
                batch_size=10,
                max_batching_window=Duration.seconds(30),
                report_batch_item_failures=True,  # Enable partial batch failures
            )
        )

        # Grant permissions
        self.asset_sync_job_table.table.grant_read_write_data(self._initialize_job_lambda.function)
        self.asset_sync_job_table.table.grant_read_write_data(self._scanner_lambda.function)
        self.asset_sync_job_table.table.grant_read_write_data(self._query_lambda.function)
        self.asset_sync_job_table.table.grant_read_write_data(self._batch_processor_lambda.function)
        self.asset_sync_job_table.table.grant_read_write_data(self._worker_lambda.function)
        self.asset_sync_job_table.table.grant_read_data(self._job_status_lambda.function)
        
        props.asset_table.grant_read_data(self._query_lambda.function)
        props.asset_table.grant_read_write_data(self._worker_lambda.function)
        
        self.processing_queue.grant_send_messages(self._batch_processor_lambda.function)
        self.processing_queue.grant_consume_messages(self._worker_lambda.function)
        self.dlq.grant_send_messages(self._worker_lambda.function)

        # Add S3 cross-region permissions to scanner lambda
        self._scanner_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=["s3:ListBucket", "s3:GetObject", "s3:GetObjectTagging", "s3:PutObjectTagging"],
                resources=["*"],  # Allow access to any bucket in any region
            )
        )
        
        # Add S3 permissions to worker lambda
        self._worker_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=["s3:GetObject", "s3:GetObjectTagging", "s3:PutObjectTagging", "s3:PutObject"],
                resources=["*"],  # Allow access to any bucket in any region
            )
        )

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
                "bucketName.$": "$.Payload.bucketName"
            }
        )

        scanner_task = sfn_tasks.LambdaInvoke(
            self,
            "ScanS3",
            lambda_function=self._scanner_lambda.function,
            retry_on_service_exceptions=True,
            result_path="$.scanResult",
            payload=sfn.TaskInput.from_object({
                "jobId.$": "$.jobInfo.jobId",
                "bucketName.$": "$.jobInfo.bucketName",
                "batchSize.$": "$.jobInfo.batchSize",
                "continuationToken.$": "$.continuationToken"
            })
        )

        query_task = sfn_tasks.LambdaInvoke(
            self,
            "QueryAssets",
            lambda_function=self._query_lambda.function,
            retry_on_service_exceptions=True,
            result_path="$.queryResult",
            payload=sfn.TaskInput.from_object({
                "jobId.$": "$.jobInfo.jobId",
                "bucketName.$": "$.jobInfo.bucketName",
                "scanResult.$": "$.scanResult.Payload"
            })
        )

        process_batch_task = sfn_tasks.LambdaInvoke(
            self,
            "ProcessBatch",
            lambda_function=self._batch_processor_lambda.function,
            retry_on_service_exceptions=True,
            result_path="$.processResult",
            payload=sfn.TaskInput.from_object({
                "jobId.$": "$.jobInfo.jobId",
                "bucketName.$": "$.jobInfo.bucketName",
                "concurrencyLimit.$": "$.jobInfo.concurrencyLimit",
                "queryResult.$": "$.queryResult.Payload"
            })
        )

        # Check if there's more data to scan
        check_more_data = sfn.Choice(self, "MoreDataToScan")
        
        # Define success and complete states
        job_complete = sfn.Succeed(self, "JobComplete")
        
        # Map state for parallel processing if needed
        continue_scanning = sfn.Pass(
            self,
            "ContinueScanning",
            comment="Continue scanning",
            result=sfn.Result.from_object({
                "continue": True
            })
        )

        # Define the Step Function workflow
        self.state_machine = sfn.StateMachine(
            self,
            "AssetResyncStateMachine",
            definition_body=sfn.DefinitionBody.from_chainable(initialize_job_task.next(
                scanner_task.next(
                    query_task.next(
                        process_batch_task.next(
                            check_more_data
                            .when(
                                sfn.Condition.boolean_equals("$.scanResult.Payload.isTruncated", True), 
                                continue_scanning.next(scanner_task)
                            )
                            .otherwise(job_complete)
                        )
                    )
                )
            )),
            timeout=Duration.hours(24),
            logs=sfn.LogOptions(
                destination=self.log_group,
                level=sfn.LogLevel.ALL,
                include_execution_data=True
            ),
            tracing_enabled=True
        )


        self._storage_sync_post_lambda = Lambda(
            self,
            "StorageSyncPostLambda",
            LambdaConfig(
                name=f"{config.resource_prefix}-storage-sync-post-{config.environment}",
                entry="lambdas/api/storage/s3/sync/post_sync",
                environment_variables={
                    **asset_sync_lambda_env,
                    "STATE_MACHINE_ARN": self.state_machine.state_machine_arn
                },
            ),
        )
        

        
        sync_resource.add_method(
            "POST",
            apigateway.LambdaIntegration(self._storage_sync_post_lambda.function),
            authorization_type=apigateway.AuthorizationType.COGNITO,
            authorizer=props.cognito_authorizer,
        )
        
        job_resource.add_method(
            "GET",
            apigateway.LambdaIntegration(self._job_status_lambda.function),
            authorization_type=apigateway.AuthorizationType.COGNITO,
            authorizer=props.cognito_authorizer,
        )   