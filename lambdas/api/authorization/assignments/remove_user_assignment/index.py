import json
import os
from typing import Any, Dict

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
metrics = Metrics(namespace="medialake", service="assignments-user-remove")

# Initialize DynamoDB client
dynamodb = boto3.resource("dynamodb")


class ErrorResponse(BaseModel):
    status: str = Field(..., description="Error status code")
    message: str = Field(..., description="Error message")
    data: Dict = Field(default={}, description="Empty data object for errors")


class RemoveAssignmentResponse(BaseModel):
    status: str = Field(..., description="Success status code")
    message: str = Field(..., description="Success message")
    data: Dict[str, Any] = Field(..., description="Removal data")


@tracer.capture_lambda_handler
@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """
    Lambda handler to remove a permission set assignment from a user in DynamoDB
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
        admin_user_id = claims.get("sub")

        # If not found in claims, try to get it directly from the authorizer context
        if not admin_user_id:
            admin_user_id = authorizer.get("userId")
            logger.info(
                "Using userId from authorizer context", extra={"user_id": admin_user_id}
            )
        else:
            logger.info("Using sub from claims", extra={"user_id": admin_user_id})

        if not admin_user_id:
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

        # Get the target user ID and permission set ID from path parameters
        path_parameters = event.get("pathParameters", {})
        user_id = path_parameters.get("userId")
        permission_set_id = path_parameters.get("permissionSetId")

        if not user_id:
            logger.error("Missing userId in path parameters")
            metrics.add_metric(
                name="MissingUserIdError", unit=MetricUnit.Count, value=1
            )
            return _create_error_response(400, "Missing userId in path parameters")

        if not permission_set_id:
            logger.error("Missing permissionSetId in path parameters")
            metrics.add_metric(
                name="MissingPermissionSetIdError", unit=MetricUnit.Count, value=1
            )
            return _create_error_response(
                400, "Missing permissionSetId in path parameters"
            )

        # Check if the assignment exists before attempting to remove it
        if not _check_assignment_exists(auth_table_name, user_id, permission_set_id):
            logger.error(
                f"Assignment does not exist for user {user_id} and permission set {permission_set_id}"
            )
            metrics.add_metric(
                name="AssignmentNotFoundError", unit=MetricUnit.Count, value=1
            )
            return _create_error_response(
                404,
                f"Assignment not found for user {user_id} and permission set {permission_set_id}",
            )

        # Remove the permission set assignment from the user
        _remove_user_assignment(auth_table_name, user_id, permission_set_id)

        # Create success response
        response = RemoveAssignmentResponse(
            status="200",
            message="Permission set assignment removed successfully",
            data={
                "userId": user_id,
                "permissionSetId": permission_set_id,
                "removedBy": admin_user_id,
            },
        )

        logger.info(
            "Successfully removed permission set assignment",
            extra={"user_id": user_id, "permission_set_id": permission_set_id},
        )
        metrics.add_metric(name="SuccessfulRemoval", unit=MetricUnit.Count, value=1)

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
def _check_assignment_exists(
    table_name: str, user_id: str, permission_set_id: str
) -> bool:
    """
    Check if a permission set assignment exists for a user in DynamoDB
    """
    try:
        table = dynamodb.Table(table_name)

        response = table.get_item(
            Key={"PK": f"USER#{user_id}", "SK": f"ASSIGNMENT#PS#{permission_set_id}"}
        )

        return "Item" in response

    except ClientError as e:
        logger.error(f"DynamoDB error", extra={"error": str(e)})
        metrics.add_metric(name="DynamoDBError", unit=MetricUnit.Count, value=1)
        raise


@tracer.capture_method
def _remove_user_assignment(
    table_name: str, user_id: str, permission_set_id: str
) -> None:
    """
    Remove a permission set assignment from a user in DynamoDB using TransactWriteItems
    """
    try:
        # Use TransactWriteItems to ensure atomicity
        transaction_items = [
            # Delete user assignment item
            {
                "Delete": {
                    "TableName": table_name,
                    "Key": {
                        "PK": f"USER#{user_id}",
                        "SK": f"ASSIGNMENT#PS#{permission_set_id}",
                    },
                }
            },
            # Delete reverse lookup item
            {
                "Delete": {
                    "TableName": table_name,
                    "Key": {
                        "PK": f"PS#{permission_set_id}",
                        "SK": f"ASSIGNED_TO#USER#{user_id}",
                    },
                }
            },
        ]

        # Execute the transaction
        dynamodb_client = boto3.client("dynamodb")
        dynamodb_client.transact_write_items(TransactItems=transaction_items)

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
