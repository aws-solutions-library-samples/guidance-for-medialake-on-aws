import json
import os
from typing import Any, Dict, Optional

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.typing import LambdaContext
from botocore.exceptions import ClientError
from pydantic import BaseModel, Field

# Initialize AWS PowerTools
logger = Logger(
    service="authorization-service", level=os.getenv("LOG_LEVEL", "WARNING")
)
tracer = Tracer(service="authorization-service")
metrics = Metrics(namespace="medialake", service="permission-set-delete")

# Initialize DynamoDB client
dynamodb = boto3.resource("dynamodb")


class ErrorResponse(BaseModel):
    status: str = Field(..., description="Error status code")
    message: str = Field(..., description="Error message")
    data: Dict = Field(default={}, description="Empty data object for errors")


class DeleteResponse(BaseModel):
    status: str = Field(..., description="Success status code")
    message: str = Field(..., description="Success message")
    data: Dict[str, Any] = Field(
        default={}, description="Empty data object for success"
    )


@tracer.capture_lambda_handler
@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """
    Lambda handler to delete a permission set from DynamoDB
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

        # Get the permission set ID from the path parameters
        path_parameters = event.get("pathParameters", {}) or {}
        permission_set_id = path_parameters.get("permissionSetId")

        if not permission_set_id:
            logger.error("Missing permissionSetId in path parameters")
            metrics.add_metric(
                name="MissingParameterError", unit=MetricUnit.Count, value=1
            )
            return _create_error_response(400, "Missing permission set ID")

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

        # Prevent deletion of system permission sets
        if existing_permission_set.get("isSystem", False):
            logger.warning(
                f"Attempted to delete system permission set",
                extra={"permission_set_id": permission_set_id},
            )
            metrics.add_metric(
                name="SystemPermissionSetDeletionAttempt",
                unit=MetricUnit.Count,
                value=1,
            )
            return _create_error_response(403, "Cannot delete system permission sets")

        # Delete the permission set from DynamoDB
        _delete_permission_set(auth_table_name, permission_set_id)

        # Create success response
        response = DeleteResponse(
            status="200",
            message=f"Permission set {permission_set_id} deleted successfully",
            data={},
        )

        logger.info(
            "Successfully deleted permission set",
            extra={"permission_set_id": permission_set_id},
        )
        metrics.add_metric(
            name="SuccessfulPermissionSetDeletion", unit=MetricUnit.Count, value=1
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
def _delete_permission_set(table_name: str, permission_set_id: str) -> None:
    """
    Delete a permission set from DynamoDB

    Note: In a production system, we would also need to:
    1. Check if the permission set is in use (assigned to users/groups)
    2. Delete any assignments or references to this permission set
    3. Consider using a transaction to ensure consistency
    """
    try:
        table = dynamodb.Table(table_name)

        # Delete the permission set using the primary key
        table.delete_item(Key={"PK": f"PS#{permission_set_id}", "SK": "METADATA"})

        # Note: In a production system, we would also need to delete any assignments
        # or references to this permission set, possibly using a transaction

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
