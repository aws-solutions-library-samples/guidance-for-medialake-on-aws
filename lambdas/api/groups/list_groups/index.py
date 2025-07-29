import json
import os
from typing import Any, Dict, List

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.typing import LambdaContext
from boto3.dynamodb.conditions import Attr
from botocore.exceptions import ClientError
from pydantic import BaseModel, Field

# Initialize AWS PowerTools
logger = Logger(
    service="authorization-service", level=os.getenv("LOG_LEVEL", "WARNING")
)
tracer = Tracer(service="authorization-service")
metrics = Metrics(namespace="medialake", service="groups-list")

# Initialize DynamoDB client
dynamodb = boto3.resource("dynamodb")


class ErrorResponse(BaseModel):
    status: str = Field(..., description="Error status code")
    message: str = Field(..., description="Error message")
    data: Dict = Field(default={}, description="Empty data object for errors")


class GroupsResponse(BaseModel):
    status: str = Field(..., description="Success status code")
    message: str = Field(..., description="Success message")
    data: Dict[str, Any] = Field(..., description="Groups data")


@tracer.capture_lambda_handler
@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """
    Lambda handler to list all groups from DynamoDB
    """
    try:
        # Log the entire event structure for debugging
        logger.info("Received event", extra={"event": json.dumps(event)})

        # Extract user ID from Cognito authorizer context
        request_context = event.get("requestContext", {})
        logger.info(
            "Request context", extra={"request_context": json.dumps(request_context)}
        )

        authorizer = request_context.get("authorizer", {})
        logger.info("Authorizer context", extra={"authorizer": json.dumps(authorizer)})

        claims = authorizer.get("claims", {})
        logger.info("Claims", extra={"claims": json.dumps(claims)})

        # Get the user ID from the Cognito claims or directly from the authorizer context
        user_id = claims.get("sub")

        # If not found in claims, try to get it directly from the authorizer context
        if not user_id:
            user_id = authorizer.get("userId")
            logger.info(
                "Using userId from authorizer context", extra={"user_id": user_id}
            )
        else:
            logger.info("Using sub from claims", extra={"user_id": user_id})

        if not user_id:
            logger.error(
                "Missing user_id in both Cognito claims and authorizer context"
            )
            metrics.add_metric(
                name="MissingUserIdError", unit=MetricUnit.Count, value=1
            )
            return _create_error_response(
                400,
                "Unable to identify user - missing from both claims and authorizer context",
            )

        # Get the auth table name from environment variable
        auth_table_name = os.getenv("AUTH_TABLE_NAME")
        if not auth_table_name:
            logger.error("AUTH_TABLE_NAME environment variable not set")
            metrics.add_metric(
                name="MissingConfigError", unit=MetricUnit.Count, value=1
            )
            return _create_error_response(500, "Internal configuration error")

        # Get query parameters
        query_string_parameters = event.get("queryStringParameters", {}) or {}

        # Fetch groups from DynamoDB
        groups = _list_groups(auth_table_name, query_string_parameters)

        # Create success response
        response = GroupsResponse(
            status="200",
            message="Groups retrieved successfully",
            data={"groups": groups},
        )

        logger.info("Successfully retrieved groups", extra={"count": len(groups)})
        metrics.add_metric(
            name="SuccessfulGroupsLookup", unit=MetricUnit.Count, value=1
        )

        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": response.model_dump_json(),
        }

    except Exception as e:
        logger.exception("Error processing request")
        metrics.add_metric(name="UnhandledError", unit=MetricUnit.Count, value=1)
        return _create_error_response(500, f"Internal server error: {str(e)}")


@tracer.capture_method
def _list_groups(table_name: str, query_params: Dict[str, str]) -> List[Dict[str, Any]]:
    """
    List all groups from DynamoDB using a scan operation with a filter expression
    to find all items where PK begins with "GROUP#" and SK equals "METADATA"
    """
    try:
        table = dynamodb.Table(table_name)

        # Use scan with filter expression to find all group items
        # This is more efficient than using a GSI when we have a known prefix pattern
        response = table.scan(
            FilterExpression=Attr("PK").begins_with("GROUP#")
            & Attr("SK").eq("METADATA")
        )

        items = response.get("Items", [])

        # Process pagination if there are more results
        while "LastEvaluatedKey" in response:
            response = table.scan(
                FilterExpression=Attr("PK").begins_with("GROUP#")
                & Attr("SK").eq("METADATA"),
                ExclusiveStartKey=response["LastEvaluatedKey"],
            )
            items.extend(response.get("Items", []))

        # Log the number of items found
        logger.info(f"Found {len(items)} group items in DynamoDB")

        # Transform the items to remove DynamoDB-specific attributes
        groups = []
        for item in items:
            group = {
                "id": item.get("id"),
                "name": item.get("name"),
                "description": item.get("description"),
                "createdBy": item.get("createdBy"),
                "createdAt": item.get("createdAt"),
                "updatedAt": item.get("updatedAt"),
                # Include any additional fields that might be useful
                "department": item.get("department"),
            }
            # Remove None values
            group = {k: v for k, v in group.items() if v is not None}
            groups.append(group)

        return groups

    except ClientError as e:
        logger.error(f"DynamoDB error", extra={"error": str(e)})
        metrics.add_metric(name="DynamoDBError", unit=MetricUnit.Count, value=1)
        raise


def _create_error_response(status_code: int, message: str) -> Dict[str, Any]:
    """
    Create standardized error response
    """
    error_response = ErrorResponse(status=str(status_code), message=message, data={})

    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": error_response.model_dump_json(),
    }
