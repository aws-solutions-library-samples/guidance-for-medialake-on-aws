import json
import os
import uuid
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
metrics = Metrics(namespace="medialake", service="groups-create")

# Initialize DynamoDB client
dynamodb = boto3.resource("dynamodb")


class GroupRequest(BaseModel):
    """Model for group creation request from frontend"""

    name: str = Field(..., description="Name of the group")
    description: str = Field(..., description="Description of the group")
    department: Optional[str] = Field(
        None, description="Department associated with the group"
    )

    @validator("name")
    def name_not_empty(cls, v, values, **kwargs):
        if not v.strip():
            raise ValueError("name cannot be empty")
        return v


class ErrorResponse(BaseModel):
    status: str = Field(..., description="Error status code")
    message: str = Field(..., description="Error message")
    data: Dict = Field(default={}, description="Empty data object for errors")


class GroupResponse(BaseModel):
    status: str = Field(..., description="Success status code")
    message: str = Field(..., description="Success message")
    data: Dict[str, Any] = Field(..., description="Created group data")


@tracer.capture_lambda_handler
@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """
    Lambda handler to create a new group in DynamoDB

    This function handles requests from the frontend to create a new group
    following the single table design pattern with primary key structure:
    PK="GROUP#{groupId}", SK="METADATA"
    """
    logger.info("Received event", extra={"event": json.dumps(event)})
    try:
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

        # Check if user has admin permissions (this would be a more robust check in production)
        # In a real implementation, you would check if the user has the 'manageGroups' permission
        # For now, we'll assume the API Gateway authorizer has already verified this

        # Get the auth table name from environment variable
        auth_table_name = os.getenv("AUTH_TABLE_NAME")
        if not auth_table_name:
            logger.error("AUTH_TABLE_NAME environment variable not set")
            metrics.add_metric(
                name="MissingConfigError", unit=MetricUnit.Count, value=1
            )
            return _create_error_response(500, "Internal configuration error")

        # Parse the request body
        try:
            body = json.loads(event.get("body", "{}"))
            logger.info("Request body", extra={"body": json.dumps(body)})
            group_request = GroupRequest(**body)
        except Exception as e:
            logger.error(f"Invalid request body: {str(e)}")
            metrics.add_metric(
                name="InvalidRequestError", unit=MetricUnit.Count, value=1
            )
            return _create_error_response(400, f"Invalid request: {str(e)}")

        # Create the group in DynamoDB
        group = _create_group(auth_table_name, group_request, user_id)

        # Create success response
        try:
            response = GroupResponse(
                status="201",
                message="Group created successfully",
                data=group,
            )

            logger.info("Successfully created group", extra={"group_id": group["id"]})
            metrics.add_metric(
                name="SuccessfulGroupCreation", unit=MetricUnit.Count, value=1
            )

            # Try to serialize the response
            response_json = response.model_dump_json()
            logger.info(f"Response JSON: {response_json}")

            return {
                "statusCode": 201,
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token",
                    "Access-Control-Allow-Methods": "OPTIONS,GET,PUT,POST,DELETE,PATCH",
                },
                "body": response_json,
            }
        except Exception as e:
            logger.error(f"Error creating response: {str(e)}")
            return _create_error_response(500, f"Error creating response: {str(e)}")

    except Exception as e:
        logger.exception(f"Error processing request: {str(e)}")
        metrics.add_metric(name="UnhandledError", unit=MetricUnit.Count, value=1)
        return _create_error_response(500, f"Internal server error: {str(e)}")


@tracer.capture_method
def _create_group(
    table_name: str, group_request: GroupRequest, created_by: str
) -> Dict[str, Any]:
    """
    Create a new group in DynamoDB following the single table design pattern

    Primary key structure:
    - PK: "GROUP#{groupId}"
    - SK: "METADATA"

    This function also sets up GSI1 keys for backward compatibility, but
    the list_groups function has been modified to use a direct scan with
    a filter expression on the primary key instead of using the GSI.
    """
    try:
        # Generate a unique ID for the group
        group_id = str(uuid.uuid4())

        # Get the current timestamp
        current_time = datetime.utcnow().isoformat()

        # Create the DynamoDB item
        group_item = {
            "PK": f"GROUP#{group_id}",
            "SK": "METADATA",
            "id": group_id,
            "name": group_request.name,
            "description": group_request.description,
            "createdBy": created_by,
            "createdAt": current_time,
            "updatedAt": current_time,
            "entity": "group",
            "type": "GROUP",
        }

        # Add optional fields if provided
        if group_request.department:
            group_item["department"] = group_request.department

        # Add GSI1 keys for backward compatibility
        # Note: The list_groups function has been modified to use a direct scan
        # with a filter expression on the primary key instead of using the GSI
        group_item["GSI1PK"] = "GROUPS"
        group_item["GSI1SK"] = f"GROUP#{group_id}"

        # Write to DynamoDB
        table = dynamodb.Table(table_name)
        table.put_item(Item=group_item)

        # Return the created group (without the DynamoDB-specific keys)
        result = {
            "id": group_id,
            "name": group_request.name,
            "description": group_request.description,
            "createdBy": created_by,
            "createdAt": current_time,
            "updatedAt": current_time,
        }

        # Include optional fields in the response if they were provided
        if group_request.department:
            result["department"] = group_request.department

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
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token",
            "Access-Control-Allow-Methods": "OPTIONS,GET,PUT,POST,DELETE,PATCH",
        },
        "body": error_response.model_dump_json(),
    }
