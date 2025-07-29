import json
from typing import Any, Dict

import boto3


def lambda_handler(event: Dict[str, Any], context) -> Dict[str, Any]:
    """
    Lambda handler for TwelveLabs Bedrock Status node.
    Checks if async embedding job is complete by polling S3 for output.json file.
    """
    try:
        # Initialize S3 client
        s3 = boto3.client("s3")

        # Extract payload from event
        payload = event.get("payload", {})

        # Get job information from payload
        invocation_arn = payload.get("invocation_arn")
        s3_bucket = payload.get("s3_bucket")
        output_location = payload.get("output_location")

        if not all([invocation_arn, s3_bucket, output_location]):
            raise ValueError(
                "Missing required job information: invocation_arn, s3_bucket, or output_location"
            )

        # Check for output.json file in S3
        try:
            response = s3.list_objects_v2(Bucket=s3_bucket, Prefix=output_location)

            if "Contents" in response:
                # Look for output.json file
                output_files = [
                    obj
                    for obj in response["Contents"]
                    if obj["Key"].endswith("output.json")
                ]

                if output_files:
                    # Job is complete
                    output_file_key = output_files[0]["Key"]

                    result = {
                        "invocation_arn": invocation_arn,
                        "s3_bucket": s3_bucket,
                        "output_location": output_location,
                        "output_file_key": output_file_key,
                        "status": "completed",
                        "message": "Embedding job completed successfully",
                    }

                    # Include original payload data
                    result.update({k: v for k, v in payload.items() if k not in result})

                    return {
                        "statusCode": 200,
                        "body": json.dumps(result),
                        "payload": result,
                    }
                else:
                    # Job is still in progress
                    result = {
                        "invocation_arn": invocation_arn,
                        "s3_bucket": s3_bucket,
                        "output_location": output_location,
                        "status": "in_progress",
                        "message": "Embedding job is still in progress",
                    }

                    # Include original payload data
                    result.update({k: v for k, v in payload.items() if k not in result})

                    return {
                        "statusCode": 200,
                        "body": json.dumps(result),
                        "payload": result,
                    }
            else:
                # No objects found yet - job is still in progress
                result = {
                    "invocation_arn": invocation_arn,
                    "s3_bucket": s3_bucket,
                    "output_location": output_location,
                    "status": "in_progress",
                    "message": "Embedding job is still in progress - no output files found yet",
                }

                # Include original payload data
                result.update({k: v for k, v in payload.items() if k not in result})

                return {
                    "statusCode": 200,
                    "body": json.dumps(result),
                    "payload": result,
                }

        except Exception as s3_error:
            # If we can't access S3, assume job is still in progress
            result = {
                "invocation_arn": invocation_arn,
                "s3_bucket": s3_bucket,
                "output_location": output_location,
                "status": "in_progress",
                "message": f"Unable to check S3 status: {str(s3_error)}",
            }

            # Include original payload data
            result.update({k: v for k, v in payload.items() if k not in result})

            return {"statusCode": 200, "body": json.dumps(result), "payload": result}

    except Exception as e:
        error_msg = f"Error in TwelveLabs Bedrock Status: {str(e)}"
        print(error_msg)
        return {
            "statusCode": 500,
            "body": json.dumps({"error": error_msg}),
            "payload": {"error": error_msg},
        }
