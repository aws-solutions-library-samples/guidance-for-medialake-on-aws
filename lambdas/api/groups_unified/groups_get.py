"""GET /groups - List all groups"""

from typing import Any, Dict, List

from aws_lambda_powertools.metrics import MetricUnit
from boto3.dynamodb.conditions import Attr
from botocore.exceptions import ClientError
from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    status: str = Field(..., description="Error status code")
    message: str = Field(..., description="Error message")
    data: Dict = Field(default={}, description="Empty data object for errors")


class GroupsResponse(BaseModel):
    status: str = Field(..., description="Success status code")
    message: str = Field(..., description="Success message")
    data: Dict[str, Any] = Field(..., description="Groups data")


def _list_groups(dynamodb, table_name: str, query_params: Dict[str, str], logger, metrics) -> List[Dict[str, Any]]:
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


def handle_get_groups(app, dynamodb, table_name: str, logger, metrics, tracer) -> Dict[str, Any]:
    """
    Lambda handler to list all groups from DynamoDB
    """
    try:
        # Extract user ID from Cognito authorizer context
        request_context = app.current_event.raw_event.get("requestContext", {})
        authorizer = request_context.get("authorizer", {})

        # Get the user ID directly from the authorizer context
        user_id = authorizer.get("userId")

        # Try claims if not found in authorizer
        if not user_id:
            claims = authorizer.get("claims", {})
            user_id = claims.get("sub") if isinstance(claims, dict) else None

        if not user_id:
            logger.error("Missing user_id in authorizer context")
            metrics.add_metric(
                name="MissingUserIdError", unit=MetricUnit.Count, value=1
            )
            return _create_error_response(400, "Unable to identify user")

        if not table_name:
            logger.error("AUTH_TABLE_NAME environment variable not set")
            metrics.add_metric(
                name="MissingConfigError", unit=MetricUnit.Count, value=1
            )
            return _create_error_response(500, "Internal configuration error")

        # Get query parameters
        query_string_parameters = app.current_event.query_string_parameters or {}

        # Fetch groups from DynamoDB
        groups = _list_groups(dynamodb, table_name, query_string_parameters, logger, metrics)

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

