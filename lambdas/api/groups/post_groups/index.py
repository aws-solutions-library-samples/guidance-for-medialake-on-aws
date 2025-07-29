import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.utilities.validation import validate
from botocore.exceptions import ClientError
from pydantic import BaseModel, Field, validator

# Initialize AWS PowerTools
logger = Logger(service="groups-service", level=os.getenv("LOG_LEVEL", "WARNING"))
tracer = Tracer(service="groups-service")
metrics = Metrics(namespace="medialake", service="groups-create")

# Initialize AWS clients
dynamodb = boto3.resource("dynamodb")
cognito_client = boto3.client("cognito-idp")


class GroupRequest(BaseModel):
    """Model for group creation request from frontend"""

    name: str = Field(..., description="Display name of the group")
    id: str = Field(
        ..., description="Unique identifier for the group (used for Cognito group name)"
    )
    description: str = Field(..., description="Description of the group")
    department: Optional[str] = Field(
        None, description="Department associated with the group"
    )
    assignedPermissionSets: Optional[List[str]] = Field(
        default=[], description="List of permission sets assigned to the group"
    )

    @validator("name")
    def name_not_empty(cls, v, values, **kwargs):
        if not v.strip():
            raise ValueError("name cannot be empty")
        return v.strip()

    @validator("id")
    def id_not_empty(cls, v, values, **kwargs):
        if not v.strip():
            raise ValueError("id cannot be empty")
        # Ensure id is valid for Cognito group names (alphanumeric and underscore only)
        import re

        if not re.match(r"^[a-zA-Z0-9_]+$", v.strip()):
            raise ValueError(
                "id must contain only alphanumeric characters and underscores"
            )
        return v.strip()


class ErrorResponse(BaseModel):
    status: str = Field(..., description="Error status code")
    message: str = Field(..., description="Error message")
    data: Dict = Field(default={}, description="Empty data object for errors")


class GroupResponse(BaseModel):
    status: str = Field(..., description="Success status code")
    message: str = Field(..., description="Success message")
    data: Dict[str, Any] = Field(..., description="Created group data")


# Validation schema for request
input_schema = {
    "type": "object",
    "properties": {"body": {"type": "string"}},
    "required": ["body"],
}


