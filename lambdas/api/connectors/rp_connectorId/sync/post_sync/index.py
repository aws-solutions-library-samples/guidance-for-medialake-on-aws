import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import boto3
from aws_lambda_powertools import Metrics, Tracer
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.validation import validate
from aws_lambda_powertools.utilities.validation.exceptions import SchemaValidationError
from common import AssetProcessor, DecimalEncoder, ErrorType, JobStatus, logger

# Initialize powertools
tracer = Tracer()
metrics = Metrics(namespace="MedialakeConnectorSync")

# Define JSON schema for input validation
INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "jobId": {"type": "string"},
        "objectPrefix": {"type": ["string", "null"]},
        "concurrencyLimit": {"type": "integer", "minimum": 1, "maximum": 100},
        "batchSize": {"type": "integer", "minimum": 1, "maximum": 10000},
        "continuationToken": {"type": ["string", "null"]},
    },
    "additionalProperties": True,
}


def api_response(status_code: int, body: Dict[str, Any]) -> Dict[str, Any]:
    """Format API Gateway response"""
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps(body, cls=DecimalEncoder),
    }


@tracer.capture_method
def get_bucket_name_for_connector(connector_id: str) -> Optional[str]:
    """Get S3 bucket name associated with a connector ID"""
    logger.info(f"Retrieving bucket name for connector ID: {connector_id}")
    try:
        # Log environment variables for debugging
        logger.info(
            f"Environment variables: MEDIALAKE_CONNECTOR_TABLE={os.environ.get('MEDIALAKE_CONNECTOR_TABLE', 'NOT_SET')}"
        )

        # Use DynamoDB to look up the connector details
        if "MEDIALAKE_CONNECTOR_TABLE" in os.environ:
            dynamodb = boto3.resource("dynamodb")
            table_name = os.environ["MEDIALAKE_CONNECTOR_TABLE"]
            connector_table = dynamodb.Table(table_name)

            logger.info(f"Looking up connector {connector_id} in table {table_name}")
            response = connector_table.get_item(Key={"id": connector_id})

            logger.info(f"DynamoDB response: {json.dumps(response, default=str)}")

            if "Item" in response:
                # Get the storage identifier which is used as the bucket name
                storage_id = response["Item"].get("storageIdentifier")
                logger.info(
                    f"Found storage identifier '{storage_id}' for connector {connector_id}"
                )
                return storage_id
            else:
                logger.error(
                    f"Connector {connector_id} not found in DynamoDB table {table_name}"
                )
                return None
        else:
            logger.error("MEDIALAKE_CONNECTOR_TABLE environment variable is not set")
            return None

    except Exception as e:
        logger.error(
            f"Error getting bucket name for connector {connector_id}: {str(e)}",
            exc_info=True,
        )
        return None


@tracer.capture_method
def get_connector_details(connector_id: str) -> Optional[Dict[str, Any]]:
    """Get full connector details including bucket name and object prefixes"""
    logger.info(f"Retrieving connector details for connector ID: {connector_id}")
    try:
        # Log environment variables for debugging
        logger.info(
            f"Environment variables: MEDIALAKE_CONNECTOR_TABLE={os.environ.get('MEDIALAKE_CONNECTOR_TABLE', 'NOT_SET')}"
        )

        # Use DynamoDB to look up the connector details
        if "MEDIALAKE_CONNECTOR_TABLE" in os.environ:
            dynamodb = boto3.resource("dynamodb")
            table_name = os.environ["MEDIALAKE_CONNECTOR_TABLE"]
            connector_table = dynamodb.Table(table_name)

            logger.info(f"Looking up connector {connector_id} in table {table_name}")
            response = connector_table.get_item(Key={"id": connector_id})

            logger.info(f"DynamoDB response: {json.dumps(response, default=str)}")

            if "Item" in response:
                connector = response["Item"]
                bucket_name = connector.get("storageIdentifier")
                object_prefix = connector.get("objectPrefix")

                # Handle different types of object prefix values
                prefixes = []
                if object_prefix:
                    if isinstance(object_prefix, str):
                        # Single string prefix
                        prefixes = [object_prefix]
                    elif isinstance(object_prefix, list):
                        # List of prefixes
                        prefixes = [
                            prefix
                            for prefix in object_prefix
                            if prefix and prefix.strip()
                        ]

                result = {
                    "bucketName": bucket_name,
                    "objectPrefixes": prefixes,
                    "connectorId": connector_id,
                    "status": connector.get("status"),
                    "name": connector.get("name"),
                }

                logger.info(
                    f"Found connector details for {connector_id}: bucket='{bucket_name}', prefixes={prefixes}"
                )
                return result
            else:
                logger.error(
                    f"Connector {connector_id} not found in DynamoDB table {table_name}"
                )
                return None
        else:
            logger.error("MEDIALAKE_CONNECTOR_TABLE environment variable is not set")
            return None

    except Exception as e:
        logger.error(
            f"Error getting connector details for {connector_id}: {str(e)}",
            exc_info=True,
        )
        return None


