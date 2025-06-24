import boto3
import json
import os
import re


def is_medialake_bucket(bucket_name):
    """
    Check if a bucket is deployed by MediaLake based on naming patterns.
    
    MediaLake buckets typically follow these patterns:
    - {resource_prefix}-*-{account}-{region}-{environment}
    - {resource_prefix}-nodes-templates-{account}-{region}--{environment}
    - Contains 'medialake' in the name (case insensitive)
    """
    resource_prefix = os.environ.get("RESOURCE_PREFIX", "").lower()
    
    # Convert bucket name to lowercase for comparison
    bucket_lower = bucket_name.lower()
    
    # Check if bucket contains 'medialake' in the name
    if "medialake" in bucket_lower:
        return True
    
    # If resource prefix is available, check for MediaLake bucket patterns
    if resource_prefix:
        # Pattern 1: {resource_prefix}-*-{account}-{region}-{environment}
        # Pattern 2: {resource_prefix}-nodes-templates-{account}-{region}--{environment}
        if bucket_lower.startswith(resource_prefix + "-"):
            # Check for common MediaLake bucket suffixes
            medialake_patterns = [
                r"-access-logs?-",
                r"-asset-bucket-",
                r"-iac-assets?-",
                r"-external-payload-",
                r"-dynamodb-export-",
                r"-nodes-templates-",
                r"-media-assets?-"
            ]
            
            for pattern in medialake_patterns:
                if re.search(pattern, bucket_lower):
                    return True
    
    return False


def lambda_handler(event, context):
    try:
        # Create an S3 client
        s3_client = boto3.client("s3")

        # Get list of buckets
        response = s3_client.list_buckets()

        # Extract bucket names from response and filter out MediaLake buckets
        all_buckets = [bucket["Name"] for bucket in response["Buckets"]]
        filtered_buckets = [
            bucket for bucket in all_buckets
            if not is_medialake_bucket(bucket)
        ]

        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
            },
            "body": json.dumps(
                {"status": "200", "message": "ok", "data": {"buckets": filtered_buckets}}
            ),
        }

    except Exception as e:
        return {
            "statusCode": 500,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
            },
            "body": json.dumps(
                {"status": "500", "message": str(e), "data": {"buckets": []}}
            ),
        }
