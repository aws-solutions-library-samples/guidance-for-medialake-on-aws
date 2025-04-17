import os
import json
import boto3
import uuid
import time
import hashlib
import csv
import io
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Set, Tuple
from concurrent.futures import ThreadPoolExecutor

from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.metrics import MetricUnit

from common import (
    AssetProcessor, JobStatus, ErrorType,
    get_optimized_client, get_optimized_s3_client, MAX_THREADS, MAX_RETRY_ATTEMPTS,
    DecimalEncoder
)

# Initialize powertools
logger = Logger()
tracer = Tracer()
metrics = Metrics()

# Constants
DEFAULT_MAX_PARTITIONS = 1000  # Maximum number of partitions to create
DEFAULT_BATCH_SIZE = 1000      # Default batch size for operations
MAX_MANIFEST_SIZE = 10000000     # Maximum number of objects in a manifest
MAX_CHUNK_SIZE = 1000          # Maximum number of objects in a chunk

class AssetSyncEngine:
    """Handles S3 asset synchronization using batch operations"""
    
    def __init__(self, job_id: str, bucket_name: str, prefix: Optional[str] = None, max_concurrent_tasks: int = 500):
        """
        Initialize the Asset Sync Engine
        
        Args:
            job_id: Unique job identifier
            bucket_name: S3 bucket name to sync
            prefix: Optional prefix within the bucket to limit sync scope
            max_concurrent_tasks: Limit on concurrent batch operations tasks (default: 500)
        """
        self.job_id = job_id
        self.bucket_name = bucket_name
        self.prefix = prefix
        self.max_concurrent_tasks = max_concurrent_tasks
        self.s3_client = get_optimized_s3_client(bucket_name)
        self.results_bucket = os.environ.get('RESULTS_BUCKET_NAME')
        
        if not self.results_bucket:
            raise ValueError("RESULTS_BUCKET_NAME environment variable is not set")
            
    def retry_with_backoff(self, func, *args, max_attempts=MAX_RETRY_ATTEMPTS, initial_backoff=1, **kwargs):
        """
        Execute a function with exponential backoff retry logic
        
        Args:
            func: Function to execute
            *args: Positional arguments for the function
            max_attempts: Maximum number of retry attempts
            initial_backoff: Initial backoff time in seconds
            **kwargs: Keyword arguments for the function
            
        Returns:
            Result of the function call
        
        Raises:
            Exception: If all retry attempts fail
        """
        attempt = 0
        last_exception = None
        
        while attempt < max_attempts:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                attempt += 1
                last_exception = e
                
                if attempt >= max_attempts:
                    logger.error(f"All {max_attempts} retry attempts failed: {str(e)}", exc_info=True)
                    break
                    
                # Calculate backoff with jitter to avoid thundering herd
                backoff = initial_backoff * (2 ** (attempt - 1)) + (attempt * 0.1)
                logger.warning(f"Operation failed (attempt {attempt}/{max_attempts}): {str(e)}. Retrying in {backoff:.2f}s")
                time.sleep(backoff)
        
        # If we get here, all retries failed
        raise last_exception
            
    def create_batch_operations_job(self) -> str:
        """
        Create and start an S3 batch operations job to inventory objects

        Returns:
            S3 batch job ID
        """
        # Update job status
        AssetProcessor.update_job_status(
            self.job_id,
            JobStatus.DISCOVERING,
            f"Creating inventory for bucket {self.bucket_name}"
        )

        # Generate a unique report path
        timestamp = datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')
        manifest_key = f"job-manifests/{self.job_id}/inventory-{timestamp}.csv"

        # Create manifest content
        manifest_content = self._generate_csv_manifest()

        # Upload manifest to S3
        try:
            self.s3_client.put_object(
                Bucket=self.results_bucket,
                Key=manifest_key,
                Body=manifest_content,
                ContentType='text/csv'
            )
            logger.info(f"Uploaded manifest to s3://{self.results_bucket}/{manifest_key}")
        except Exception as e:
            logger.error(f"Error uploading manifest: {str(e)}", exc_info=True)
            raise

        # Create manifest metadata object (required by S3 batch operations)
        etag = self.s3_client.head_object(Bucket=self.results_bucket, Key=manifest_key)['ETag'].strip('"')

        # Create S3 batch operations job
        try:
            s3control = boto3.client('s3control', region_name=boto3.session.Session().region_name)
            account_id = boto3.client('sts').get_caller_identity().get('Account')

            processor_function_arn = os.environ.get('PROCESSOR_FUNCTION_ARN')
            if not processor_function_arn:
                logger.error("PROCESSOR_FUNCTION_ARN environment variable is not set")
                raise ValueError("PROCESSOR_FUNCTION_ARN environment variable is not set")

            batch_operations_role_arn = os.environ.get('BATCH_OPERATIONS_ROLE_ARN')
            if not batch_operations_role_arn:
                logger.error("BATCH_OPERATIONS_ROLE_ARN environment variable is not set")
                raise ValueError("BATCH_OPERATIONS_ROLE_ARN environment variable is not set")

            # UserArguments must be a dictionary of string keys and string values
            user_args = {
                'jobId': self.job_id,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }

            # Log details about the batch operation job creation
            logger.info(f"Creating S3 batch operations job with account ID: {account_id}")
            logger.info(f"Processor Lambda ARN: {processor_function_arn}")
            logger.info(f"Batch Operations Role ARN: {batch_operations_role_arn}")
            logger.info(f"User arguments: {json.dumps(user_args)}")

            # Use the configured max_concurrent_tasks value
            max_concurrent_tasks = self.max_concurrent_tasks
            job_priority = int(os.environ.get('BATCH_JOB_PRIORITY', '50'))
            
            logger.info(f"Configuring batch job with MaximumTasksInParallel={max_concurrent_tasks}, Priority={job_priority}")

            # Store the rate limiting configuration in job metadata
            AssetProcessor.update_job_metadata(self.job_id, {
                'maxConcurrentTasks': max_concurrent_tasks,
                'jobPriority': job_priority
            })

            response = s3control.create_job(
                AccountId=account_id,
                ConfirmationRequired=False,
                Operation={
                    'LambdaInvoke': {
                        'FunctionArn': processor_function_arn,
                        'InvocationSchemaVersion': '2.0',  # Updated to 2.0
                        'UserArguments': {k: str(v) for k, v in user_args.items()}
                    }
                },
                Report={
                    'Bucket': f"arn:aws:s3:::{self.results_bucket}",
                    'Prefix': f"job-reports/{self.job_id}",
                    'Format': 'Report_CSV_20180820',
                    'Enabled': True,
                    'ReportScope': 'AllTasks'
                },
                Manifest={
                    'Spec': {
                        'Format': 'S3BatchOperations_CSV_20180820',
                        'Fields': ['Bucket', 'Key']
                    },
                    'Location': {
                        'ObjectArn': f"arn:aws:s3:::{self.results_bucket}/{manifest_key}",
                        'ETag': etag
                    }
                },
                Priority=job_priority,
                RoleArn=batch_operations_role_arn,
                Description=f"Asset sync for job {self.job_id}",
                ClientRequestToken=self.job_id
            )

            batch_job_id = response['JobId']
            logger.info(f"Created S3 batch operations job: {batch_job_id}")

            # Store batch job ID in job metadata
            AssetProcessor.update_job_metadata(self.job_id, {
                'batchJobId': batch_job_id,
                'manifestKey': manifest_key
            })
            
            # Start the batch job
            try:
                s3control.update_job_status(
                    AccountId=account_id,
                    JobId=batch_job_id,
                    RequestedJobStatus='Ready'
                )
                logger.info(f"Successfully started S3 batch job: {batch_job_id}")
            except Exception as e:
                logger.error(f"Error starting S3 batch job {batch_job_id}: {str(e)}", exc_info=True)
                
                # Update job status to failed
                AssetProcessor.update_job_status(
                    self.job_id,
                    JobStatus.FAILED,
                    f"Failed to start batch job: {str(e)}"
                )
                
                raise

            return batch_job_id

        except Exception as e:
            logger.error(f"Error creating S3 batch operations job: {str(e)}", exc_info=True)

            # Update job status to failed
            AssetProcessor.update_job_status(
                self.job_id,
                JobStatus.FAILED,
                f"Failed to create batch job: {str(e)}"
            )

            raise
        
    def _generate_csv_manifest(self) -> str:
        """
        Generate a CSV manifest file for S3 batch operations with no header row
        
        Returns:
            CSV content as string
        """
        logger.info(f"Generating CSV manifest for bucket {self.bucket_name}, prefix: {self.prefix or 'NONE'}")
        
        # Use StringIO to hold CSV data
        output = io.StringIO()
        csv_writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)
        
        objects_count = 0
        continuation_token = None
        
        list_params = {
            'Bucket': self.bucket_name,
            'MaxKeys': 1000
        }
        
        if self.prefix:
            list_params['Prefix'] = self.prefix
            
        while objects_count < MAX_MANIFEST_SIZE:
            if continuation_token:
                list_params['ContinuationToken'] = continuation_token
                
            try:
                response = self.retry_with_backoff(
                    self.s3_client.list_objects_v2,
                    **list_params
                )
                
                contents = response.get('Contents', [])
                for obj in contents:
                    key = obj.get('Key', '')
                    # Write row with bucket and key - csv.writer handles proper escaping
                    csv_writer.writerow([self.bucket_name, key])
                    objects_count += 1
                    
                    if objects_count >= MAX_MANIFEST_SIZE:
                        logger.info(f"Reached maximum manifest size: {MAX_MANIFEST_SIZE} objects")
                        break
                        
                continuation_token = response.get('NextContinuationToken')
                if not continuation_token or not response.get('IsTruncated'):
                    logger.info(f"Completed listing all objects: {objects_count} total")
                    break
                    
            except Exception as e:
                logger.error(f"Error listing objects: {str(e)}", exc_info=True)
                raise
                
        logger.info(f"Generated manifest with {objects_count} objects for bucket '{self.bucket_name}'")
        
        # Get CSV content as string
        csv_content = output.getvalue()
        
        # Log first few lines of the manifest for verification
        preview_lines = "\n".join(csv_content.split("\n")[:5])
        logger.info(f"Manifest preview:\n{preview_lines}")
        
        AssetProcessor.update_job_metadata(self.job_id, {
            'objectsCount': objects_count
        })
        
        return csv_content
        
    def split_manifest_into_chunks(self, manifest_key: str) -> List[str]:
        """
        Split a large manifest into smaller chunks for processing
        
        Args:
            manifest_key: S3 key of the manifest file
            
        Returns:
            List of chunk keys in S3
        """
        logger.info(f"Splitting manifest {manifest_key} into chunks")
        
        # Get the manifest from S3
        try:
            response = self.s3_client.get_object(
                Bucket=self.results_bucket,
                Key=manifest_key
            )
            manifest_content = response['Body'].read().decode('utf-8')
            
            # Parse the CSV
            csv_lines = manifest_content.strip().split('\n')
            header = csv_lines[0]
            data_lines = csv_lines[1:]
            
            logger.info(f"Processing {len(data_lines)} objects from manifest")
            
            # Calculate number of chunks
            chunks_count = (len(data_lines) + MAX_CHUNK_SIZE - 1) // MAX_CHUNK_SIZE
            chunk_keys = []
            
            # Create chunks
            for i in range(chunks_count):
                chunk_start = i * MAX_CHUNK_SIZE
                chunk_end = min((i + 1) * MAX_CHUNK_SIZE, len(data_lines))
                
                chunk_lines = [header] + data_lines[chunk_start:chunk_end]
                chunk_content = '\n'.join(chunk_lines)
                
                # Create a unique chunk key
                chunk_key = f"job-chunks/{self.job_id}/chunk-{i+1}-of-{chunks_count}.csv"
                
                # Upload chunk to S3
                self.s3_client.put_object(
                    Bucket=self.results_bucket,
                    Key=chunk_key,
                    Body=chunk_content,
                    ContentType='text/csv'
                )
                
                chunk_keys.append(chunk_key)
                logger.info(f"Created chunk {i+1}/{chunks_count}: {len(chunk_lines)-1} objects")
                
            # Update job metadata with chunk information
            AssetProcessor.update_job_metadata(self.job_id, {
                'chunksCount': chunks_count,
                'chunksProcessed': 0,
                'objectsCount': len(data_lines)
            })
            
            return chunk_keys
            
        except Exception as e:
            logger.error(f"Error splitting manifest: {str(e)}", exc_info=True)
            
            # Update job status to failed
            AssetProcessor.update_job_status(
                self.job_id,
                JobStatus.FAILED,
                f"Failed to split manifest: {str(e)}"
            )
            
            raise
            
    def enqueue_chunks_for_processing(self, chunk_keys: List[str]) -> None:
        """
        Enqueue chunks for processing
        
        Args:
            chunk_keys: List of chunk keys in S3
        """
        logger.info(f"Enqueueing {len(chunk_keys)} chunks for processing")
        
        # Get processor queue URL
        processor_queue_url = os.environ.get('PROCESSOR_QUEUE_URL')
        if not processor_queue_url:
            logger.error("PROCESSOR_QUEUE_URL environment variable is not set")
            raise ValueError("PROCESSOR_QUEUE_URL environment variable is not set")
            
        # Create SQS client
        sqs = get_optimized_client('sqs')
        
        # Enqueue chunks
        for i, chunk_key in enumerate(chunk_keys):
            # Create message
            message = {
                'jobId': self.job_id,
                'operation': 'PROCESS_CHUNK',
                'chunkKey': chunk_key,
                'chunkIndex': i + 1,
                'totalChunks': len(chunk_keys),
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
            
            # Send message
            try:
                sqs.send_message(
                    QueueUrl=processor_queue_url,
                    MessageBody=json.dumps(message),
                    MessageAttributes={
                        'jobId': {
                            'DataType': 'String',
                            'StringValue': self.job_id
                        },
                        'operation': {
                            'DataType': 'String',
                            'StringValue': 'PROCESS_CHUNK'
                        }
                    }
                )
                logger.info(f"Enqueued chunk {i+1}/{len(chunk_keys)}: {chunk_key}")
            except Exception as e:
                logger.error(f"Error enqueueing chunk {chunk_key}: {str(e)}", exc_info=True)
                # Continue with the next chunk
        
        # Update job status
        AssetProcessor.update_job_status(
            self.job_id,
            JobStatus.PROCESSING,
            f"Processing {len(chunk_keys)} chunks"
        )


def check_stuck_jobs():
    """Check for and recover stuck jobs"""
    logger.info("Checking for stuck jobs")
    
    # Get job table name
    job_table_name = os.environ.get('JOB_TABLE_NAME')
    if not job_table_name:
        logger.error("JOB_TABLE_NAME environment variable is not set")
        return
        
    # Create DynamoDB client
    dynamodb = boto3.resource('dynamodb')
    job_table = dynamodb.Table(job_table_name)
    
    # Get current time
    now = datetime.now(timezone.utc)
    
    # Scan for jobs in DISCOVERING, SCANNING, or PROCESSING status
    try:
        response = job_table.scan(
            FilterExpression="(#status = :discovering OR #status = :scanning OR #status = :processing) AND #last_updated < :threshold",
            ExpressionAttributeNames={
                '#status': 'status',
                '#last_updated': 'lastUpdated'
            },
            ExpressionAttributeValues={
                ':discovering': JobStatus.DISCOVERING.value,
                ':scanning': JobStatus.SCANNING.value,
                ':processing': JobStatus.PROCESSING.value,
                ':threshold': (now - timedelta(minutes=30)).isoformat()  # 30 minutes ago
            }
        )
        
        stuck_jobs = response.get('Items', [])
        logger.info(f"Found {len(stuck_jobs)} potentially stuck jobs")
        
        # Handle each stuck job
        for job in stuck_jobs:
            job_id = job.get('jobId')
            status = job.get('status')
            last_updated = job.get('lastUpdated')
            logger.info(f"Processing potentially stuck job {job_id} in status {status}, last updated at {last_updated}")
            
            # Get job metadata
            metadata = job.get('metadata', {})
            batch_job_id = metadata.get('batchJobId')
            
            if batch_job_id:
                # Check the status of the S3 batch job
                try:
                    s3control = boto3.client('s3control', region_name=boto3.session.Session().region_name)
                    account_id = boto3.client('sts').get_caller_identity().get('Account')
                    
                    batch_job = s3control.describe_job(
                        AccountId=account_id,
                        JobId=batch_job_id
                    )
                    
                    batch_status = batch_job.get('Job', {}).get('Status')
                    logger.info(f"S3 batch job {batch_job_id} for job {job_id} has status {batch_status}")
                    
                    # If the batch job is complete but the job is still in SCANNING or DISCOVERING status,
                    # update the job status
                    if batch_status == 'Complete' and status in [JobStatus.DISCOVERING.value, JobStatus.SCANNING.value]:
                        logger.info(f"Batch job is complete, but job is still in {status} status. Updating job status.")
                        
                        # Get the manifest key
                        manifest_key = metadata.get('manifestKey')
                        if manifest_key:
                            # Create engine to process the job
                            engine = AssetSyncEngine(job_id, job.get('bucketName'), job.get('objectPrefix'))
                            
                            # Split the manifest into chunks
                            try:
                                chunk_keys = engine.split_manifest_into_chunks(manifest_key)
                                
                                # Enqueue chunks for processing
                                engine.enqueue_chunks_for_processing(chunk_keys)
                                
                                logger.info(f"Successfully processed manifest and enqueued chunks for job {job_id}")
                            except Exception as e:
                                logger.error(f"Error processing manifest for job {job_id}: {str(e)}", exc_info=True)
                                
                                # Update job status to failed
                                AssetProcessor.update_job_status(
                                    job_id,
                                    JobStatus.FAILED,
                                    f"Failed to process manifest: {str(e)}"
                                )
                        else:
                            logger.error(f"No manifest key found for job {job_id}")
                            
                            # Update job status to failed
                            AssetProcessor.update_job_status(
                                job_id,
                                JobStatus.FAILED,
                                "No manifest key found"
                            )
                    elif batch_status == 'Failed':
                        logger.error(f"Batch job {batch_job_id} for job {job_id} has failed")
                        
                        # Update job status to failed
                        AssetProcessor.update_job_status(
                            job_id,
                            JobStatus.FAILED,
                            f"S3 batch job failed: {batch_job.get('Job', {}).get('FailureReasons', ['Unknown error'])}"
                        )
                    elif batch_status == 'Cancelled':
                        logger.info(f"Batch job {batch_job_id} for job {job_id} was cancelled")
                        
                        # Update job status to cancelled
                        AssetProcessor.update_job_status(
                            job_id,
                            JobStatus.CANCELLED,
                            "S3 batch job was cancelled"
                        )
                    
                except Exception as e:
                    logger.error(f"Error checking batch job {batch_job_id} for job {job_id}: {str(e)}", exc_info=True)
            else:
                # If the job has been in PROCESSING status for too long, check the chunk processing
                if status == JobStatus.PROCESSING.value:
                    chunks_count = metadata.get('chunksCount', 0)
                    chunks_processed = metadata.get('chunksProcessed', 0)
                    
                    logger.info(f"Job {job_id} has processed {chunks_processed}/{chunks_count} chunks")
                    
                    # If all chunks are processed but job is still in PROCESSING status,
                    # update the job status to COMPLETED
                    if chunks_processed >= chunks_count and chunks_count > 0:
                        logger.info(f"All chunks processed for job {job_id}, updating status to COMPLETED")
                        
                        AssetProcessor.update_job_status(
                            job_id,
                            JobStatus.COMPLETED,
                            f"Completed processing {metadata.get('objectsCount', 0)} objects"
                        )
        
        return stuck_jobs
        
    except Exception as e:
        logger.error(f"Error checking for stuck jobs: {str(e)}", exc_info=True)
        return []


@tracer.capture_lambda_handler
@metrics.log_metrics
def lambda_handler(event, context):
    """Lambda handler for Asset Sync Engine"""
    try:
        logger.info(f"Received event: {json.dumps(event)}")
        
        # Handle CHECK_STUCK_JOBS event from EventBridge rule
        if isinstance(event, dict) and 'CHECK_STUCK_JOBS' in event:
            logger.info("Processing CHECK_STUCK_JOBS event")
            try:
                stuck_jobs = check_stuck_jobs()
                return {
                    "status": "success", 
                    "message": f"Completed check for stuck jobs, found {len(stuck_jobs)} stuck jobs"
                }
            except Exception as e:
                logger.error(f"Error checking stuck jobs: {str(e)}", exc_info=True)
                return {"error": f"Error checking stuck jobs: {str(e)}"}
        
        # Handle detail from EventBridge S3 batch event
        elif 'detail' in event and 'jobId' in event.get('detail', {}):
            # This is an EventBridge event from S3 batch operations
            batch_job_id = event['detail'].get('jobId')
            batch_status = event['detail'].get('status')
            
            logger.info(f"Processing S3 batch job status change: {batch_job_id} -> {batch_status}")
            
            # Find the job that initiated this batch job
            try:
                # Get job table name
                job_table_name = os.environ.get('JOB_TABLE_NAME')
                if not job_table_name:
                    logger.error("JOB_TABLE_NAME environment variable is not set")
                    return {"error": "JOB_TABLE_NAME environment variable is not set"}
                    
                # Create DynamoDB client
                dynamodb = boto3.resource('dynamodb')
                job_table = dynamodb.Table(job_table_name)
                
                # Scan for jobs with this batch job ID
                response = job_table.scan(
                    FilterExpression="metadata.batchJobId = :batch_job_id",
                    ExpressionAttributeValues={
                        ':batch_job_id': batch_job_id
                    }
                )
                
                jobs = response.get('Items', [])
                
                if not jobs:
                    logger.warning(f"No job found for batch job ID {batch_job_id}")
                    return {"error": f"No job found for batch job ID {batch_job_id}"}
                    
                # Should be only one job with this batch job ID
                job = jobs[0]
                job_id = job.get('jobId')
                
                logger.info(f"Found job {job_id} for batch job {batch_job_id}")
                
                if batch_status == 'Complete':
                    logger.info(f"Batch job {batch_job_id} completed successfully")
                    
                    # Get the manifest key
                    manifest_key = job.get('metadata', {}).get('manifestKey')
                    if not manifest_key:
                        logger.error(f"No manifest key found for job {job_id}")
                        
                        # Update job status to failed
                        AssetProcessor.update_job_status(
                            job_id,
                            JobStatus.FAILED,
                            "No manifest key found"
                        )
                        
                        return {"error": f"No manifest key found for job {job_id}"}
                        
                    # Create engine to process the job
                    engine = AssetSyncEngine(job_id, job.get('bucketName'), job.get('objectPrefix'))
                    
                    # Split the manifest into chunks
                    try:
                        chunk_keys = engine.split_manifest_into_chunks(manifest_key)
                        
                        # Enqueue chunks for processing
                        engine.enqueue_chunks_for_processing(chunk_keys)
                        
                        logger.info(f"Successfully processed manifest and enqueued chunks for job {job_id}")
                        
                        return {
                            "status": "success", 
                            "message": f"Enqueued {len(chunk_keys)} chunks for processing"
                        }
                    except Exception as e:
                        logger.error(f"Error processing manifest for job {job_id}: {str(e)}", exc_info=True)
                        
                        # Update job status to failed
                        AssetProcessor.update_job_status(
                            job_id,
                            JobStatus.FAILED,
                            f"Failed to process manifest: {str(e)}"
                        )
                        
                        return {"error": f"Error processing manifest: {str(e)}"}
                        
                elif batch_status in ['Failed', 'Cancelled']:
                    logger.error(f"Batch job {batch_job_id} {batch_status.lower()}")
                    
                    # Update job status to failed or cancelled
                    status = JobStatus.FAILED if batch_status == 'Failed' else JobStatus.CANCELLED
                    message = f"S3 batch job {batch_status.lower()}"
                    
                    AssetProcessor.update_job_status(
                        job_id,
                        status,
                        message
                    )
                    
                    return {
                        "status": "error", 
                        "message": f"Batch job {batch_status.lower()}"
                    }
                    
                else:
                    logger.info(f"Batch job {batch_job_id} status change to {batch_status} - no action needed")
                    
                    return {
                        "status": "success", 
                        "message": f"Batch job status changed to {batch_status}"
                    }
                    
            except Exception as e:
                logger.error(f"Error processing batch job status change: {str(e)}", exc_info=True)
                return {"error": f"Error processing batch job status change: {str(e)}"}
        
        # Handle SQS event    
        elif 'Records' in event:
            # This is an SQS event
            for record in event['Records']:
                try:
                    body = json.loads(record.get('body', '{}'))
                    operation = body.get('operation')
                    job_id = body.get('jobId')
                    
                    if not job_id:
                        logger.error("No job ID found in SQS message")
                        continue
                        
                    # Get the job details
                    job = AssetProcessor.get_job_details(job_id)
                    if not job:
                        logger.error(f"Job {job_id} not found")
                        continue
                        
                    # Initialize the engine
                    engine = AssetSyncEngine(job_id, job.get('bucketName'), job.get('objectPrefix'))
                    
                    if operation == 'START_SYNC':
                        logger.info(f"Starting sync for job {job_id}")
                        
                        try:
                            # Create S3 batch operations job
                            batch_job_id = engine.create_batch_operations_job()
                            logger.info(f"Created S3 batch job {batch_job_id} for job {job_id}")
                        except Exception as e:
                            logger.error(f"Error starting sync for job {job_id}: {str(e)}", exc_info=True)
                            
                            # Update job status to failed
                            AssetProcessor.update_job_status(
                                job_id,
                                JobStatus.FAILED,
                                f"Failed to start sync: {str(e)}"
                            )
                    else:
                        logger.warning(f"Unknown operation: {operation}")
                        
                except Exception as e:
                    logger.error(f"Error processing SQS record: {str(e)}", exc_info=True)
                    
            return {"status": "success", "message": f"Processed {len(event['Records'])} SQS messages"}
            
        # Handle direct invocation
        elif 'jobId' in event and 'bucketName' in event:
            # This is a direct invocation
            job_id = event.get('jobId')
            bucket_name = event.get('bucketName')
            prefix = event.get('objectPrefix')
            
            # Get maxConcurrentTasks from event or use default of 500
            max_concurrent_tasks = event.get('maxConcurrentTasks', 250)
            
            logger.info(f"Starting sync for job {job_id}, bucket {bucket_name}, prefix {prefix}, maxConcurrentTasks={max_concurrent_tasks}")
            
            # Initialize the engine with the max_concurrent_tasks parameter
            engine = AssetSyncEngine(job_id, bucket_name, prefix, max_concurrent_tasks)
            
            try:
                # Create S3 batch operations job
                batch_job_id = engine.create_batch_operations_job()
                logger.info(f"Created S3 batch job {batch_job_id} for job {job_id} with {max_concurrent_tasks} concurrent tasks")
                
                return {
                    "status": "success", 
                    "message": f"Started S3 batch job {batch_job_id}",
                    "jobId": job_id,
                    "batchJobId": batch_job_id,
                    "maxConcurrentTasks": max_concurrent_tasks
                }
                
            except Exception as e:
                logger.error(f"Error starting sync for job {job_id}: {str(e)}", exc_info=True)
                
                # Update job status to failed
                AssetProcessor.update_job_status(
                    job_id,
                    JobStatus.FAILED,
                    f"Failed to start sync: {str(e)}"
                )
                
                return {"error": f"Failed to start sync: {str(e)}"}
            
        else:
            logger.error("Unrecognized event format")
            return {"error": "Unrecognized event format"}
            
    except Exception as e:
        logger.error(f"Error in lambda handler: {str(e)}", exc_info=True)
        return {"error": f"Error in lambda handler: {str(e)}"}