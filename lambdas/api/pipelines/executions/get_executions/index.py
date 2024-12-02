import boto3
import os
import json
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.event_handler import APIGatewayRestResolver
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.utilities.data_classes import APIGatewayProxyEvent
from aws_lambda_powertools.utilities.data_classes.common import BaseProxyEvent
from aws_lambda_powertools.event_handler.api_gateway import CORSConfig
from typing import Dict, Any, List
from botocore.exceptions import ClientError
from aws_lambda_powertools.metrics import Metrics
from urllib.parse import parse_qs
import base64

# Initialize Powertools
logger = Logger()
tracer = Tracer()
metrics = Metrics(namespace="Pipelines")

# Configure CORS
cors_config = CORSConfig(
    allow_origin="*",
    allow_headers=[
        "Content-Type",
        "X-Amz-Date",
        "Authorization",
        "X-Api-Key",
        "X-Amz-Security-Token",
    ],
)

app = APIGatewayRestResolver(
    serializer=lambda x: json.dumps(x, default=str),
    strip_prefixes=["/api"],
    cors=cors_config,
)

# Initialize DynamoDB client
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["PIPELINES_EXECUTIONS_TABLE_NAME"])

# Default pagination values
DEFAULT_PAGE_SIZE = 20


class PipelineExecutionError(Exception):
    """Custom exception for pipeline execution errors"""

    pass


def encode_last_evaluated_key(last_evaluated_key: Dict) -> str:
    """Encode the LastEvaluatedKey to a base64 string"""
    if not last_evaluated_key:
        return ""
    return base64.b64encode(json.dumps(last_evaluated_key).encode()).decode()


def decode_last_evaluated_key(encoded_key: str) -> Dict:
    """Decode the base64 string back to LastEvaluatedKey"""
    if not encoded_key:
        return None
    try:
        return json.loads(base64.b64decode(encoded_key.encode()).decode())
    except:
        return None


@tracer.capture_method
def get_pipeline_executions(
    page_size: int, next_token: str = None, status: str = None
) -> Dict[str, Any]:
    """
    Retrieve paginated pipeline executions from DynamoDB using Scan operation with filtering

    Args:
        page_size: Number of items per page
        next_token: Base64 encoded LastEvaluatedKey for pagination
        status: Optional status filter

    Returns:
        Dict containing status, message, and paginated pipeline executions data
    """
    try:
        # Base scan parameters
        scan_params = {"Limit": page_size}

        # Add status filter if provided
        if status:
            scan_params.update(
                {
                    "FilterExpression": "#status = :status",
                    "ExpressionAttributeNames": {"#status": "status"},
                    "ExpressionAttributeValues": {":status": status},
                }
            )

        # Add LastEvaluatedKey if next_token is provided
        if next_token:
            last_evaluated_key = decode_last_evaluated_key(next_token)
            if last_evaluated_key:
                scan_params["ExclusiveStartKey"] = last_evaluated_key

        # Execute scan
        response = table.scan(**scan_params)
        executions = response.get("Items", [])

        # Sort executions by start_time in descending order
        executions.sort(key=lambda x: x.get("start_time", ""), reverse=True)

        # Get the next token for pagination
        next_token = None
        if "LastEvaluatedKey" in response:
            next_token = encode_last_evaluated_key(response["LastEvaluatedKey"])

        # Add metrics for monitoring
        metrics.add_metric(name="SuccessfulQueries", unit="Count", value=1)

        return {
            "status": "200",
            "message": "ok",
            "data": {
                "searchMetadata": {
                    "totalResults": response.get("Count", 0),
                    "pageSize": page_size,
                    "nextToken": next_token,
                },
                "executions": executions,
            },
        }

    except ClientError as e:
        logger.exception("Failed to retrieve pipeline executions")
        metrics.add_metric(name="FailedQueries", unit="Count", value=1)
        raise PipelineExecutionError(
            f"Failed to retrieve pipeline executions: {str(e)}"
        )


@app.get("/pipelines/executions")
@tracer.capture_method
def handle_get_executions() -> Dict[str, Any]:
    """
    Handle GET request for pipeline executions with pagination

    Returns:
        Dict containing response with paginated pipeline executions
    """
    try:
        # Get query parameters
        query_string = app.current_event.query_string_parameters or {}

        # Parse pagination parameters
        try:
            page_size = int(query_string.get("pageSize", DEFAULT_PAGE_SIZE))
            page_size = max(1, min(100, page_size))  # Limit page size between 1 and 100
        except (ValueError, TypeError):
            page_size = DEFAULT_PAGE_SIZE

        # Get the next token for pagination
        next_token = query_string.get("nextToken")

        # Get status filter if provided
        status = query_string.get("status")

        return get_pipeline_executions(page_size, next_token, status)
    except PipelineExecutionError as e:
        logger.exception("Error processing pipeline executions request")
        return {
            "status": "500",
            "message": str(e),
            "data": {
                "searchMetadata": {
                    "totalResults": 0,
                    "pageSize": DEFAULT_PAGE_SIZE,
                    "nextToken": None,
                },
                "executions": [],
            },
        }


@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(
    event: APIGatewayProxyEvent, context: LambdaContext
) -> Dict[str, Any]:
    """
    Main Lambda handler

    Args:
        event: API Gateway event
        context: Lambda context

    Returns:
        API Gateway response
    """
    try:
        return app.resolve(event, context)
    except Exception as e:
        logger.exception("Error in lambda handler")
        return {
            "statusCode": 500,
            "body": {
                "status": "500",
                "message": "Internal server error",
                "data": {
                    "searchMetadata": {
                        "totalResults": 0,
                        "pageSize": DEFAULT_PAGE_SIZE,
                        "nextToken": None,
                    },
                    "executions": [],
                },
            },
        }
