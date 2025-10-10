"""GET /groups/{groupId} - Get group details"""

from typing import Any, Dict, List, Optional

from aws_lambda_powertools.metrics import MetricUnit
from botocore.exceptions import ClientError
from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    status: str = Field(..., description="Error status code")
    message: str = Field(..., description="Error message")
    data: Dict = Field(default={}, description="Empty data object for errors")


class GroupResponse(BaseModel):
    status: str = Field(..., description="Success status code")
    message: str = Field(..., description="Success message")
    data: Dict[str, Any] = Field(..., description="Group data")


def _get_group_members(
    table, group_id: str, logger, metrics
) -> List[Dict[str, Any]]:
    """
    Get all members of a group
    """
    try:
        # Query for all items with PK=GROUP#{group_id} and SK starting with MEMBERSHIP#USER#
        response = table.query(
            KeyConditionExpression="PK = :pk AND begins_with(SK, :sk_prefix)",
            ExpressionAttributeValues={
                ":pk": f"GROUP#{group_id}",
                ":sk_prefix": "MEMBERSHIP#USER#",
            },
        )

        items = response.get("Items", [])

        # Process pagination if there are more results
        while "LastEvaluatedKey" in response:
            response = table.query(
                KeyConditionExpression="PK = :pk AND begins_with(SK, :sk_prefix)",
                ExpressionAttributeValues={
                    ":pk": f"GROUP#{group_id}",
                    ":sk_prefix": "MEMBERSHIP#USER#",
                },
                ExclusiveStartKey=response["LastEvaluatedKey"],
            )
            items.extend(response.get("Items", []))

        # Extract user IDs from the membership items
        members = []
        for item in items:
            # SK format is "MEMBERSHIP#USER#{userId}"
            sk_parts = item.get("SK", "").split("#")
            if len(sk_parts) >= 3:
                user_id = sk_parts[2]
                members.append({"userId": user_id, "addedAt": item.get("addedAt")})

        return members

    except ClientError as e:
        logger.error(f"DynamoDB error getting group members", extra={"error": str(e)})
        metrics.add_metric(name="DynamoDBMembersError", unit=MetricUnit.Count, value=1)
        raise


def _get_group(dynamodb, table_name: str, group_id: str, logger, metrics) -> Optional[Dict[str, Any]]:
    """
    Get a specific group from DynamoDB
    """
    try:
        table = dynamodb.Table(table_name)

        # Get the group item from DynamoDB
        response = table.get_item(Key={"PK": f"GROUP#{group_id}", "SK": "METADATA"})

        item = response.get("Item")

        if not item:
            return None

        # Transform the item to remove DynamoDB-specific attributes
        group = {
            "id": item.get("id"),
            "name": item.get("name"),
            "description": item.get("description"),
            "createdBy": item.get("createdBy"),
            "createdAt": item.get("createdAt"),
            "updatedAt": item.get("updatedAt"),
        }

        # Get the group members
        members = _get_group_members(table, group_id, logger, metrics)
        group["members"] = members

        return group

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


def handle_get_group(
    group_id: str, dynamodb, table_name: str, logger, metrics, tracer
) -> Dict[str, Any]:
    """
    Lambda handler to get a specific group from DynamoDB
    """
    try:
        if not group_id:
            logger.error("Missing groupId in path parameters")
            metrics.add_metric(
                name="MissingGroupIdError", unit=MetricUnit.Count, value=1
            )
            return _create_error_response(400, "Missing group ID")

        if not table_name:
            logger.error("AUTH_TABLE_NAME environment variable not set")
            metrics.add_metric(
                name="MissingConfigError", unit=MetricUnit.Count, value=1
            )
            return _create_error_response(500, "Internal configuration error")

        # Get the group from DynamoDB
        group = _get_group(dynamodb, table_name, group_id, logger, metrics)

        if not group:
            logger.error(f"Group not found", extra={"group_id": group_id})
            metrics.add_metric(
                name="GroupNotFoundError", unit=MetricUnit.Count, value=1
            )
            return _create_error_response(404, f"Group with ID {group_id} not found")

        # Create success response
        response = GroupResponse(
            status="200",
            message="Group retrieved successfully",
            data=group,
        )

        logger.info("Successfully retrieved group", extra={"group_id": group_id})
        metrics.add_metric(name="SuccessfulGroupLookup", unit=MetricUnit.Count, value=1)

        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": response.model_dump_json(),
        }

    except Exception as e:
        logger.exception("Error processing request")
        metrics.add_metric(name="UnhandledError", unit=MetricUnit.Count, value=1)
        return _create_error_response(500, f"Internal server error: {str(e)}")

