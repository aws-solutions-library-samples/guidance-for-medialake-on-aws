import os
import sys
import time
from functools import lru_cache

# Import boto3 and Key inside handler
import boto3

# Add common_libraries to path
sys.path.insert(0, "/opt/python")
# Add AWS PowerTools for better tracing and performance measurement
from aws_lambda_powertools import Logger, Metrics, Tracer
from boto3.dynamodb.conditions import Key
from common_libraries.cors_utils import create_response

logger = Logger()
tracer = Tracer()
metrics = Metrics(namespace="MedialakeS3Explorer")

# Create a global S3 client outside the handler to benefit from connection reuse
s3_client = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")


# Cache connector lookups to avoid repeated DB calls
@lru_cache(maxsize=100)
def get_connector(connector_id, table_name):
    """Get connector with caching to avoid repeated DB calls"""
    try:
        logger.debug(f"Getting connector {connector_id} from table {table_name}")
        table = dynamodb.Table(table_name)

        with tracer.provider.in_subsegment("get_connector_from_dynamodb") as subsegment:
            subsegment.put_annotation("connector_id", connector_id)

            start_time = time.time()
            connector_response = table.query(
                KeyConditionExpression=Key("id").eq(connector_id)
            )
            query_time = (time.time() - start_time) * 1000

            metrics.add_metric(
                name="DynamoDBQueryLatency", unit="Milliseconds", value=query_time
            )
            logger.debug(f"DynamoDB query took {query_time}ms")

            return (
                connector_response["Items"][0] if connector_response["Items"] else None
            )
    except Exception as e:
        logger.error(f"Failed to get connector: {str(e)}")
        return None


@logger.inject_lambda_context(correlation_id_path="requestContext.requestId")
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event, context):
    """Main handler for S3 explorer API endpoint"""
    try:
        # Extract parameters
        connector_id = event["pathParameters"]["connector_id"]
        prefix = event.get("queryStringParameters", {}).get("prefix", "")
        continuation_token = event.get("queryStringParameters", {}).get(
            "continuationToken"
        )

        logger.info(
            f"S3 Explorer request for connector: {connector_id}, prefix: {prefix}"
        )

        # Get table name from environment variable
        table_name = os.environ.get("MEDIALAKE_CONNECTOR_TABLE")

        if not table_name:
            logger.error("MEDIALAKE_CONNECTOR_TABLE environment variable not set")
            return create_response(
                500,
                {
                    "status": "error",
                    "message": "Configuration error: Missing MEDIALAKE_CONNECTOR_TABLE environment variable",
                },
            )

        # Get connector with caching
        connector = get_connector(connector_id, table_name)

        if not connector:
            logger.warning(f"Connector {connector_id} not found")
            return create_response(
                404,
                {
                    "status": "error",
                    "message": f"Connector {connector_id} not found",
                },
            )

        bucket = connector.get("storageIdentifier")
        object_prefix = connector.get("objectPrefix", "")

        if not prefix:
            prefix = object_prefix

        if not bucket:
            logger.warning(f"Bucket not configured for connector {connector_id}")
            return create_response(
                400,
                {
                    "status": "error",
                    "message": "Bucket not configured for connector",
                },
            )

        # List S3 objects
        params = {
            "Bucket": bucket,
            "Delimiter": "/",
            "MaxKeys": 1000,
            "Prefix": prefix or "",
        }
        if continuation_token:
            params["ContinuationToken"] = continuation_token

        # Record S3 operation with tracing
        with tracer.provider.in_subsegment("list_s3_objects") as subsegment:
            subsegment.put_annotation("bucket", bucket)
            subsegment.put_annotation("prefix", prefix)

            start_time = time.time()
            response = s3_client.list_objects_v2(**params)
            end_time = time.time()

            # Record the S3 operation latency
            latency = (end_time - start_time) * 1000
            metrics.add_metric(
                name="S3ListObjectsLatency", unit="Milliseconds", value=latency
            )
            logger.info(f"S3 list_objects_v2 latency: {latency}ms")

            # Count objects returned for metrics
            object_count = len(response.get("Contents", []))
            prefix_count = len(response.get("CommonPrefixes", []))
            metrics.add_metric(
                name="S3ObjectsReturned", unit="Count", value=object_count
            )
            metrics.add_metric(
                name="S3PrefixesReturned", unit="Count", value=prefix_count
            )

            subsegment.put_metadata("object_count", object_count)
            subsegment.put_metadata("prefix_count", prefix_count)

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

        response = create_response(
            200,
            {
                "status": "success",
                "message": "Objects retrieved successfully",
                "data": result,
            },
        )
        # Add caching header for frontend
        response["headers"]["Cache-Control"] = "max-age=60"
        return response

    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        error_message = str(e)
        status_code = 400 if "NoSuchBucket" in error_message else 500

        return create_response(
            status_code, {"status": "error", "message": error_message}
        )
