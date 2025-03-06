import os
import boto3
import json
import uuid
from concurrent.futures import ThreadPoolExecutor
from common import logger, AssetProcessor, JobStatus, ErrorType

def check_object_status(obj, job_id, bucket_name):
    """Check if an object needs processing based on tags"""
    try:
        # Log the object being checked for debugging
        logger.debug(f"Checking object: {json.dumps(obj)}")
        
        # First try with inventoryId if available (primary key)
        if obj.get('inventoryId'):
            # Strip any prefix like "asset:uuid:" from the inventoryId
            clean_inventory_id = obj['inventoryId'].split(':')[-1] if ':' in obj['inventoryId'] else obj['inventoryId']
            logger.info(f"Checking asset existence with clean inventoryId: {clean_inventory_id}, original: {obj['inventoryId']}")
            try:
                # For primary key, we don't need to specify an index
                logger.info(f"Calling check_asset_exists with inventory_id={clean_inventory_id}")
                
                # Try direct DynamoDB query to avoid any method parameter issues
                try:
                    dynamodb = boto3.resource('dynamodb')
                    assets_table = dynamodb.Table(os.environ.get('ASSETS_TABLE_NAME'))
                    response = assets_table.get_item(Key={"InventoryID": clean_inventory_id})
                    exists = "Item" in response
                    logger.info(f"Direct DynamoDB query for InventoryID={clean_inventory_id}: {exists}")
                except Exception as direct_query_error:
                    logger.error(f"Direct DynamoDB query failed: {str(direct_query_error)}")
                    # Fall back to the method
                    exists = AssetProcessor.check_asset_exists(inventory_id=clean_inventory_id)
                    logger.info(f"Asset check result for inventory_id {clean_inventory_id}: {exists}")
                
                if not exists:
                    return obj
            except Exception as inventory_error:
                error_msg = f"Failed to check asset with inventoryId={clean_inventory_id}: {str(inventory_error)}"
                logger.error(error_msg)
                error_id = str(uuid.uuid4())
                error_details = AssetProcessor.format_error(
                    error_id,
                    obj['key'],
                    ErrorType.DYNAMO_QUERY_ERROR,
                    error_msg,
                    0,
                    job_id,
                    bucket_name
                )
                AssetProcessor.log_error(error_details)
                # Continue to try with assetId if available
        
        # Then try with assetId if available (using AssetIDIndex)
        if obj.get('assetId'):
            # Strip any prefix like "asset:uuid:" or "asset:img:" from the assetId
            clean_asset_id = obj['assetId'].split(':')[-1] if ':' in obj['assetId'] else obj['assetId']
            logger.info(f"Checking asset existence with clean assetId: {clean_asset_id}, original: {obj['assetId']}")
            try:
                # Try direct DynamoDB query using the secondary index
                try:
                    dynamodb = boto3.resource('dynamodb')
                    assets_table = dynamodb.Table(os.environ.get('ASSETS_TABLE_NAME'))
                    response = assets_table.query(
                        IndexName="AssetIDIndex",
                        KeyConditionExpression="DigitalSourceAsset.ID = :assetId",
                        ExpressionAttributeValues={":assetId": clean_asset_id}
                    )
                    exists = len(response.get("Items", [])) > 0
                    logger.info(f"Direct DynamoDB query for AssetIDIndex with DigitalSourceAsset.ID={clean_asset_id}: {exists}")
                except Exception as direct_query_error:
                    error_msg = f"Direct DynamoDB query failed: {str(direct_query_error)}"
                    logger.error(error_msg)
                    # Fall back to the method
                    exists = AssetProcessor.check_asset_exists(asset_id=clean_asset_id)
                    logger.info(f"Asset check result for asset_id {clean_asset_id}: {exists}")
                
                if not exists:
                    return obj
            except Exception as asset_error:
                error_msg = f"Failed to check asset with assetId={clean_asset_id}: {str(asset_error)}"
                logger.error(error_msg)
                error_id = str(uuid.uuid4())
                error_details = AssetProcessor.format_error(
                    error_id,
                    obj['key'],
                    ErrorType.DYNAMO_QUERY_ERROR,
                    error_msg,
                    0,
                    job_id,
                    bucket_name
                )
                AssetProcessor.log_error(error_details)
                # Return the object for processing if we can't determine its status
                return obj
        
        # If no identifiers are available, process the object
        if not obj.get('assetId') and not obj.get('inventoryId'):
            logger.info(f"Object has no assetId or inventoryId, will be processed: {obj['key']}")
            return obj
            
        # If we got here, the asset exists in the database
        return None
            
    except Exception as e:
        error_id = str(uuid.uuid4())
        error_msg = f"Error checking object {obj.get('key', 'unknown')}: {str(e)}"
        logger.error(error_msg)
        error_details = AssetProcessor.format_error(
            error_id,
            obj['key'],
            ErrorType.DYNAMO_QUERY_ERROR,
            error_msg,
            0,
            job_id,
            bucket_name
        )
        AssetProcessor.log_error(error_details)
        # Raise the exception to fail the Lambda and make it visible in Step Functions
        raise Exception(f"Object status check failed for {obj.get('key', 'unknown')}: {str(e)}")

def lambda_handler(event, context):
    try:
        # Validate required input parameters
        if not event.get('jobId'):
            raise ValueError("Missing required parameter: jobId")
        if not event.get('bucketName'):
            raise ValueError("Missing required parameter: bucketName")
        if not event.get('scanResult') or not event.get('scanResult', {}).get('objects'):
            raise ValueError("Missing required parameter: scanResult.objects")
            
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
        errors = []
        
        with ThreadPoolExecutor(max_workers=min(32, len(objects))) as executor:
            futures = [executor.submit(check_object_status, obj, job_id, bucket_name) for obj in objects]
            for future in futures:
                try:
                    result = future.result()
                    if result:
                        objects_to_process.append(result)
                except Exception as e:
                    error_count += 1
                    error_msg = f"Error checking object status: {str(e)}"
                    logger.error(error_msg)
                    errors.append(error_msg)
        
        # If we encountered errors, fail the Lambda
        if error_count > 0:
            AssetProcessor.increment_job_counter(job_id, 'errors', error_count)
            error_summary = f"Encountered {error_count} errors during object status check"
            AssetProcessor.update_job_status(
                job_id,
                JobStatus.FAILED,
                error_summary
            )
            raise Exception(f"{error_summary}: {'; '.join(errors[:5])}{'...' if len(errors) > 5 else ''}")
        
        # Update job statistics
        AssetProcessor.increment_job_counter(job_id, 'objectsToProcess', len(objects_to_process))
        
        logger.info(f"Found {len(objects_to_process)} objects requiring processing for job {job_id}")
        
        return {
            'objectsToProcess': objects_to_process,
            'processCount': len(objects_to_process)
        }
    except Exception as e:
        error_id = str(uuid.uuid4())
        error_msg = f"Query lambda failed: {str(e)}"
        logger.error(error_msg)
        error_details = AssetProcessor.format_error(
            error_id,
            "N/A",
            ErrorType.DYNAMO_QUERY_ERROR,
            error_msg,
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
        
        # Re-raise the exception to fail the Lambda and make it visible in Step Functions
        raise