import os
import json
import boto3
import uuid
import csv
import io
import random
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Callable
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import unquote_plus
from botocore.exceptions import ClientError

from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.metrics import MetricUnit

from common import (
    AssetProcessor, JobStatus, ErrorType,
    get_optimized_client, get_optimized_s3_client, MAX_THREADS
)

# Initialize powertools
logger = Logger()
tracer = Tracer()
metrics = Metrics()

# Define retry constants
MAX_RETRY_ATTEMPTS = 15
BASE_BACKOFF_TIME = 0.1  # 100 ms
MAX_BACKOFF_TIME = 30.0  # 30 seconds

def retry_with_backoff(
    func: Callable, 
    *args, 
    exception_class=ClientError, 
    max_attempts=MAX_RETRY_ATTEMPTS, 
    base_delay=BASE_BACKOFF_TIME, 
    max_delay=MAX_BACKOFF_TIME,
    throttling_errors=('ThrottlingException', 'ProvisionedThroughputExceededException'),
    **kwargs
) -> Any:
    """
    Execute a function with exponential backoff and jitter for retries.
    Specifically handles DynamoDB throttling exceptions.
    
    Args:
        func: Function to execute
        *args: Arguments to pass to the function
        exception_class: Exception class to catch and retry on
        max_attempts: Maximum number of retry attempts
        base_delay: Base delay time in seconds
        max_delay: Maximum delay time in seconds
        throttling_errors: Error codes that indicate throttling
        **kwargs: Keyword arguments to pass to the function
        
    Returns:
        Result from the function call
        
    Raises:
        The last exception if all retries fail
    """
    attempt = 0
    last_exception = None
    metrics_count = 0
    
    while attempt < max_attempts:
        try:
            return func(*args, **kwargs)
        except exception_class as e:
            # Check if this is a throttling error
            if hasattr(e, 'response') and 'Error' in e.response:
                error_code = e.response['Error'].get('Code')
                if error_code not in throttling_errors:
                    # Not a throttling error, reraise
                    raise
            else:
                # Not a ClientError with error code, reraise
                raise
                
            attempt += 1
            metrics_count += 1
            last_exception = e
            
            if attempt >= max_attempts:
                logger.error(f"Max retry attempts ({max_attempts}) exceeded: {str(e)}")
                break
                
            # Calculate delay with exponential backoff and jitter
            delay = min(max_delay, base_delay * (2 ** attempt))
            jitter = random.uniform(0, 1)
            delay = delay + (delay * 0.2 * jitter)  # Add up to 20% jitter
            
            logger.warning(
                f"DynamoDB throttling error on attempt {attempt}/{max_attempts}. "
                f"Retrying in {delay:.2f}s: {str(e)}"
            )
            
            # Record metric for throttling
            metrics.add_metric(
                name="DynamoDBThrottlingRetries",
                unit=MetricUnit.Count,
                value=metrics_count
            )
            
            # Sleep with backoff
            time.sleep(delay)
    
    # If we get here, we've exhausted our retries
    if last_exception:
        raise last_exception
        
    # This should never happen
    raise Exception("Unexpected error in retry mechanism")

# Patch AssetProcessor methods with retry
original_increment_job_counter = AssetProcessor.increment_job_counter
original_update_job_status = AssetProcessor.update_job_status
original_update_job_metadata = AssetProcessor.update_job_metadata
original_log_error = AssetProcessor.log_error

@staticmethod
def patched_increment_job_counter(job_id: str, counter_name: str, increment_by: int = 1) -> bool:
    """Patched method with retry for DynamoDB throttling"""
    return retry_with_backoff(
        original_increment_job_counter,
        job_id, counter_name, increment_by
    )

@staticmethod
def patched_update_job_status(job_id: str, status: JobStatus, message: str = None) -> bool:
    """Patched method with retry for DynamoDB throttling"""
    return retry_with_backoff(
        original_update_job_status,
        job_id, status, message
    )

@staticmethod
def patched_update_job_metadata(job_id: str, metadata: Dict[str, Any]) -> bool:
    """Patched method with retry for DynamoDB throttling"""
    return retry_with_backoff(
        original_update_job_metadata,
        job_id, metadata
    )

@staticmethod
def patched_log_error(error_data: Dict[str, Any]) -> bool:
    """Patched method with retry for DynamoDB throttling"""
    return retry_with_backoff(
        original_log_error,
        error_data
    )