@tracer.capture_method
def initialize_job(
    connector_id: str, bucket_name: str, body: Dict[str, Any] = None
) -> Dict[str, Any]:
    """Initialize a new sync job"""
    # Generate a unique job ID
    job_id = body.get("jobId") or str(uuid.uuid4())

    # Extract optional parameters from request body
    if body is None:
        body = {}

    concurrency_limit = min(int(body.get("concurrencyLimit", 10)), 75)
    batch_size = min(int(body.get("batchSize", 1000)), 10000)

    # Calculate TTL for job record (30 days)
    ttl = int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp())

    # Create job record
    job_record = {
        "jobId": job_id,
        "connectorId": connector_id,
        "bucketName": bucket_name,
        "concurrencyLimit": concurrency_limit,
        "batchSize": batch_size,
        "status": JobStatus.INITIALIZING.value,
        "createTime": datetime.now(timezone.utc).isoformat(),
        "lastUpdated": datetime.now(timezone.utc).isoformat(),
        "ttl": ttl,
        "metadata": {"chunksCount": 0, "chunksProcessed": 0, "objectsCount": 0},
        "stats": {
            "totalObjectsScanned": 0,
            "totalObjectsToProcess": 0,
            "totalObjectsProcessed": 0,
            "errors": 0,
        },
    }

    # Log job record
    logger.info(f"Created job record: {json.dumps(job_record, default=str)}")

    # Log environment variables for debugging
    logger.info(
        f"Environment variables: JOB_TABLE_NAME={os.environ.get('JOB_TABLE_NAME', 'NOT_SET')}"
    )

    # Save job record to DynamoDB
    try:
        dynamodb = boto3.resource("dynamodb")
        job_table = dynamodb.Table(os.environ["JOB_TABLE_NAME"])

        logger.info(
            f"Attempting to write job record to table {os.environ['JOB_TABLE_NAME']}"
        )
        job_table.put_item(Item=job_record)
        logger.info(f"Successfully saved job record to DynamoDB")
    except Exception as e:
        logger.error(f"Error saving job record to DynamoDB: {str(e)}", exc_info=True)
        raise

    logger.info(
        f"Initialized sync job {job_id} for connector {connector_id}, bucket {bucket_name}"
    )
    metrics.add_metric(name="JobsInitialized", unit=MetricUnit.Count, value=1)

    # Get the engine Lambda ARN
    engine_function_arn = os.environ.get("ENGINE_FUNCTION_ARN")
    logger.info(f"ENGINE_FUNCTION_ARN environment variable: {engine_function_arn}")

    # If the engine function ARN is not set, try to find it using the function name
    if not engine_function_arn and "ENGINE_FUNCTION_NAME" in os.environ:
        try:
            engine_function_name = os.environ["ENGINE_FUNCTION_NAME"]
            logger.info(
                f"Using ENGINE_FUNCTION_NAME environment variable: {engine_function_name}"
            )

            lambda_client = boto3.client("lambda")
            response = lambda_client.get_function(FunctionName=engine_function_name)
            engine_function_arn = response["Configuration"]["FunctionArn"]
            logger.info(f"Retrieved engine function ARN: {engine_function_arn}")
        except Exception as e:
            logger.error(
                f"Error retrieving engine function ARN: {str(e)}", exc_info=True
            )

    # If asset-sync-engine is in the list of functions, try to use that
    if not engine_function_arn:
        try:
            lambda_client = boto3.client("lambda")
            response = lambda_client.list_functions(MaxItems=100)
            for function in response.get("Functions", []):
                if "asset-sync-engine" in function["FunctionName"].lower():
                    engine_function_arn = function["FunctionArn"]
                    logger.info(
                        f"Found engine function ARN by name pattern: {engine_function_arn}"
                    )
                    break
        except Exception as e:
            logger.error(f"Error listing Lambda functions: {str(e)}", exc_info=True)

    # Start the sync process by invoking the engine lambda directly
    if engine_function_arn:
        lambda_client = boto3.client("lambda")

        # Prepare payload
        payload = {"jobId": job_id, "bucketName": bucket_name}
        logger.info(
            f"Preparing to invoke engine Lambda with payload: {json.dumps(payload)}"
        )

        # Invoke the engine lambda to start the sync process
        try:
            logger.info(f"Invoking engine Lambda: {engine_function_arn}")
            response = lambda_client.invoke(
                FunctionName=engine_function_arn,
                InvocationType="Event",  # Asynchronous invocation
                Payload=json.dumps(payload),
            )

            status_code = response.get("StatusCode")
            logger.info(f"Engine Lambda invocation response: StatusCode={status_code}")

            if status_code == 202:  # 202 Accepted
                logger.info(f"Successfully invoked engine Lambda for job {job_id}")
            else:
                logger.warning(
                    f"Engine Lambda invocation returned unexpected status code: {status_code}"
                )

            # Log the full response for debugging
            logger.info(
                f"Full Lambda invoke response: {json.dumps(response, default=str)}"
            )

        except Exception as e:
            logger.error(f"Error invoking engine Lambda: {str(e)}", exc_info=True)

            # Don't raise the exception - we want to return the job record even if the Lambda invocation fails
            # The job is created in DynamoDB and can be processed later
    else:
        logger.warning(
            f"ENGINE_FUNCTION_ARN not set, sync will not start automatically for job {job_id}"
        )
        logger.info("Available environment variables:")
        for key, value in os.environ.items():
            # Mask sensitive values
            if (
                "key" in key.lower()
                or "secret" in key.lower()
                or "password" in key.lower()
            ):
                logger.info(f"  {key}=*****")
            else:
                logger.info(f"  {key}={value}")

    return job_record


