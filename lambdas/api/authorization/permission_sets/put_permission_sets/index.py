import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

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
metrics = Metrics(namespace="medialake", service="permission-set-update")

# Initialize DynamoDB client
dynamodb = boto3.resource("dynamodb")


class Permission(BaseModel):
    """Model for a permission within a permission set"""

    action: str = Field(
        ...,
        description="The action to be performed (e.g., 'create', 'read', 'update', 'delete')",
    )
    resource: str = Field(
        ...,
        description="The resource type the action applies to (e.g., 'Asset', 'Pipeline')",
    )
    effect: str = Field(
        ..., description="Whether to allow or deny the permission ('Allow' or 'Deny')"
    )
    conditions: Optional[Dict[str, Any]] = Field(
        default=None, description="Optional conditions for the permission"
    )


class PermissionSetUpdateRequest(BaseModel):
    """Model for permission set update request"""

    name: str = Field(..., description="Name of the permission set")
    description: str = Field(..., description="Description of the permission set")
    permissions: List[Permission] = Field(
        ..., description="List of permissions in this set"
    )

    @validator("name")
    def name_not_empty(cls, v):
        if not v.strip():
            raise ValueError("name cannot be empty")
        return v


class ErrorResponse(BaseModel):
    status: str = Field(..., description="Error status code")
    message: str = Field(..., description="Error message")
    data: Dict = Field(default={}, description="Empty data object for errors")


class PermissionSetResponse(BaseModel):
    status: str = Field(..., description="Success status code")
    message: str = Field(..., description="Success message")
    data: Dict[str, Any] = Field(..., description="Updated permission set data")


@tracer.capture_lambda_handler
@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """
    Lambda handler to update a permission set in DynamoDB
    """
    try:
        # Extract user ID from Cognito authorizer context
        request_context = event.get("requestContext", {})
        authorizer = request_context.get("authorizer", {})
        claims = authorizer.get("claims", {})

        # Get the user ID from the Cognito claims
        user_id = claims.get("sub")

        if not user_id:
            logger.error("Missing user_id in Cognito claims")
            metrics.add_metric(
                name="MissingUserIdError", unit=MetricUnit.Count, value=1
            )
            return _create_error_response(400, "Unable to identify user")

        # Get the auth table name from environment variable
        auth_table_name = os.getenv("AUTH_TABLE_NAME")
        if not auth_table_name:
            logger.error("AUTH_TABLE_NAME environment variable not set")
            metrics.add_metric(
                name="MissingConfigError", unit=MetricUnit.Count, value=1
            )
            return _create_error_response(500, "Internal configuration error")

        # Get the permission set ID from the path parameters
        path_parameters = event.get("pathParameters", {}) or {}
        permission_set_id = path_parameters.get("permissionSetId")

        if not permission_set_id:
            logger.error("Missing permissionSetId in path parameters")
            metrics.add_metric(
                name="MissingParameterError", unit=MetricUnit.Count, value=1
            )
            return _create_error_response(400, "Missing permission set ID")

        # Parse the request body
        try:
            body = json.loads(event.get("body", "{}"))
            permission_set_update = PermissionSetUpdateRequest(**body)
        except Exception as e:
            logger.error(f"Invalid request body: {str(e)}")
            metrics.add_metric(
                name="InvalidRequestError", unit=MetricUnit.Count, value=1
            )
            return _create_error_response(400, f"Invalid request: {str(e)}")

        # Check if the permission set exists and is not a system permission set
        existing_permission_set = _get_permission_set(
            auth_table_name, permission_set_id
        )

        if not existing_permission_set:
            logger.warning(
                f"Permission set not found",
                extra={"permission_set_id": permission_set_id},
            )
            metrics.add_metric(
                name="PermissionSetNotFound", unit=MetricUnit.Count, value=1
            )
            return _create_error_response(
                404, f"Permission set with ID {permission_set_id} not found"
            )

        # Prevent modification of system permission sets
        if existing_permission_set.get("isSystem", False):
            logger.warning(
                f"Attempted to modify system permission set",
                extra={"permission_set_id": permission_set_id},
            )
            metrics.add_metric(
                name="SystemPermissionSetModificationAttempt",
                unit=MetricUnit.Count,
                value=1,
            )
            return _create_error_response(403, "Cannot modify system permission sets")

        # Update the permission set in DynamoDB
        updated_permission_set = _update_permission_set(
            auth_table_name, permission_set_id, permission_set_update, user_id
        )

        # Create success response
        response = PermissionSetResponse(
            status="200",
            message="Permission set updated successfully",
            data=updated_permission_set,
        )

        logger.info(
            "Successfully updated permission set",
            extra={"permission_set_id": permission_set_id},
        )
        metrics.add_metric(
            name="SuccessfulPermissionSetUpdate", unit=MetricUnit.Count, value=1
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
def _get_permission_set(
    table_name: str, permission_set_id: str
) -> Optional[Dict[str, Any]]:
    """
    Get a specific permission set from DynamoDB
    """
    try:
        table = dynamodb.Table(table_name)

        # Get the permission set using the primary key
        response = table.get_item(
            Key={"PK": f"PS#{permission_set_id}", "SK": "METADATA"}
        )

        # Check if the item exists
        if "Item" not in response:
            return None

        return response["Item"]

    except ClientError as e:
        logger.error(f"DynamoDB error", extra={"error": str(e)})
        metrics.add_metric(name="DynamoDBError", unit=MetricUnit.Count, value=1)
        raise


@tracer.capture_method
def _update_permission_set(
    table_name: str,
    permission_set_id: str,
    permission_set_update: PermissionSetUpdateRequest,
    updated_by: str,
) -> Dict[str, Any]:
    """
    Update an existing permission set in DynamoDB
    """
    try:
        # Get the current timestamp
        current_time = datetime.utcnow().isoformat()

        table = dynamodb.Table(table_name)

        # Update the DynamoDB item
        response = table.update_item(
            Key={"PK": f"PS#{permission_set_id}", "SK": "METADATA"},
            UpdateExpression="SET #name = :name, #description = :description, #permissions = :permissions, #updatedAt = :updatedAt, #updatedBy = :updatedBy",
            ExpressionAttributeNames={
                "#name": "name",
                "#description": "description",
                "#permissions": "permissions",
                "#updatedAt": "updatedAt",
                "#updatedBy": "updatedBy",
            },
            ExpressionAttributeValues={
                ":name": permission_set_update.name,
                ":description": permission_set_update.description,
                ":permissions": [p.dict() for p in permission_set_update.permissions],
                ":updatedAt": current_time,
                ":updatedBy": updated_by,
            },
            ReturnValues="ALL_NEW",
        )

        # Get the updated item
        updated_item = response.get("Attributes", {})

        # Transform the item to remove DynamoDB-specific attributes
        permission_set = {
            "id": updated_item.get("id"),
            "name": updated_item.get("name"),
            "description": updated_item.get("description"),
            "permissions": updated_item.get("permissions", []),
            "isSystem": updated_item.get("isSystem", False),
            "createdBy": updated_item.get("createdBy"),
            "createdAt": updated_item.get("createdAt"),
            "updatedAt": updated_item.get("updatedAt"),
            "updatedBy": updated_item.get("updatedBy"),
        }

        return permission_set

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
