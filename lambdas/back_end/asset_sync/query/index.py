import os
import boto3
import json
import uuid
from concurrent.futures import ThreadPoolExecutor
from common import logger, AssetProcessor, JobStatus, ErrorType

def check_object_status(obj, job_id, bucket_name):
    """Check if an object needs processing based on tags"""
    try:
        if obj.get('assetId'):
            exists = AssetProcessor.check_asset_exists(asset_id=obj['assetId'])
            if not exists:
                return obj
        elif obj.get('inventoryId'):
            exists = AssetProcessor.check_asset_exists(inventory_id=obj['inventoryId'])
            if not exists:
                return obj
        else:
            return obj
    except Exception as e:
        error_id = str(uuid.uuid4())
        error_details = AssetProcessor.format_error(
            error_id,
            obj['key'],
            ErrorType.DYNAMO_QUERY_ERROR,
            str(e),
            0,
            job_id,
            bucket_name
        )
        AssetProcessor.log_error(error_details)
    return None

def handle(event, context):
    try:
        job_id = event['jobId']
        bucket_name = event['bucketName']
        scan_result = event['scanResult']
        objects = scan_result['objects']
        
        # Update job status
        AssetProcessor.update_job_status(
            job_id, 
            JobStatus.PROCESSING, 
            f"Checking {len(objects)} objects against assets table"
        )
        
        logger.info(f"Checking {len(objects)} objects for job {job_id}")
        
        # Use ThreadPoolExecutor for parallel processing
        objects_to_process = []
        error_count = 0
        
        with ThreadPoolExecutor(max_workers=min(32, len(objects))) as executor:
            futures = [executor.submit(check_object_status, obj, job_id, bucket_name) for obj in objects]
            for future in futures:
                try:
                    result = future.result()
                    if result:
                        objects_to_process.append(result)
                except Exception as e:
                    error_count += 1
                    logger.error(f"Error checking object status: {str(e)}")
        
        # Update job statistics
        AssetProcessor.increment_job_counter(job_id, 'objectsToProcess', len(objects_to_process))
        if error_count > 0:
            AssetProcessor.increment_job_counter(job_id, 'errors', error_count)
        
        logger.info(f"Found {len(objects_to_process)} objects requiring processing for job {job_id}")
        
        return {
            'objectsToProcess': objects_to_process,
            'processCount': len(objects_to_process)
        }
    except Exception as e:
        error_id = str(uuid.uuid4())
        error_details = AssetProcessor.format_error(
            error_id,
            "N/A",
            ErrorType.DYNAMO_QUERY_ERROR,
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
            f"Failed to query assets: {str(e)}"
        )
        
        raise
