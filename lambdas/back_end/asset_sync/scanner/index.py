import os
import boto3
import json
import uuid
from datetime import datetime
from common import logger, AssetProcessor, JobStatus, ErrorType

def lambda_handler(event, context):
    try:
        job_id = event['jobId']
        bucket_name = event['bucketName']
        batch_size = event.get('batchSize', 1000)
        
        if 'scanResult' in event and event['scanResult'] and 'Payload' in event['scanResult']:
            continuation_token = event['scanResult']['Payload']['continuationToken']
        else:
            continuation_token = None
        
        # Update job status
        AssetProcessor.update_job_status(
            job_id,
            JobStatus.SCANNING, 
            f"Scanning bucket {bucket_name}"
        )
        
        # Initialize S3 client (works for any region)
        s3 = boto3.client('s3')
        
        # List objects from the bucket
        list_params = {
            'Bucket': bucket_name,
            'MaxKeys': batch_size
        }
        
        if continuation_token:
            list_params['ContinuationToken'] = continuation_token

        logger.info(f"Listing objects from bucket {bucket_name} for job {job_id}")
        response = s3.list_objects_v2(**list_params)
        
        objects = []
        error_count = 0
        
        # Process each object and get its tags
        for obj in response.get('Contents', []):
            try:
                tags = s3.get_object_tagging(
                    Bucket=bucket_name,
                    Key=obj['Key']
                )
                
                tag_dict = {tag['Key']: tag['Value'] for tag in tags['TagSet']}
                objects.append({
                    'key': obj['Key'],
                    'assetId': tag_dict.get('AssetID'),
                    'inventoryId': tag_dict.get('InventoryID'),
                    'lastModified': obj['LastModified'].isoformat() if isinstance(obj['LastModified'], datetime) else obj['LastModified'],
                    'size': obj['Size']
                })
            except Exception as e:
                error_count += 1
                error_id = str(uuid.uuid4())
                error_details = AssetProcessor.format_error(
                    error_id,
                    obj['Key'],
                    ErrorType.TAG_FETCH_ERROR,
                    str(e),
                    0,
                    job_id,
                    bucket_name
                )
                AssetProcessor.log_error(error_details)
        
        # Update job statistics
        scanned_count = len(response.get('Contents', []))
        AssetProcessor.increment_job_counter(job_id, 'totalObjectsScanned', scanned_count)
        if error_count > 0:
            AssetProcessor.increment_job_counter(job_id, 'errors', error_count)
        
        logger.info(f"Scanned {scanned_count} objects from bucket {bucket_name} for job {job_id}")
        
        return {
            'objects': objects,
            'continuationToken': response.get('NextContinuationToken'),
            'isTruncated': response.get('IsTruncated', False),
            'scannedCount': scanned_count
        }
    except Exception as e:
        error_id = str(uuid.uuid4())
        error_details = AssetProcessor.format_error(
            error_id,
            "N/A",
            ErrorType.S3_ACCESS_ERROR,
            str(e),
            0,
            event.get('jobId', 'unknown'),
            event.get('bucketName', 'unknown')
        )
        AssetProcessor.log_error(error_details)
        
        # Update job status to reflect error
        AssetProcessor.update_job_status(
            event.get('jobId', 'unknown'),
            JobStatus.FAILED,
            f"Failed to scan bucket: {str(e)}"
        )
        
        raise
