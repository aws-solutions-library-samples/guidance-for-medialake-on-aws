import os
import boto3
import json
import uuid
from common import logger, AssetProcessor, JobStatus, ErrorType

def handle(event, context):
    # Initialize clients
    s3 = boto3.client('s3')
    dynamodb = boto3.resource('dynamodb')
    assets_table = dynamodb.Table(os.environ['ASSETS_TABLE_NAME'])
    
    # Process SQS messages
    failed_message_ids = []
    processed_count = 0
    error_count = 0
    
    # Get all SQS messages
    for record in event['Records']:
        try:
            # Parse the message
            message_id = record['messageId']
            message_body = json.loads(record['body'])
            
            job_id = message_body['jobId']
            bucket_name = message_body['bucketName']
            objects = message_body['objects']
            batch_number = message_body.get('batchNumber', 0)
            total_batches = message_body.get('totalBatches', 0)
            
            logger.info(f"Processing batch {batch_number}/{total_batches} with {len(objects)} objects for job {job_id}")
            
            # Process each object in the batch
            for obj in objects:
                try:
                    object_key = obj['key']
                    asset_id = obj.get('assetId')
                    inventory_id = obj.get('inventoryId')
                    
                    # Trigger processing by simulating S3:ObjectCreated event
                    # Option 1: Update tags to trigger an existing event
                    tags = {}
                    if asset_id:
                        tags['AssetID'] = asset_id
                    if inventory_id:
                        tags['InventoryID'] = inventory_id
                        
                    # Simulate the S3:ObjectCreated event by copying the object to itself with new tags
                    # This will trigger any existing event notifications on the bucket
                    
                    # First, get the existing tags if any
                    existing_tags_response = s3.get_object_tagging(
                        Bucket=bucket_name,
                        Key=object_key
                    )
                    existing_tags = {tag['Key']: tag['Value'] for tag in existing_tags_response.get('TagSet', [])}
                    
                    # Merge with new tags
                    merged_tags = {**existing_tags, **tags}
                    
                    # Put the updated tags on the object
                    tag_set = [{'Key': k, 'Value': v} for k, v in merged_tags.items()]
                    s3.put_object_tagging(
                        Bucket=bucket_name,
                        Key=object_key,
                        Tagging={'TagSet': tag_set}
                    )
                    
                    # Copy the object to itself to trigger the S3:ObjectCreated event
                    # This essentially simulates a new object being created
                    s3.copy_object(
                        Bucket=bucket_name,
                        CopySource={'Bucket': bucket_name, 'Key': object_key},
                        Key=object_key,
                        TaggingDirective='REPLACE',
                        Tagging=f"AssetID={asset_id or ''}&InventoryID={inventory_id or ''}"
                    )
                    
                    logger.info(f"Processed object {object_key} for job {job_id}")
                    processed_count += 1
                    
                except Exception as e:
                    error_count += 1
                    error_id = str(uuid.uuid4())
                    error_details = AssetProcessor.format_error(
                        error_id,
                        obj.get('key', 'unknown'),
                        ErrorType.PROCESS_ERROR,
                        str(e),
                        0,
                        job_id,
                        bucket_name
                    )
                    AssetProcessor.log_error(error_details)
            
            # Update job counters
            AssetProcessor.increment_job_counter(job_id, 'objectsProcessed', processed_count)
            if error_count > 0:
                AssetProcessor.increment_job_counter(job_id, 'errors', error_count)
            
        except Exception as e:
            # Track the failed message for batch failure handling
            failed_message_ids.append(record['messageId'])
            logger.error(f"Failed to process message {record['messageId']}: {str(e)}")
    
    # Return failed message IDs for partial batch failures
    if failed_message_ids:
        return {"batchItemFailures": [{"itemIdentifier": mid} for mid in failed_message_ids]}
    
    return {"batchItemFailures": []}
