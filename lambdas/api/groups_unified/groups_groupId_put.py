"""PUT /groups/{groupId} - Update group details"""

from datetime import datetime
from typing import Any, Dict, Optional

from aws_lambda_powertools.metrics import MetricUnit
from botocore.exceptions import ClientError
from pydantic import BaseModel, Field, validator


class GroupUpdateRequest(BaseModel):
    """Model for group update request"""

    name: Optional[str] = Field(None, description="Name of the group")
    description: Optional[str] = Field(None, description="Description of the group")

    @validator("name")
    def name_not_empty(cls, v):
        if v is not None and not v.strip():
            raise ValueError("name cannot be empty")
        return v


class ErrorResponse(BaseModel):
    status: str = Field(..., description="Error status code")
    message: str = Field(..., description="Error message")
    data: Dict = Field(default={}, description="Empty data object for errors")


class GroupResponse(BaseModel):
    status: str = Field(..., description="Success status code")
    message: str = Field(..., description="Success message")
    data: Dict[str, Any] = Field(..., description="Updated group data")


def _update_group(
    dynamodb,
    table_name: str,
    group_id: str,
    group_update_request: GroupUpdateRequest,
    updated_by: str,
    logger,
    metrics,
) -> Dict[str, Any]:
    """
    Update a group in DynamoDB
    """
    try:
        table = dynamodb.Table(table_name)

        # Get the current timestamp
        current_time = datetime.utcnow().isoformat()

        # Build the update expression and attribute values
        update_expression_parts = ["SET updatedAt = :updatedAt"]
        expression_attribute_values = {":updatedAt": current_time}

        if group_update_request.name is not None:
            update_expression_parts.append("name = :name")
            expression_attribute_values[":name"] = group_update_request.name

        if group_update_request.description is not None:
            update_expression_parts.append("description = :description")
            expression_attribute_values[":description"] = (
                group_update_request.description
            )

        update_expression = ", ".join(update_expression_parts)

        # Update the item in DynamoDB
        response = table.update_item(
            Key={"PK": f"GROUP#{group_id}", "SK": "METADATA"},
            UpdateExpression=update_expression,
            ExpressionAttributeValues=expression_attribute_values,
            ReturnValues="ALL_NEW",
        )

        updated_item = response.get("Attributes", {})

        # Return the updated group (without the DynamoDB-specific keys)
        result = {
            "id": updated_item.get("id"),
            "name": updated_item.get("name"),
            "description": updated_item.get("description"),
            "createdBy": updated_item.get("createdBy"),
            "createdAt": updated_item.get("createdAt"),
            "updatedAt": updated_item.get("updatedAt"),
        }

        return result

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


def handle_put_group(
    group_id: str, app, dynamodb, table_name: str, logger, metrics, tracer
) -> Dict[str, Any]:
    """
    Lambda handler to update a group in DynamoDB
    """
    try:
        # Extract user ID from Cognito authorizer context
        request_context = app.current_event.raw_event.get("requestContext", {})
        authorizer = request_context.get("authorizer", {})
        claims = authorizer.get("claims", {})

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

        # Parse the request body
        try:
            body = app.current_event.json_body
            group_update_request = GroupUpdateRequest(**body)
        except Exception as e:
            logger.error(f"Invalid request body: {str(e)}")
            metrics.add_metric(
                name="InvalidRequestError", unit=MetricUnit.Count, value=1
            )
            return _create_error_response(400, f"Invalid request: {str(e)}")

        # Check if the group exists
        table = dynamodb.Table(table_name)
        response = table.get_item(Key={"PK": f"GROUP#{group_id}", "SK": "METADATA"})

        if "Item" not in response:
            logger.error(f"Group not found", extra={"group_id": group_id})
            metrics.add_metric(
                name="GroupNotFoundError", unit=MetricUnit.Count, value=1
            )
            return _create_error_response(404, f"Group with ID {group_id} not found")

        # Update the group in DynamoDB
        updated_group = _update_group(
            dynamodb, table_name, group_id, group_update_request, user_id, logger, metrics
        )

        # Create success response
        response = GroupResponse(
            status="200",
            message="Group updated successfully",
            data=updated_group,
        )

        logger.info("Successfully updated group", extra={"group_id": group_id})
        metrics.add_metric(name="SuccessfulGroupUpdate", unit=MetricUnit.Count, value=1)

        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": response.model_dump_json(),
        }

    except Exception as e:
        logger.exception("Error processing request")
        metrics.add_metric(name="UnhandledError", unit=MetricUnit.Count, value=1)
        return _create_error_response(500, f"Internal server error: {str(e)}")

