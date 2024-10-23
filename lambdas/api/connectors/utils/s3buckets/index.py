import boto3
from typing import Dict, List


def lambda_handler(event: Dict, context) -> Dict:
    """
    Lambda function to list all S3 buckets in the AWS account

    Args:
        event (Dict): Lambda event object
        context: Lambda context object

    Returns:
        Dict: Response containing list of S3 buckets
    """
    try:
        # Initialize S3 client
        s3_client = boto3.client("s3")

        # Get list of buckets
        response = s3_client.list_buckets()

        # Extract bucket names from response
        buckets = [bucket["Name"] for bucket in response["Buckets"]]

        return {"statusCode": 200, "body": {"buckets": buckets, "count": len(buckets)}}

    except Exception as e:
        return {
            "statusCode": 500,
            "body": {"error": str(e), "message": "Failed to list S3 buckets"},
        }
