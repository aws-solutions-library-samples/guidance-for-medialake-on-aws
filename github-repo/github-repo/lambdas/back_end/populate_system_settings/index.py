import json
import os
from typing import Any, Dict

import boto3


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Custom resource Lambda function to populate system settings table with MediaLake bucket names.
    This function is triggered during CDK deployment.
    """
    print(f"Received event: {json.dumps(event)}")

    request_type = event.get("RequestType")
    response_data = {}

    try:
        if request_type in ["Create", "Update"]:
            # Get bucket names from environment variables
            bucket_names = []

            # Collect all MediaLake bucket names from environment variables
            bucket_env_vars = [
                "ACCESS_LOGS_BUCKET_NAME",
                "MEDIA_ASSETS_BUCKET_NAME",
                "IAC_ASSETS_BUCKET_NAME",
                "EXTERNAL_PAYLOAD_BUCKET_NAME",
                "DDB_EXPORT_BUCKET_NAME",
                "PIPELINES_NODES_TEMPLATES_BUCKET_NAME",
                "ASSET_SYNC_RESULTS_BUCKET_NAME",
                "USER_INTERFACE_BUCKET_NAME",
            ]

            for env_var in bucket_env_vars:
                bucket_name = os.environ.get(env_var)
                if bucket_name:
                    bucket_names.append(bucket_name)
                    print(f"Added bucket from {env_var}: {bucket_name}")

            if bucket_names:
                # Store bucket names in DynamoDB system settings table
                dynamodb = boto3.resource("dynamodb")
                table_name = os.environ.get("SYSTEM_SETTINGS_TABLE_NAME")

                if not table_name:
                    raise Exception(
                        "SYSTEM_SETTINGS_TABLE_NAME environment variable not set"
                    )

                table = dynamodb.Table(table_name)

                # Store the bucket list in the system settings table
                table.put_item(
                    Item={
                        "PK": "SYSTEM_SETTINGS",
                        "SK": "MEDIALAKE_BUCKETS",
                        "setting_value": bucket_names,
                        "description": "List of S3 buckets created by MediaLake infrastructure",
                        "created_by": "system",
                        "last_updated": context.aws_request_id,
                    }
                )

                print(
                    f"Successfully stored {len(bucket_names)} MediaLake bucket names in system settings"
                )
                response_data["BucketCount"] = len(bucket_names)
                response_data["Buckets"] = bucket_names
            else:
                print("No MediaLake bucket names found in environment variables")
                response_data["BucketCount"] = 0
                response_data["Buckets"] = []

        elif request_type == "Delete":
            # Optionally clean up the setting on stack deletion
            try:
                dynamodb = boto3.resource("dynamodb")
                table_name = os.environ.get("SYSTEM_SETTINGS_TABLE_NAME")

                if table_name:
                    table = dynamodb.Table(table_name)
                    table.delete_item(
                        Key={"PK": "SYSTEM_SETTINGS", "SK": "MEDIALAKE_BUCKETS"}
                    )
                    print("Cleaned up MediaLake buckets setting from system table")
            except Exception as e:
                print(f"Error cleaning up setting (non-critical): {str(e)}")

        # Send success response to CloudFormation
        send_response(event, context, "SUCCESS", response_data)

    except Exception as e:
        print(f"Error: {str(e)}")
        send_response(event, context, "FAILED", {"Error": str(e)})

    return {"statusCode": 200}


def send_response(
    event: Dict[str, Any],
    context: Any,
    response_status: str,
    response_data: Dict[str, Any],
):
    """Send response to CloudFormation custom resource."""
    import urllib3

    response_url = event["ResponseURL"]

    response_body = {
        "Status": response_status,
        "Reason": f"See CloudWatch Log Stream: {context.log_stream_name}",
        "PhysicalResourceId": context.log_stream_name,
        "StackId": event["StackId"],
        "RequestId": event["RequestId"],
        "LogicalResourceId": event["LogicalResourceId"],
        "Data": response_data,
    }

    json_response_body = json.dumps(response_body)

    headers = {"content-type": "", "content-length": str(len(json_response_body))}

    http = urllib3.PoolManager()

    try:
        response = http.request(
            "PUT", response_url, body=json_response_body, headers=headers
        )
        print(f"Status code: {response.status}")
    except Exception as e:
        print(f"send_response failed: {e}")
