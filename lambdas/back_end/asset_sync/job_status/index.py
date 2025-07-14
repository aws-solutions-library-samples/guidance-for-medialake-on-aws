import json
import os

import boto3
from boto3.dynamodb.conditions import Key
from common import AssetProcessor, logger


def get_job_errors(job_id, limit=100, last_evaluated_key=None):
    """Get errors associated with a job"""
    try:
        dynamodb = boto3.resource("dynamodb")
        log_table = dynamodb.Table(os.environ.get("LOG_TABLE_NAME", "AssetSyncLogs"))

        params = {"KeyConditionExpression": Key("jobId").eq(job_id), "Limit": limit}

        if last_evaluated_key:
            params["ExclusiveStartKey"] = json.loads(last_evaluated_key)

        response = log_table.query(**params)

        return {
            "items": response.get("Items", []),
            "lastEvaluatedKey": (
                json.dumps(response.get("LastEvaluatedKey"))
                if "LastEvaluatedKey" in response
                else None
            ),
            "count": response.get("Count", 0),
        }
    except Exception as e:
        logger.error(f"Error retrieving job errors: {str(e)}")
        return {"items": [], "lastEvaluatedKey": None, "count": 0}


def lambda_handler(event, context):
    try:
        # Extract job ID from path parameters
        job_id = event.get("pathParameters", {}).get("jobId")

        if not job_id:
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "Job ID is required"}),
            }

        # Get query string parameters for pagination
        query_params = event.get("queryStringParameters", {}) or {}
        include_errors = query_params.get("includeErrors", "false").lower() == "true"
        error_limit = int(query_params.get("errorLimit", "100"))
        error_last_key = query_params.get("errorLastKey")

        # Get job details from DynamoDB
        job_details = AssetProcessor.get_job_details(job_id)

        if not job_details:
            return {"statusCode": 404, "body": json.dumps({"error": "Job not found"})}

        # Get job errors if requested
        if include_errors:
            errors = get_job_errors(job_id, error_limit, error_last_key)
            job_details["errors"] = errors

        # Get state machine execution status if available
        if "executionArn" in job_details:
            try:
                sf_client = boto3.client("stepfunctions")
                execution = sf_client.describe_execution(
                    executionArn=job_details["executionArn"]
                )
                job_details["executionStatus"] = {
                    "status": execution["status"],
                    "startDate": execution["startDate"].isoformat(),
                    "stopDate": (
                        execution.get("stopDate", "").isoformat()
                        if "stopDate" in execution
                        else None
                    ),
                }
            except Exception as e:
                logger.warning(f"Could not get execution status: {str(e)}")

        # Return job status
        return {"statusCode": 200, "body": json.dumps(job_details)}
    except Exception as e:
        logger.error(f"Error retrieving job status: {str(e)}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": f"Failed to retrieve job status: {str(e)}"}),
        }
