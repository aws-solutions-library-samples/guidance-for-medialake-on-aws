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
metrics = Metrics(namespace="medialake", service="groups-add-members")

# Initialize DynamoDB client
dynamodb = boto3.resource("dynamodb")


class AddMembersRequest(BaseModel):
    """Model for adding members to a group"""

    userIds: List[str] = Field(..., description="List of user IDs to add to the group")

    @validator("userIds")
    def userIds_not_empty(cls, v):
        if not v:
            raise ValueError("userIds cannot be empty")
        return v


class ErrorResponse(BaseModel):
    status: str = Field(..., description="Error status code")
    message: str = Field(..., description="Error message")
    data: Dict = Field(default={}, description="Empty data object for errors")


class AddMembersResponse(BaseModel):
    status: str = Field(..., description="Success status code")
    message: str = Field(..., description="Success message")
    data: Dict[str, Any] = Field(..., description="Added members data")


@tracer.capture_lambda_handler
@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """
    Lambda handler to add members to a group in DynamoDB
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
            add_members_request = AddMembersRequest(**body)
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

        # Add members to the group
        result = _add_group_members(
            auth_table_name, group_id, add_members_request.userIds, user_id
        )

        # Create success response
        response = AddMembersResponse(
            status="200",
            message="Members added to group successfully",
            data={
                "groupId": group_id,
                "addedMembers": result["added"],
                "alreadyMembers": result["already_members"],
            },
        )

        logger.info(
            "Successfully added members to group",
            extra={"group_id": group_id, "added_count": len(result["added"])},
        )
        metrics.add_metric(
            name="SuccessfulMembersAddition", unit=MetricUnit.Count, value=1
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
def _add_group_members(
    table_name: str, group_id: str, user_ids: List[str], added_by: str
) -> Dict[str, List[str]]:
    """
    Add members to a group in DynamoDB

    Returns a dictionary with lists of user IDs that were added and those that were already members
    """
    try:
        table = dynamodb.Table(table_name)
        current_time = datetime.utcnow().isoformat()

        # Track which users were added and which were already members
        added_users = []
        already_members = []

        # Process each user ID
        for user_id in user_ids:
            # Check if the user is already a member of the group
            response = table.get_item(
                Key={"PK": f"GROUP#{group_id}", "SK": f"MEMBERSHIP#USER#{user_id}"}
            )

            if "Item" in response:
                # User is already a member
                already_members.append(user_id)
                continue

            # Add the user to the group
            membership_item = {
                "PK": f"GROUP#{group_id}",
                "SK": f"MEMBERSHIP#USER#{user_id}",
                "groupId": group_id,
                "userId": user_id,
                "addedBy": added_by,
                "addedAt": current_time,
                "type": "GROUP_MEMBERSHIP",
            }

            # Add GSI1 keys for querying memberships
            membership_item["GSI1PK"] = f"USER#{user_id}"
            membership_item["GSI1SK"] = f"MEMBERSHIP#GROUP#{group_id}"

            # Write to DynamoDB
            table.put_item(Item=membership_item)

            # Also create the reverse lookup item for efficient user->groups queries
            reverse_membership_item = {
                "PK": f"USER#{user_id}",
                "SK": f"MEMBERSHIP#GROUP#{group_id}",
                "groupId": group_id,
                "userId": user_id,
                "addedBy": added_by,
                "addedAt": current_time,
                "type": "USER_GROUP_MEMBERSHIP",
            }

            # Add GSI1 keys for querying user memberships
            reverse_membership_item["GSI1PK"] = f"USER#{user_id}"
            reverse_membership_item["GSI1SK"] = f"MEMBERSHIPS"

            # Write to DynamoDB
            table.put_item(Item=reverse_membership_item)

            added_users.append(user_id)

        return {"added": added_users, "already_members": already_members}

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