# Apply patches
AssetProcessor.increment_job_counter = patched_increment_job_counter
AssetProcessor.update_job_status = patched_update_job_status
AssetProcessor.update_job_metadata = patched_update_job_metadata
AssetProcessor.log_error = patched_log_error

class AssetSyncProcessor:
    """Processes objects for synchronization with the Asset Management system"""
    
    def __init__(self, job_id: str, bucket_name: str):
        """
        Initialize the Asset Sync Processor
        
        Args:
            job_id: Unique job identifier
            bucket_name: S3 bucket name
        """
        self.job_id = job_id
        self.bucket_name = bucket_name
        self.s3_client = get_optimized_s3_client(bucket_name)
        self.results_bucket = os.environ.get('RESULTS_BUCKET_NAME')
        
        if not self.results_bucket:
            logger.error("RESULTS_BUCKET_NAME environment variable is not set")
            raise ValueError("RESULTS_BUCKET_NAME environment variable is not set")
        
    def process_s3_batch_operation(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a single task from S3 batch operations
        
        Args:
            task: Task information from S3 batch operations
            
        Returns:
            Result of processing
        """
        logger.info(f"Processing S3 batch operation task: {json.dumps(task)}")
        
        # Extract the S3 key
        try:
            key = task.get('s3Key')
            if not key:
                logger.error("No S3 key found in task")
                return {
                    'resultCode': 'PermanentFailure',
                    'resultString': 'No S3 key found in task'
                }
                
            # Get object tags
            tags = self._get_object_tags(key)
            
            # Prepare object for processing
            obj = {
                'key': key,
                'assetId': tags.get('AssetID'),
                'inventoryId': tags.get('InventoryID'),
                'lastModified': datetime.now(timezone.utc).isoformat(),
                'size': 0  # We don't need the size for processing
            }
            
            # Filter and process the object
            objects_to_process = self._filter_objects_to_process([obj])
            
            if not objects_to_process:
                logger.info(f"Object {key} doesn't need processing")
                return {
                    'resultCode': 'Succeeded',
                    'resultString': 'Object already processed'
                }
                
            # Process the object
            result = self._process_object(objects_to_process[0])
            
            if result.get('status') == 'success':
                # Update job counters
                AssetProcessor.increment_job_counter(self.job_id, 'totalObjectsScanned', 1)
                AssetProcessor.increment_job_counter(self.job_id, 'totalObjectsToProcess', 1)
                AssetProcessor.increment_job_counter(self.job_id, 'totalObjectsProcessed', 1)
                
                return {
                    'resultCode': 'Succeeded',
                    'resultString': f"Successfully processed object: {key}"
                }
            else:
                # Update error counters
                AssetProcessor.increment_job_counter(self.job_id, 'totalObjectsScanned', 1)
                AssetProcessor.increment_job_counter(self.job_id, 'totalObjectsToProcess', 1)
                AssetProcessor.increment_job_counter(self.job_id, 'errors', 1)
                
                return {
                    'resultCode': 'PermanentFailure',
                    'resultString': f"Failed to process object: {key}. Error: {result.get('error')}"
                }
                
        except Exception as e:
            logger.error(f"Error processing S3 batch operation task: {str(e)}", exc_info=True)
            
            # Update error counters
            AssetProcessor.increment_job_counter(self.job_id, 'errors', 1)
            
            return {
                'resultCode': 'PermanentFailure',
                'resultString': f"Exception: {str(e)}"
            }
            
    def process_chunk(self, chunk_key: str, chunk_index: int, total_chunks: int) -> Dict[str, int]:
        """
        Process a manifest chunk
        
        Args:
            chunk_key: S3 key of the chunk file
            chunk_index: Index of this chunk
            total_chunks: Total number of chunks
            
        Returns:
            Processing statistics
        """
        logger.info(f"Processing chunk {chunk_key} ({chunk_index}/{total_chunks})")
        
        # Get the chunk from S3
        try:
            response = self.s3_client.get_object(
                Bucket=self.results_bucket,
                Key=chunk_key
            )
            
            # Parse the CSV
            csv_text = response['Body'].read().decode('utf-8')
            csv_reader = csv.DictReader(io.StringIO(csv_text))
            
            objects = []
            for row in csv_reader:
                if 'Key' in row:
                    objects.append({
                        'key': row['Key'],
                        'assetId': None,  # Will be populated during processing
                        'inventoryId': None,  # Will be populated during processing
                        'lastModified': row.get('LastModifiedDate', datetime.now(timezone.utc).isoformat()),
                        'size': int(row.get('Size', 0))
                    })
            
            logger.info(f"Found {len(objects)} objects in chunk {chunk_index}")
            
            # Fetch tags for objects to determine if they need processing
            with ThreadPoolExecutor(max_workers=min(MAX_THREADS, len(objects))) as executor:
                futures = [
                    executor.submit(
                        self._get_object_tags,
                        obj['key']
                    ) for obj in objects
                ]
                
                # Process results
                for i, future in enumerate(futures):
                    try:
                        tags = future.result()
                        objects[i]['assetId'] = tags.get('AssetID')
                        objects[i]['inventoryId'] = tags.get('InventoryID')
                    except Exception as e:
                        logger.warning(f"Error fetching tags for object {objects[i]['key']}: {str(e)}")
            
            # Filter objects that need processing
            objects_to_process = self._filter_objects_to_process(objects)
            
            logger.info(f"Found {len(objects_to_process)} objects that need processing in chunk {chunk_index}")
            
            # Process objects
            results = self._process_objects(objects_to_process)
            
            # Update job progress
            AssetProcessor.increment_job_counter(self.job_id, 'totalObjectsScanned', len(objects))
            AssetProcessor.increment_job_counter(self.job_id, 'totalObjectsToProcess', len(objects_to_process))
            AssetProcessor.increment_job_counter(self.job_id, 'totalObjectsProcessed', results['successful'])
            
            if results['failed'] > 0:
                AssetProcessor.increment_job_counter(self.job_id, 'errors', results['failed'])
            
            # Increment chunks processed counter
            job_details = AssetProcessor.get_job_details(self.job_id)
            metadata = job_details.get('metadata', {})
            chunks_processed = metadata.get('chunksProcessed', 0) + 1
            
            AssetProcessor.update_job_metadata(self.job_id, {
                'chunksProcessed': chunks_processed
            })
            
            # Check if this was the last chunk
            if chunks_processed >= total_chunks:
                logger.info(f"Completed processing all {total_chunks} chunks for job {self.job_id}")
                
                # Update job status to completed
                AssetProcessor.update_job_status(
                    self.job_id,
                    JobStatus.COMPLETED,
                    f"Completed processing {metadata.get('objectsCount', 0)} objects"
                )
            
            return {
                'scanned': len(objects),
                'to_process': len(objects_to_process),
                'processed_successfully': results['successful'],
                'failed': results['failed'],
                'chunk_index': chunk_index,
                'total_chunks': total_chunks,
                'chunks_processed': chunks_processed
            }
            
        except Exception as e:
            logger.error(f"Error processing chunk {chunk_index}: {str(e)}", exc_info=True)
            
            # Update job counters
            AssetProcessor.increment_job_counter(self.job_id, 'errors', 1)
            
            # Rethrow the exception
            raise
            
    def _get_object_tags(self, object_key: str) -> Dict[str, str]:
        """Get tags for an S3 object"""
        try:
            response = self.s3_client.get_object_tagging(
                Bucket=self.bucket_name,
                Key=object_key
            )
            
            return {tag['Key']: tag['Value'] for tag in response.get('TagSet', [])}
        except Exception as e:
            logger.warning(f"Error getting tags for object {object_key}: {str(e)}")
            return {}
            
    def _filter_objects_to_process(self, objects: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Filter objects that need processing
        
        Processing logic:
        1. If neither asset ID nor inventory ID exists - process object (PUT)
        2. If asset ID doesn't exist but inventory ID exists - process object (COPY)
        3. If asset ID exists - skip object (already processed)
        """
        logger.info(f"Filtering {len(objects)} objects for processing")
        
        if not objects:
            return []
            
        # Extract IDs for batch checking
        asset_ids = [obj.get('assetId') for obj in objects if obj.get('assetId')]
        inventory_ids = [obj.get('inventoryId') for obj in objects if obj.get('inventoryId')]
        
        try:
            # Batch check existence with retry
            existing = retry_with_backoff(
                AssetProcessor.batch_check_asset_exists,
                asset_ids, inventory_ids
            )
            existing_asset_ids = existing['asset_ids']
            existing_inventory_ids = existing['inventory_ids']
            
            # Filter objects that need processing
            objects_to_process = []
            
            for obj in objects:
                asset_id = obj.get('assetId')
                inventory_id = obj.get('inventoryId')
                
                # Determine processing action based on ID existence
                if asset_id and asset_id in existing_asset_ids:
                    # Asset ID exists - skip processing
                    continue
                elif inventory_id and inventory_id in existing_inventory_ids:
                    # Inventory ID exists but asset ID doesn't - S3 copy
                    obj['processingAction'] = 'COPY'
                    objects_to_process.append(obj)
                else:
                    # Neither ID exists - full processing
                    obj['processingAction'] = 'PUT'
                    objects_to_process.append(obj)
            
            return objects_to_process
            
        except Exception as e:
            logger.error(f"Error filtering objects: {str(e)}", exc_info=True)
            raise
            
    def _process_objects(self, objects: List[Dict[str, Any]]) -> Dict[str, int]:
        """
        Process a list of objects
        
        Args:
            objects: List of objects to process
            
        Returns:
            Processing results statistics
        """
        logger.info(f"Processing {len(objects)} objects for job {self.job_id}")
        
        # Initialize results
        results = {
            'successful': 0,
            'failed': 0,
            'copy_operations': 0,
            'put_operations': 0,
            'skip_operations': 0
        }
        
        # Process objects in parallel
        with ThreadPoolExecutor(max_workers=min(MAX_THREADS, len(objects))) as executor:
            futures = [
                executor.submit(
                    self._process_object, obj
                ) for obj in objects
            ]
            
            # Collect results
            for future in futures:
                try:
                    result = future.result()
                    
                    if result.get('status') == 'success':
                        results['successful'] += 1
                        
                        # Track operation type
                        action = result.get('action')
                        if action == 'COPY':
                            results['copy_operations'] += 1
                        elif action == 'PUT':
                            results['put_operations'] += 1
                        else:
                            results['skip_operations'] += 1
                    else:
                        results['failed'] += 1
                except Exception as e:
                    logger.error(f"Error processing object: {str(e)}")
                    results['failed'] += 1
        
        logger.info(f"Processing complete: {results['successful']} successful, {results['failed']} failed")
        
        return results
        
    def _process_object(self, obj: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a single object
        
        Args:
            obj: Object to process
            
        Returns:
            Processing result
        """
        # URL decode the object key
        object_key = unquote_plus(obj['key'])
        processing_action = obj.get('processingAction', 'PUT')
        
        try:
            # Get existing tags
            try:
                tags_response = self.s3_client.get_object_tagging(
                    Bucket=self.bucket_name,
                    Key=object_key
                )
                existing_tags = {tag['Key']: tag['Value'] for tag in tags_response.get('TagSet', [])}
            except Exception as e:
                logger.warning(f"Error fetching tags for {object_key}: {str(e)}")
                existing_tags = {}
            
            # Simulate S3 copy operation to trigger ObjectCreated event
            copy_source = {'Bucket': self.bucket_name, 'Key': object_key}
            
            # Generate tag string from existing tags
            tag_string = "&".join([f"{k}={v}" for k, v in existing_tags.items()])
            
            logger.info(f"Simulating S3 copy for object {object_key}")
            
            # Copy object to itself, preserving existing tags
            self.s3_client.copy_object(
                Bucket=self.bucket_name,
                CopySource=copy_source,
                Key=object_key,
                TaggingDirective='REPLACE',
                Tagging=tag_string
            )
            
            logger.info(f"Successfully copied object {object_key}")
            
            # Return success result
            return {
                'status': 'success',
                'key': object_key,
                'action': 'COPY'
            }
            
        except Exception as e:
            # Log error
            error_id = str(uuid.uuid4())
            AssetProcessor.log_error(
                AssetProcessor.format_error(
                    error_id=error_id,
                    object_key=object_key,
                    error_type=ErrorType.PROCESS_ERROR,
                    error_message=str(e),
                    retry_count=0,
                    job_id=self.job_id,
                    bucket_name=self.bucket_name
                )
            )
            
            # Return error result
            return {
                'status': 'error',
                'key': object_key,
                'error': str(e),
                'errorId': error_id
            }


@tracer.capture_lambda_handler
@metrics.log_metrics
def lambda_handler(event, context):
    """Lambda handler for Asset Sync Processor"""
    try:
        logger.info(f"Received event: {json.dumps(event)}")
        
        if 'Records' in event:
            # This is an SQS event
            for record in event['Records']:
                try:
                    body = json.loads(record.get('body', '{}'))
                    operation = body.get('operation')
                    job_id = body.get('jobId')
                    
                    if not job_id:
                        logger.error("No job ID found in message")
                        continue
                        
                    # Get the job details from DynamoDB
                    job_details = retry_with_backoff(
                        AssetProcessor.get_job_details,
                        job_id
                    )
                    if not job_details:
                        logger.error(f"Job {job_id} not found")
                        continue
                        
                    # Extract bucket name
                    bucket_name = job_details.get('bucketName')
                    
                    # Initialize the processor
                    processor = AssetSyncProcessor(job_id, bucket_name)
                    
                    if operation == 'PROCESS_CHUNK':
                        # Process a manifest chunk
                        chunk_key = body.get('chunkKey')
                        chunk_index = body.get('chunkIndex', 1)
                        total_chunks = body.get('totalChunks', 1)
                        
                        if not chunk_key:
                            logger.error("No chunk key found in message")
                            continue
                            
                        try:
                            result = processor.process_chunk(chunk_key, chunk_index, total_chunks)
                            logger.info(f"Processed chunk: {result}")
                        except Exception as e:
                            logger.error(f"Error processing chunk: {str(e)}", exc_info=True)
                            
                            # Update job status to failed if this is a critical error
                            if chunk_index == total_chunks:
                                AssetProcessor.update_job_status(
                                    job_id, 
                                    JobStatus.FAILED,
                                    f"Failed to process chunk: {str(e)}"
                                )
                    else:
                        logger.warning(f"Unknown operation: {operation}")
                        
                except Exception as e:
                    logger.error(f"Error processing SQS record: {str(e)}", exc_info=True)
                    
            return {"status": "success", "message": f"Processed {len(event['Records'])} SQS messages"}
                
        elif 'tasks' in event or 'task' in event or 'job' in event:
            # This is an S3 batch operations event
            logger.info("Processing S3 batch operations event")
            
            # Get the invocation details
            invocation_schema_version = event.get('invocationSchemaVersion', '1.0')
            invocation_id = event.get('invocationId', 'unknown')
            
            # S3 batch operations sends the task directly or in an array
            tasks = event.get('tasks', [])
            if 'task' in event:
                tasks = [event['task']]
            
            # Extract the INTERNAL job ID from userArguments
            job_id = None
            if 'job' in event and isinstance(event['job'], dict):
                # Get userArguments which contains our application's job ID
                user_args = event['job'].get('userArguments', {})
                if isinstance(user_args, dict):
                    job_id = user_args.get('jobId')
                    
                # If we didn't find it in userArguments, log that for debugging
                if not job_id:
                    logger.warning(f"No jobId found in userArguments: {user_args}")
                    # Fallback to using S3 batch job ID
                    s3_batch_job_id = event['job'].get('id')
                    if s3_batch_job_id:
                        logger.info(f"Using S3 batch job ID as fallback: {s3_batch_job_id}")
                        job_id = f"s3batch-{s3_batch_job_id}"
            
            # Log the extracted information for debugging
            logger.info(f"Batch operation details: jobId={job_id}, tasks={len(tasks)}")
            
            if not job_id:
                logger.error("No job ID found in userArguments")
                return {
                    'invocationSchemaVersion': invocation_schema_version,
                    'treatMissingKeysAs': 'PermanentFailure',
                    'invocationId': invocation_id,
                    'results': [
                        {
                            'taskId': task.get('taskId', 'unknown'),
                            'resultCode': 'PermanentFailure',
                            'resultString': 'No job ID found in userArguments'
                        } for task in tasks
                    ]
                }
            
            # Extract bucket name from the tasks
            bucket_name = None
            if tasks:
                # First, try to get from s3BucketArn
                if 's3BucketArn' in tasks[0]:
                    bucket_arn = tasks[0]['s3BucketArn']
                    bucket_name = bucket_arn.split(':')[-1]
                # Otherwise, try s3Bucket directly
                elif 's3Bucket' in tasks[0]:
                    bucket_name = tasks[0]['s3Bucket']
                
                logger.info(f"Extracted bucket name: {bucket_name}")
            
            if not bucket_name:
                # Get the job details from DynamoDB to find the bucket name
                job_details = retry_with_backoff(
                    AssetProcessor.get_job_details,
                    job_id
                )
                if not job_details:
                    logger.error(f"Job {job_id} not found")
                    return {
                        'invocationSchemaVersion': invocation_schema_version,
                        'treatMissingKeysAs': 'PermanentFailure',
                        'invocationId': invocation_id,
                        'results': [
                            {
                                'taskId': task.get('taskId', 'unknown'),
                                'resultCode': 'PermanentFailure',
                                'resultString': f'Job {job_id} not found'
                            } for task in tasks
                        ]
                    }
                # Extract bucket name from job details
                bucket_name = job_details.get('bucketName')
            
            # Initialize the processor
            processor = AssetSyncProcessor(job_id, bucket_name)
            
            # Process tasks and collect results
            results = []
            for task in tasks:
                try:
                    task_id = task.get('taskId', 'unknown')
                    logger.info(f"Processing task {task_id}")
                    
                    result = processor.process_s3_batch_operation(task)
                    results.append({
                        'taskId': task_id,
                        'resultCode': result.get('resultCode', 'PermanentFailure'),
                        'resultString': result.get('resultString', 'Unknown error')
                    })
                except Exception as e:
                    logger.error(f"Error processing task: {str(e)}", exc_info=True)
                    results.append({
                        'taskId': task.get('taskId', 'unknown'),
                        'resultCode': 'PermanentFailure',
                        'resultString': f'Exception: {str(e)}'
                    })
            
            # Return the results
            return {
                'invocationSchemaVersion': invocation_schema_version,
                'treatMissingKeysAs': 'PermanentFailure',
                'invocationId': invocation_id,
                'results': results
            }
            
        else:
            logger.error("Unrecognized event format")
            return {"error": "Unrecognized event format"}
            
    except Exception as e:
        logger.error(f"Error in lambda handler: {str(e)}", exc_info=True)
        return {"error": f"Error in lambda handler: {str(e)}"}

def determine_asset_type(content_type: str, file_extension: str) -> str:
    """
    Determine the asset type using content type and file extension.
    Uses a more comprehensive classification based on mime types and extensions.
    
    Args:
        content_type: The MIME type from S3 metadata
        file_extension: The file extension (without the dot)
    
    Returns:
        One of: "Image", "Video", "Audio", or "Other"
    """
    logger.info(f"Determining asset type for content_type: {content_type}, extension: {file_extension}")
    
    # Convert to lowercase for comparison
    content_type = content_type.lower() if content_type else ""
    file_extension = file_extension.lower() if file_extension else ""
    
    # Track what criteria matched
    matched_criteria = []
    
    # Check MIME type first as it's more reliable
    for prefix in image_mimes:
        if content_type.startswith(prefix):
            matched_criteria.append(f"MIME type {content_type} matched image prefix {prefix}")
            return "Image"
    
    for prefix in video_mimes:
        if content_type.startswith(prefix):
            matched_criteria.append(f"MIME type {content_type} matched video prefix {prefix}")
            return "Video"
    
    for prefix in audio_mimes:
        if content_type.startswith(prefix):
            matched_criteria.append(f"MIME type {content_type} matched audio prefix {prefix}")
            return "Audio"
    
    # If MIME type doesn't give us a clear answer, check file extension
    if file_extension in image_extensions:
        matched_criteria.append(f"File extension {file_extension} matched image extension")
        return "Image"
    
    if file_extension in video_extensions:
        matched_criteria.append(f"File extension {file_extension} matched video extension")
        return "Video"
    
    if file_extension in audio_extensions:
        matched_criteria.append(f"File extension {file_extension} matched audio extension")
        return "Audio"
    
    # Fall back to looking at the first part of the MIME type
    if content_type:
        mime_main_type = content_type.split('/')[0].capitalize()
        if mime_main_type in ["Image", "Video", "Audio"]:
            matched_criteria.append(f"MIME main type {mime_main_type} matched")
            return mime_main_type
    
    logger.warning(
        f"Could not definitively determine asset type. Content-Type: {content_type}, "
        f"Extension: {file_extension}, Matched criteria: {matched_criteria}"
    )
    
    # Return Other instead of defaulting to Image
    return "Other"