@metrics.log_metrics
@tracer.capture_lambda_handler
def lambda_handler(event, context):
    """Lambda handler for API requests"""
    try:
        logger.info(f"Received API request: {json.dumps(event, default=str)}")
        logger.info(
            f"Lambda context: {context.function_name}, {context.function_version}, {context.memory_limit_in_mb}"
        )

        # Extract path parameters - connector ID is in the path
        path_params = event.get("pathParameters", {}) or {}
        connector_id = path_params.get("connectorId")

        if not connector_id:
            # Extract from path if not in path parameters
            path = event.get("path", "")
            parts = path.split("/")
            for i, part in enumerate(parts):
                if part == "connectors" and i + 1 < len(parts):
                    connector_id = parts[i + 1]
                    logger.info(
                        f"Extracted connector ID {connector_id} from path: {path}"
                    )
                    break

        logger.info(f"Parsed connector ID: {connector_id}")

        if not connector_id:
            logger.error("Missing required parameter: connectorId")
            return api_response(
                400,
                {
                    "error": "Missing required parameter",
                    "message": "connectorId must be provided in the path",
                },
            )

        # Parse request body for optional parameters
        try:
            body = json.loads(event.get("body", "{}")) if event.get("body") else {}
            logger.info(f"Parsed request body: {json.dumps(body)}")

            # Validate input against schema
            validate(event=body, schema=INPUT_SCHEMA)
            logger.info("Request body validation successful")
        except SchemaValidationError as e:
            logger.error(f"Validation error: {str(e)}")
            return api_response(400, {"error": "Invalid request", "message": str(e)})
        except Exception as e:
            logger.error(f"Error parsing request body: {str(e)}", exc_info=True)
            body = {}

        # Get connector details to find the bucket name
        logger.info(f"Getting connector details for connector: {connector_id}")
        connector_details = get_connector_details(connector_id)

        if not connector_details or not connector_details.get("bucketName"):
            logger.error(f"No bucket found for connector ID: {connector_id}")
            return api_response(
                404,
                {
                    "error": f"Connector {connector_id} not found or has no associated bucket"
                },
            )

        bucket_name = connector_details["bucketName"]
        logger.info(f"Found bucket name: {bucket_name}")

        # Initialize the job (object prefixes will be retrieved by the engine from connector table)
        logger.info(
            f"Initializing job for connector {connector_id}, bucket {bucket_name}"
        )
        job = initialize_job(connector_id, bucket_name, body)

        # Return success response
        logger.info(f"Successfully initialized job {job['jobId']}, returning response")
        return api_response(
            202,
            {
                "message": "Sync job started successfully",
                "jobId": job["jobId"],
                "status": job["status"],
                "connectorId": connector_id,
                "bucketName": bucket_name,
            },
        )

    except Exception as e:
        logger.exception(f"Error processing API request: {str(e)}")
        metrics.add_metric(name="ApiErrors", unit=MetricUnit.Count, value=1)

        error_id = str(uuid.uuid4())
        AssetProcessor.log_error(
            AssetProcessor.format_error(
                error_id=error_id,
                object_key="API_REQUEST",
                error_type=ErrorType.UNKNOWN_ERROR,
                error_message=str(e),
                retry_count=0,
                job_id="API_REQUEST",
                bucket_name="N/A",
            )
        )

        return api_response(
            500,
            {"error": "Internal server error", "message": str(e), "errorId": error_id},
        )
