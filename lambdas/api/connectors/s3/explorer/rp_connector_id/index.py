import json
import os


def lambda_handler(event, context):
    """Main handler"""
    try:
        # Import boto3 and Key inside handler
        import boto3
        from boto3.dynamodb.conditions import Key
        from botocore.exceptions import ClientError

        # Extract parameters
        connector_id = event["pathParameters"]["connector_id"]
        prefix = event.get("queryStringParameters", {}).get("prefix", "")
        continuation_token = event.get("queryStringParameters", {}).get(
            "continuationToken"
        )

        # Get table name from environment variable
        table_name = os.environ.get("MEDIALAKE_CONNECTOR_TABLE")

        # Get connector details
        try:
            dynamodb = boto3.resource("dynamodb")
            table = dynamodb.Table(table_name)
            print(
                f"Querying DynamoDB table '{table_name}' for connector_id: {connector_id}"
            )

            connector_response = table.query(
                KeyConditionExpression=Key("id").eq(connector_id)
            )
            connector = (
                connector_response["Items"][0] if connector_response["Items"] else None
            )

        except ClientError as e:
            if e.response["Error"]["Code"] == "ResourceNotFoundException":
                print(f"DynamoDB table '{table_name}' not found")
                return {
                    "statusCode": 404,
                    "headers": {
                        "Content-Type": "application/json",
                        "Access-Control-Allow-Origin": "*",
                    },
                    "body": json.dumps(
                        {
                            "status": "error",
                            "message": "Configuration error: Database table not found",
                        }
                    ),
                }
            raise  # Re-raise other ClientError exceptions

        if not connector:
            return {
                "statusCode": 404,
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*",
                },
                "body": json.dumps(
                    {
                        "status": "error",
                        "message": f"Connector {connector_id} not found",
                    }
                ),
            }

        bucket = connector.get("storageIdentifier")
        if not bucket:
            return {
                "statusCode": 400,
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*",
                },
                "body": json.dumps(
                    {
                        "status": "error",
                        "message": "Bucket not configured for connector",
                    }
                ),
            }

        # List S3 objects
        s3_client = boto3.client("s3")
        params = {
            "Bucket": bucket,
            "Delimiter": "/",
            "MaxKeys": 1000,
            "Prefix": prefix or "",
        }
        if continuation_token:
            params["ContinuationToken"] = continuation_token

        response = s3_client.list_objects_v2(**params)

        # Process response
        result = {
            "objects": [
                {
                    "Key": obj["Key"],
                    "LastModified": obj["LastModified"].isoformat(),
                    "Size": obj["Size"],
                    "ETag": obj["ETag"],
                    "StorageClass": obj["StorageClass"],
                }
                for obj in response.get("Contents", [])
                if not obj["Key"].endswith("/")
            ],
            "commonPrefixes": [p["Prefix"] for p in response.get("CommonPrefixes", [])],
            "prefix": prefix,
            "delimiter": "/",
            "isTruncated": response.get("IsTruncated", False),
            "nextContinuationToken": response.get("NextContinuationToken"),
        }

        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
            },
            "body": json.dumps(
                {
                    "status": "success",
                    "message": "Objects retrieved successfully",
                    "data": result,
                }
            ),
        }

    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        error_message = str(e)
        status_code = 400 if "NoSuchBucket" in error_message else 500

        return {
            "statusCode": status_code,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
            },
            "body": json.dumps({"status": "error", "message": error_message}),
        }
