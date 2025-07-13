import json
import os
from datetime import datetime
from typing import Any, Dict, List

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
metrics = Metrics(namespace="medialake", service="assignments-group-assign")

# Initialize DynamoDB client
dynamodb = boto3.resource("dynamodb")


class PermissionSetAssignmentRequest(BaseModel):
    """Model for permission set assignment request"""

    permissionSetIds: List[str] = Field(
        ..., description="List of permission set IDs to assign to the group"
    )

    @validator("permissionSetIds")
    def ids_not_empty(cls, v):
        if not v:
            raise ValueError("permissionSetIds cannot be empty")
        return v


class ErrorResponse(BaseModel):
    status: str = Field(..., description="Error status code")
    message: str = Field(..., description="Error message")
    data: Dict = Field(default={}, description="Empty data object for errors")


class AssignmentResponse(BaseModel):
    status: str = Field(..., description="Success status code")
    message: str = Field(..., description="Success message")
    data: Dict[str, Any] = Field(..., description="Assignment data")


@tracer.capture_lambda_handler
@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """
    Lambda handler to assign permission sets to a group in DynamoDB
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

        # Get the target group ID from path parameters
        path_parameters = event.get("pathParameters", {})
        group_id = path_parameters.get("groupId")

        if not group_id:
            logger.error("Missing groupId in path parameters")
            metrics.add_metric(
                name="MissingGroupIdError", unit=MetricUnit.Count, value=1
            )
            return _create_error_response(400, "Missing groupId in path parameters")

        # Parse the request body
        try:
            body = json.loads(event.get("body", "{}"))
            assignment_request = PermissionSetAssignmentRequest(**body)
        except Exception as e:
            logger.error(f"Invalid request body: {str(e)}")
            metrics.add_metric(
                name="InvalidRequestError", unit=MetricUnit.Count, value=1
            )
            return _create_error_response(400, f"Invalid request: {str(e)}")

        # Verify that all permission sets exist before assigning
        permission_set_ids = assignment_request.permissionSetIds
        if not _verify_permission_sets_exist(auth_table_name, permission_set_ids):
            logger.error("One or more permission sets do not exist")
            metrics.add_metric(
                name="InvalidPermissionSetError", unit=MetricUnit.Count, value=1
            )
            return _create_error_response(
                400, "One or more permission sets do not exist"
            )

        # Verify that the group exists
        if not _verify_group_exists(auth_table_name, group_id):
            logger.error(f"Group {group_id} does not exist")
            metrics.add_metric(name="InvalidGroupError", unit=MetricUnit.Count, value=1)
            return _create_error_response(400, f"Group {group_id} does not exist")

        # Assign the permission sets to the group
        assignments = _assign_permission_sets_to_group(
            auth_table_name, group_id, permission_set_ids, admin_user_id
        )

        # Create success response
        response = AssignmentResponse(
            status="201",
            message="Permission sets assigned successfully",
            data={
                "groupId": group_id,
                "permissionSetIds": permission_set_ids,
                "assignedBy": admin_user_id,
                "assignedAt": datetime.utcnow().isoformat(),
            },
        )

        logger.info(
            "Successfully assigned permission sets to group",
            extra={"group_id": group_id, "permission_set_ids": permission_set_ids},
        )
        metrics.add_metric(name="SuccessfulAssignment", unit=MetricUnit.Count, value=1)

        return {
            "statusCode": 201,
            "headers": {"Content-Type": "application/json"},
            "body": response.model_dump_json(),
        }

    except Exception as e:
        logger.exception("Error processing request")
        metrics.add_metric(name="UnhandledError", unit=MetricUnit.Count, value=1)
        return _create_error_response(500, f"Internal server error: {str(e)}")


@tracer.capture_method
def _verify_permission_sets_exist(
    table_name: str, permission_set_ids: List[str]
) -> bool:
    """
    Verify that all permission sets exist in DynamoDB
    """
    try:
        table = dynamodb.Table(table_name)

        for ps_id in permission_set_ids:
            response = table.get_item(Key={"PK": f"PS#{ps_id}", "SK": "METADATA"})

            if "Item" not in response:
                logger.error(f"Permission set {ps_id} does not exist")
                return False

        return True

    except ClientError as e:
        logger.error(f"DynamoDB error", extra={"error": str(e)})
        raise


@tracer.capture_method
def _verify_group_exists(table_name: str, group_id: str) -> bool:
    """
    Verify that the group exists in DynamoDB
    """
    try:
        table = dynamodb.Table(table_name)

        response = table.get_item(Key={"PK": f"GROUP#{group_id}", "SK": "METADATA"})

        return "Item" in response

    except ClientError as e:
        logger.error(f"DynamoDB error", extra={"error": str(e)})
        raise


@tracer.capture_method
def _assign_permission_sets_to_group(
    table_name: str, group_id: str, permission_set_ids: List[str], assigned_by: str
) -> Dict[str, Any]:
    """
    Assign permission sets to a group in DynamoDB using TransactWriteItems
    """
    try:
        dynamodb.Table(table_name)
        current_time = datetime.utcnow().isoformat()

        # Use TransactWriteItems to ensure atomicity
        transaction_items = []

        for ps_id in permission_set_ids:
            # Create group assignment item
            group_assignment_item = {
                "Put": {
                    "TableName": table_name,
                    "Item": {
                        "PK": f"GROUP#{group_id}",
                        "SK": f"ASSIGNMENT#PS#{ps_id}",
                        "groupId": group_id,
                        "permissionSetId": ps_id,
                        "assignedBy": assigned_by,
                        "assignedAt": current_time,
                        "type": "GROUP_PS_ASSIGNMENT",
                    },
                }
            }

            # Create reverse lookup item
            reverse_lookup_item = {
                "Put": {
                    "TableName": table_name,
                    "Item": {
                        "PK": f"PS#{ps_id}",
                        "SK": f"ASSIGNED_TO#GROUP#{group_id}",
                        "groupId": group_id,
                        "permissionSetId": ps_id,
                        "assignedBy": assigned_by,
                        "assignedAt": current_time,
                        "type": "PS_GROUP_ASSIGNMENT",
                    },
                }
            }

            transaction_items.append(group_assignment_item)
            transaction_items.append(reverse_lookup_item)

        # Execute the transaction
        dynamodb_client = boto3.client("dynamodb")
        dynamodb_client.transact_write_items(TransactItems=transaction_items)

        return {
            "groupId": group_id,
            "permissionSetIds": permission_set_ids,
            "assignedBy": assigned_by,
            "assignedAt": current_time,
        }

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
