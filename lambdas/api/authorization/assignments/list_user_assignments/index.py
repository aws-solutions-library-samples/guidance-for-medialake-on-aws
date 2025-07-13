import json
import os
from typing import Any, Dict, List

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
metrics = Metrics(namespace="medialake", service="assignments-user-list")

# Initialize DynamoDB client
dynamodb = boto3.resource("dynamodb")


class PermissionSetAssignment(BaseModel):
    """Model for a permission set assignment"""

    permissionSetId: str = Field(..., description="ID of the permission set")
    assignedAt: str = Field(
        ..., description="Timestamp when the permission set was assigned"
    )
    assignedBy: str = Field(
        ..., description="ID of the user who assigned the permission set"
    )


class ErrorResponse(BaseModel):
    status: str = Field(..., description="Error status code")
    message: str = Field(..., description="Error message")
    data: Dict = Field(default={}, description="Empty data object for errors")


class AssignmentsResponse(BaseModel):
    status: str = Field(..., description="Success status code")
    message: str = Field(..., description="Success message")
    data: Dict[str, Any] = Field(..., description="Assignments data")


@tracer.capture_lambda_handler
@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """
    Lambda handler to list permission sets assigned to a user in DynamoDB
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

        # Get the target user ID from path parameters
        path_parameters = event.get("pathParameters", {})
        user_id = path_parameters.get("userId")

        if not user_id:
            logger.error("Missing userId in path parameters")
            metrics.add_metric(
                name="MissingUserIdError", unit=MetricUnit.Count, value=1
            )
            return _create_error_response(400, "Missing userId in path parameters")

        # List the permission sets assigned to the user
        assignments = _list_user_assignments(auth_table_name, user_id)

        # Create success response
        response = AssignmentsResponse(
            status="200",
            message="Permission set assignments retrieved successfully",
            data={"userId": user_id, "assignments": assignments},
        )

        logger.info(
            "Successfully retrieved permission set assignments",
            extra={"user_id": user_id, "assignment_count": len(assignments)},
        )
        metrics.add_metric(
            name="SuccessfulListOperation", unit=MetricUnit.Count, value=1
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
def _list_user_assignments(table_name: str, user_id: str) -> List[Dict[str, Any]]:
    """
    List permission sets assigned to a user in DynamoDB
    """
    try:
        table = dynamodb.Table(table_name)

        # Query for all permission set assignments for the user
        response = table.query(
            KeyConditionExpression="PK = :pk AND begins_with(SK, :sk_prefix)",
            ExpressionAttributeValues={
                ":pk": f"USER#{user_id}",
                ":sk_prefix": "ASSIGNMENT#PS#",
            },
        )

        # Extract the permission set IDs and assignment details
        assignments = []
        for item in response.get("Items", []):
            # Extract the permission set ID from the SK
            sk = item.get("SK", "")
            if sk.startswith("ASSIGNMENT#PS#"):
                permission_set_id = sk[len("ASSIGNMENT#PS#") :]

                assignment = {
                    "permissionSetId": permission_set_id,
                    "assignedAt": item.get("assignedAt"),
                    "assignedBy": item.get("assignedBy"),
                }

                assignments.append(assignment)

        # Optionally, we could fetch the full permission set details for each ID
        # But for now, we'll just return the IDs and assignment metadata

        return assignments

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
