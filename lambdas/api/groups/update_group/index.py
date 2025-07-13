import json
import os
from datetime import datetime
from typing import Any, Dict, Optional

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.typing import LambdaContext
from botocore.exceptions import ClientError
from pydantic import BaseModel, Field, validator

# Initialize AWS PowerTools
logger = Logger(
    service="authorization-service", level=os.getenv("LOG_LEVEL", "WARNING")
)
tracer = Tracer(service="authorization-service")
metrics = Metrics(namespace="medialake", service="groups-update")

# Initialize DynamoDB client
dynamodb = boto3.resource("dynamodb")


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


@tracer.capture_lambda_handler
@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """
    Lambda handler to update a group in DynamoDB
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

        # Get the group ID from path parameters
        path_parameters = event.get("pathParameters", {})
        if not path_parameters:
            logger.error("Missing path parameters")
            metrics.add_metric(
                name="MissingPathParamsError", unit=MetricUnit.Count, value=1
            )
            return _create_error_response(400, "Missing group ID")

        group_id = path_parameters.get("groupId")
        if not group_id:
            logger.error("Missing groupId in path parameters")
            metrics.add_metric(
                name="MissingGroupIdError", unit=MetricUnit.Count, value=1
            )
            return _create_error_response(400, "Missing group ID")

        # Parse the request body
        try:
            body = json.loads(event.get("body", "{}"))
            group_update_request = GroupUpdateRequest(**body)
        except Exception as e:
            logger.error(f"Invalid request body: {str(e)}")
            metrics.add_metric(
                name="InvalidRequestError", unit=MetricUnit.Count, value=1
            )
            return _create_error_response(400, f"Invalid request: {str(e)}")

        # Check if the group exists
        table = dynamodb.Table(auth_table_name)
        response = table.get_item(Key={"PK": f"GROUP#{group_id}", "SK": "METADATA"})

        if "Item" not in response:
            logger.error(f"Group not found", extra={"group_id": group_id})
            metrics.add_metric(
                name="GroupNotFoundError", unit=MetricUnit.Count, value=1
            )
            return _create_error_response(404, f"Group with ID {group_id} not found")

        # Update the group in DynamoDB
        updated_group = _update_group(
            auth_table_name, group_id, group_update_request, user_id
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


@tracer.capture_method
def _update_group(
    table_name: str,
    group_id: str,
    group_update_request: GroupUpdateRequest,
    updated_by: str,
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