@tracer.capture_lambda_handler
@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
@metrics.log_metrics(capture_cold_start_metric=True)
@validate(inbound_schema=input_schema)
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """
    Lambda handler to create a new group in both DynamoDB and Cognito

    This function handles requests from the frontend to create a new group with:
    - DynamoDB entry following the auth table schema
    - Cognito group for user management
    - Proper rollback if either operation fails
    """
    logger.info("Received event", extra={"event": json.dumps(event)})

    # Handle Lambda warmer
    if event.get("lambda_warmer"):
        logger.info("Lambda warmer request received")
        return {"statusCode": 200, "body": "Lambda warmed"}

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

        # Get required environment variables
        auth_table_name = os.getenv("AUTH_TABLE_NAME")
        cognito_user_pool_id = os.getenv("COGNITO_USER_POOL_ID")

        if not auth_table_name:
            logger.error("AUTH_TABLE_NAME environment variable not set")
            metrics.add_metric(
                name="MissingConfigError", unit=MetricUnit.Count, value=1
            )
            return _create_error_response(
                500, "Internal configuration error - missing table name"
            )

        if not cognito_user_pool_id:
            logger.error("COGNITO_USER_POOL_ID environment variable not set")
            metrics.add_metric(
                name="MissingConfigError", unit=MetricUnit.Count, value=1
            )
            return _create_error_response(
                500, "Internal configuration error - missing user pool ID"
            )

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

        # Create the group with rollback handling
        group = _create_group_with_rollback(
            auth_table_name, cognito_user_pool_id, group_request, user_id
        )

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
def _create_group_with_rollback(
    table_name: str,
    cognito_user_pool_id: str,
    group_request: GroupRequest,
    created_by: str,
) -> Dict[str, Any]:
    """
    Create a new group in both DynamoDB and Cognito with rollback handling

    This function ensures that if either operation fails, the other is rolled back
    to maintain consistency.
    """
    cognito_created = False
    dynamodb_created = False

    try:
        # Get the current timestamp
        current_time = datetime.utcnow().isoformat()

        # Step 1: Create the Cognito group first
        logger.info(f"Creating Cognito group: {group_request.id}")
        try:
            cognito_client.create_group(
                GroupName=group_request.id,
                UserPoolId=cognito_user_pool_id,
                Description=group_request.description,
            )
            cognito_created = True
            logger.info(f"Successfully created Cognito group: {group_request.id}")
            metrics.add_metric(
                name="CognitoGroupCreated", unit=MetricUnit.Count, value=1
            )
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            if error_code == "GroupExistsException":
                logger.error(f"Cognito group already exists: {group_request.id}")
                metrics.add_metric(
                    name="CognitoGroupExistsError", unit=MetricUnit.Count, value=1
                )
                raise ValueError(f"Group with ID '{group_request.id}' already exists")
            else:
                logger.error(f"Failed to create Cognito group: {str(e)}")
                metrics.add_metric(
                    name="CognitoGroupCreationError", unit=MetricUnit.Count, value=1
                )
                raise

        # Step 2: Create the DynamoDB item following the auth table schema
        logger.info(f"Creating DynamoDB entry for group: {group_request.id}")

        # Create the DynamoDB item matching the provided schema
        group_item = {
            "PK": f"GROUP#{group_request.id}",
            "SK": "METADATA",
            "assignedPermissionSets": group_request.assignedPermissionSets or [],
            "createdAt": current_time,
            "description": group_request.description,
            "entity": "group",
            "id": group_request.id,
            "name": group_request.name,
            "updatedAt": current_time,
        }

        # Add optional fields if provided
        if group_request.department:
            group_item["department"] = group_request.department

        # Write to DynamoDB
        table = dynamodb.Table(table_name)

        # Use conditional write to prevent overwriting existing groups
        try:
            table.put_item(
                Item=group_item, ConditionExpression="attribute_not_exists(PK)"
            )
            dynamodb_created = True
            logger.info(
                f"Successfully created DynamoDB entry for group: {group_request.id}"
            )
            metrics.add_metric(
                name="DynamoDBGroupCreated", unit=MetricUnit.Count, value=1
            )
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            if error_code == "ConditionalCheckFailedException":
                logger.error(f"DynamoDB group already exists: {group_request.id}")
                metrics.add_metric(
                    name="DynamoDBGroupExistsError", unit=MetricUnit.Count, value=1
                )
                raise ValueError(
                    f"Group with ID '{group_request.id}' already exists in database"
                )
            else:
                logger.error(f"Failed to create DynamoDB entry: {str(e)}")
                metrics.add_metric(
                    name="DynamoDBGroupCreationError", unit=MetricUnit.Count, value=1
                )
                raise

        # Return the created group (without the DynamoDB-specific keys)
        result = {
            "id": group_request.id,
            "name": group_request.name,
            "description": group_request.description,
            "assignedPermissionSets": group_request.assignedPermissionSets or [],
            "createdAt": current_time,
            "updatedAt": current_time,
            "entity": "group",
        }

        # Include optional fields in the response if they were provided
        if group_request.department:
            result["department"] = group_request.department

        return result

    except Exception as e:
        logger.error(f"Error during group creation: {str(e)}")
        metrics.add_metric(name="GroupCreationError", unit=MetricUnit.Count, value=1)

        # Rollback operations in reverse order
        if dynamodb_created:
            try:
                logger.info(
                    f"Rolling back DynamoDB entry for group: {group_request.id}"
                )
                table = dynamodb.Table(table_name)
                table.delete_item(
                    Key={"PK": f"GROUP#{group_request.id}", "SK": "METADATA"}
                )
                logger.info(
                    f"Successfully rolled back DynamoDB entry for group: {group_request.id}"
                )
                metrics.add_metric(
                    name="DynamoDBRollbackSuccess", unit=MetricUnit.Count, value=1
                )
            except Exception as rollback_error:
                logger.error(
                    f"Failed to rollback DynamoDB entry: {str(rollback_error)}"
                )
                metrics.add_metric(
                    name="DynamoDBRollbackError", unit=MetricUnit.Count, value=1
                )

        if cognito_created:
            try:
                logger.info(f"Rolling back Cognito group: {group_request.id}")
                cognito_client.delete_group(
                    GroupName=group_request.id, UserPoolId=cognito_user_pool_id
                )
                logger.info(
                    f"Successfully rolled back Cognito group: {group_request.id}"
                )
                metrics.add_metric(
                    name="CognitoRollbackSuccess", unit=MetricUnit.Count, value=1
                )
            except Exception as rollback_error:
                logger.error(f"Failed to rollback Cognito group: {str(rollback_error)}")
                metrics.add_metric(
                    name="CognitoRollbackError", unit=MetricUnit.Count, value=1
                )

        # Re-raise the original exception
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
