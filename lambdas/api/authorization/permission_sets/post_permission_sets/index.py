import json
import os
import uuid
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
metrics = Metrics(namespace="medialake", service="permission-sets-create")

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


class PermissionSetRequest(BaseModel):
    """Model for permission set creation request"""

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
    data: Dict[str, Any] = Field(..., description="Created permission set data")


@tracer.capture_lambda_handler
@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """
    Lambda handler to create a new permission set in DynamoDB
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

        # Check if user has admin permissions (this would be a more robust check in production)
        # In a real implementation, you would check if the user has the 'managePermissionSets' permission
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
            permission_set_request = PermissionSetRequest(**body)
        except Exception as e:
            logger.error(f"Invalid request body: {str(e)}")
            metrics.add_metric(
                name="InvalidRequestError", unit=MetricUnit.Count, value=1
            )
            return _create_error_response(400, f"Invalid request: {str(e)}")

        # Create the permission set in DynamoDB
        permission_set = _create_permission_set(
            auth_table_name, permission_set_request, user_id
        )

        # Create success response
        response = PermissionSetResponse(
            status="201",
            message="Permission set created successfully",
            data=permission_set,
        )

        logger.info(
            "Successfully created permission set",
            extra={"permission_set_id": permission_set["id"]},
        )
        metrics.add_metric(
            name="SuccessfulPermissionSetCreation", unit=MetricUnit.Count, value=1
        )

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
def _create_permission_set(
    table_name: str, permission_set_request: PermissionSetRequest, created_by: str
) -> Dict[str, Any]:
    """
    Create a new permission set in DynamoDB
    """
    try:
        # Generate a unique ID for the permission set
        permission_set_id = str(uuid.uuid4())

        # Get the current timestamp
        current_time = datetime.utcnow().isoformat()

        # Create the DynamoDB item
        permission_set_item = {
            "PK": f"PS#{permission_set_id}",
            "SK": "METADATA",
            "id": permission_set_id,
            "name": permission_set_request.name,
            "description": permission_set_request.description,
            "permissions": [p.dict() for p in permission_set_request.permissions],
            "isSystem": False,  # Custom permission sets are not system-defined
            "createdBy": created_by,
            "createdAt": current_time,
            "updatedAt": current_time,
            "type": "PERMISSION_SET",
        }

        # Add GSI1 keys for querying permission sets
        permission_set_item["GSI1PK"] = "PERMISSION_SETS"
        permission_set_item["GSI1SK"] = f"PS#{permission_set_id}"

        # Write to DynamoDB
        table = dynamodb.Table(table_name)
        table.put_item(Item=permission_set_item)

        # Return the created permission set (without the DynamoDB-specific keys)
        result = {
            "id": permission_set_id,
            "name": permission_set_request.name,
            "description": permission_set_request.description,
            "permissions": [p.dict() for p in permission_set_request.permissions],
            "isSystem": False,
            "createdBy": created_by,
            "createdAt": current_time,
            "updatedAt": current_time,
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
