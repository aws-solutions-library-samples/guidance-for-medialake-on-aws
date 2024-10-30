import boto3
import json


def lambda_handler(event, context):
    try:
        # Create an S3 client
        s3_client = boto3.client("s3")

        # Get list of buckets
        response = s3_client.list_buckets()

        # Extract bucket names from response
        buckets = [bucket["Name"] for bucket in response["Buckets"]]

        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",  # Enable CORS
            },
            "body": json.dumps({
                "status": "200",
                "message": "ok",
                "data": {
                    "buckets": buckets
                }
            }),
        }

    except Exception as e:
        return {
            "statusCode": 500,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
            },
            "body": json.dumps({
                "status": "500",
                "message": str(e),
                "data": {
                    "buckets": []
                }
            }),
        }
