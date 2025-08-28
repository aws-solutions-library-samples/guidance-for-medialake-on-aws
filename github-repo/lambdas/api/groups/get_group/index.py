import json
import os
from typing import Any, Dict, List, Optional

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
metrics = Metrics(namespace="medialake", service="groups-get")

# Initialize DynamoDB client
dynamodb = boto3.resource("dynamodb")


class ErrorResponse(BaseModel):
    status: str = Field(..., description="Error status code")
    message: str = Field(..., description="Error message")
    data: Dict = Field(default={}, description="Empty data object for errors")


class GroupResponse(BaseModel):
    status: str = Field(..., description="Success status code")
    message: str = Field(..., description="Success message")
    data: Dict[str, Any] = Field(..., description="Group data")


@tracer.capture_lambda_handler
@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """
    Lambda handler to get a specific group from DynamoDB
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

        # Get the group from DynamoDB
        group = _get_group(auth_table_name, group_id)

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


@tracer.capture_method
def _get_group(table_name: str, group_id: str) -> Optional[Dict[str, Any]]:
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
        members = _get_group_members(table, group_id)
        group["members"] = members

        return group

    except ClientError as e:
        logger.error(f"DynamoDB error", extra={"error": str(e)})
        metrics.add_metric(name="DynamoDBError", unit=MetricUnit.Count, value=1)
        raise


@tracer.capture_method
def _get_group_members(
    table: boto3.resource("dynamodb").Table, group_id: str
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
