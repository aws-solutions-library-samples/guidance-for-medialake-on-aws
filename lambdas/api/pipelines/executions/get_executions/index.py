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

# Initialize Powertools
logger = Logger()
tracer = Tracer()
metrics = Metrics(namespace="Pipelines")
# app = APIGatewayRestResolver()


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
DEFAULT_PAGE = 1


class PipelineExecutionError(Exception):
    """Custom exception for pipeline execution errors"""

    pass


@tracer.capture_method
def get_pipeline_executions(page: int, page_size: int) -> Dict[str, Any]:
    """
    Retrieve paginated pipeline executions from DynamoDB

    Args:
        page: Page number (1-based)
        page_size: Number of items per page

    Returns:
        Dict containing status, message, and paginated pipeline executions data

    Raises:
        PipelineExecutionError: When DynamoDB operations fail
    """
    try:
        # Calculate pagination parameters
        start_key = None
        if page > 1:
            # Skip previous pages
            for _ in range(page - 1):
                scan_params = {"Limit": page_size}
                if start_key:
                    scan_params["ExclusiveStartKey"] = start_key

                response = table.scan(**scan_params)
                start_key = response.get("LastEvaluatedKey")
                if not start_key:
                    break

        # Get items for current page
        scan_params = {"Limit": page_size}
        if start_key:
            scan_params["ExclusiveStartKey"] = start_key

        response = table.scan(**scan_params)
        executions = response.get("Items", [])

        # Get total count
        count_response = table.scan(Select="COUNT")
        total_count = count_response.get("Count", 0)

        # Add metrics for monitoring
        metrics.add_metric(name="SuccessfulQueries", unit="Count", value=1)

        return {
            "status": "200",
            "message": "ok",
            "data": {
                "searchMetadata": {
                    "totalResults": total_count,
                    "page": page,
                    "pageSize": page_size,
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
            page = int(query_string.get("page", DEFAULT_PAGE))
            page_size = int(query_string.get("pageSize", DEFAULT_PAGE_SIZE))
        except (ValueError, TypeError):
            page = DEFAULT_PAGE
            page_size = DEFAULT_PAGE_SIZE

        # Validate pagination parameters
        page = max(1, page)  # Ensure page is at least 1
        page_size = max(1, min(100, page_size))  # Limit page size between 1 and 100

        return get_pipeline_executions(page, page_size)
    except PipelineExecutionError as e:
        logger.exception("Error processing pipeline executions request")
        return {
            "status": "500",
            "message": str(e),
            "data": {
                "searchMetadata": {
                    "totalResults": 0,
                    "page": 1,
                    "pageSize": DEFAULT_PAGE_SIZE,
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
                        "page": 1,
                        "pageSize": DEFAULT_PAGE_SIZE,
                    },
                    "executions": [],
                },
            },
        }
