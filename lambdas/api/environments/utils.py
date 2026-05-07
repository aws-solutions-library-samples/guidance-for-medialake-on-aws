import json
import os
from datetime import datetime
from typing import Any, Dict, Optional

from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.event_handler.api_gateway import Response
from botocore.exceptions import ClientError

# Initialize powertools
logger = Logger(service="environments")
metrics = Metrics(namespace=os.environ.get("METRICS_NAMESPACE", "MediaLake"))
tracer = Tracer()


def get_environment_pk(environment_id: str) -> str:
    """Generate the partition key for an environment."""
    return f"ENV#{environment_id}"


def get_environment_sk() -> str:
    """Generate the sort key for an environment."""
    return "METADATA"


def format_environment(item: Dict[str, Any]) -> Dict[str, Any]:
    """Format a DynamoDB item into an environment response."""
    pk = item.get("PK", "")
    environment_id = pk.replace("ENV#", "") if pk.startswith("ENV#") else pk

    return {
        "environment_id": environment_id,
        "name": item.get("name"),
        "status": item.get("status"),
        "region": item.get("region"),
        "tags": item.get("tags", {}),
        "created_at": item.get("createdAt"),
        "updated_at": item.get("updatedAt"),
    }


def create_error_response(
    status_code: int, message: str, correlation_id: Optional[str] = None
) -> Response:
    """Create a standardized error response."""
    body = {
        "status": status_code,
        "message": message,
    }
    if correlation_id:
        body["correlation_id"] = correlation_id

    return Response(
        status_code=status_code, content_type="application/json", body=json.dumps(body)
    )


def create_success_response(
    status_code: int, data: Dict[str, Any], message: str = "ok"
) -> Response:
    """Create a standardized success response."""
    return Response(
        status_code=status_code,
        content_type="application/json",
        body=json.dumps({"status": status_code, "message": message, "data": data}),
    )


def get_current_time() -> str:
    """Get current time in ISO format."""
    return datetime.utcnow().isoformat()


def setup_logging(level: Optional[str] = None) -> None:
    """Set up logging with the specified level."""
    log_level = level or os.environ.get("LOG_LEVEL", "WARNING")
    logger.setLevel(log_level)


@tracer.capture_method
def handle_dynamodb_error(
    error: ClientError, environment_id: Optional[str] = None
) -> Response:
    """Handle DynamoDB errors and return appropriate responses."""
    error_code = error.response["Error"]["Code"]
    error_message = error.response["Error"]["Message"]

    logger.error(
        f"DynamoDB error: {error_code} - {error_message}",
        extra={"environment_id": environment_id},
    )

    if error_code == "ConditionalCheckFailedException":
        return create_error_response(
            409,
            (
                "Environment already exists"
                if not environment_id
                else "Environment has been modified"
            ),
        )
    elif error_code == "ResourceNotFoundException":
        return create_error_response(404, "Environment not found")
    else:
        return create_error_response(500, "Internal server error")
