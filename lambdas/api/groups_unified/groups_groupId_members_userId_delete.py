"""DELETE /groups/{groupId}/members/{userId} - Remove member from group"""

from typing import Any, Dict

from aws_lambda_powertools.metrics import MetricUnit
from botocore.exceptions import ClientError
from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    status: str = Field(..., description="Error status code")
    message: str = Field(..., description="Error message")
    data: Dict = Field(default={}, description="Empty data object for errors")


class SuccessResponse(BaseModel):
    status: str = Field(..., description="Success status code")
    message: str = Field(..., description="Success message")
    data: Dict[str, Any] = Field(
        default={}, description="Empty data object for success"
    )


def _remove_group_member(
    dynamodb, table_name: str, group_id: str, user_id: str, logger, metrics
) -> None:
    """
    Remove a member from a group in DynamoDB
    """
    try:
        # Use a transaction to delete both the group membership and the reverse lookup
        transaction_items = [
            {
                "Delete": {
                    "TableName": table_name,
                    "Key": {
                        "PK": f"GROUP#{group_id}",
                        "SK": f"MEMBERSHIP#USER#{user_id}",
                    },
                }
            },
            {
                "Delete": {
                    "TableName": table_name,
                    "Key": {
                        "PK": f"USER#{user_id}",
                        "SK": f"MEMBERSHIP#GROUP#{group_id}",
                    },
                }
            },
        ]

        # Execute the transaction
        dynamodb.meta.client.transact_write_items(TransactItems=transaction_items)

        logger.info(
            f"Removed user from group", extra={"group_id": group_id, "user_id": user_id}
        )

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


def handle_delete_group_member(
    group_id: str, user_id: str, dynamodb, table_name: str, logger, metrics, tracer
) -> Dict[str, Any]:
    """
    Lambda handler to remove a member from a group in DynamoDB
    """
    try:
        if not table_name:
            logger.error("AUTH_TABLE_NAME environment variable not set")
            metrics.add_metric(
                name="MissingConfigError", unit=MetricUnit.Count, value=1
            )
            return _create_error_response(500, "Internal configuration error")

        if not group_id:
            logger.error("Missing groupId in path parameters")
            metrics.add_metric(
                name="MissingGroupIdError", unit=MetricUnit.Count, value=1
            )
            return _create_error_response(400, "Missing group ID")

        if not user_id:
            logger.error("Missing userId in path parameters")
            metrics.add_metric(
                name="MissingUserIdError", unit=MetricUnit.Count, value=1
            )
            return _create_error_response(400, "Missing user ID")

        # Check if the group exists
        table = dynamodb.Table(table_name)
        response = table.get_item(Key={"PK": f"GROUP#{group_id}", "SK": "METADATA"})

        if "Item" not in response:
            logger.error(f"Group not found", extra={"group_id": group_id})
            metrics.add_metric(
                name="GroupNotFoundError", unit=MetricUnit.Count, value=1
            )
            return _create_error_response(404, f"Group with ID {group_id} not found")

        # Check if the user is a member of the group
        response = table.get_item(
            Key={"PK": f"GROUP#{group_id}", "SK": f"MEMBERSHIP#USER#{user_id}"}
        )

        if "Item" not in response:
            logger.error(
                f"User is not a member of the group",
                extra={"group_id": group_id, "user_id": user_id},
            )
            metrics.add_metric(
                name="UserNotMemberError", unit=MetricUnit.Count, value=1
            )
            return _create_error_response(
                404, f"User {user_id} is not a member of group {group_id}"
            )

        # Remove the user from the group
        _remove_group_member(dynamodb, table_name, group_id, user_id, logger, metrics)

        # Create success response
        response = SuccessResponse(
            status="200",
            message="Member removed from group successfully",
            data={"groupId": group_id, "userId": user_id},
        )

        logger.info(
            "Successfully removed member from group",
            extra={"group_id": group_id, "user_id": user_id},
        )
        metrics.add_metric(
            name="SuccessfulMemberRemoval", unit=MetricUnit.Count, value=1
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
