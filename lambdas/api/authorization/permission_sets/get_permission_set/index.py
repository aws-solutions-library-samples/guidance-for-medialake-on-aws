from typing import Dict, Any, Optional
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.utilities.parser import parse
from aws_lambda_powertools.utilities.parser.models import APIGatewayProxyEventModel
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.metrics import MetricUnit
from pydantic import BaseModel, Field
import boto3
import os
from botocore.exceptions import ClientError
import json

# Initialize AWS PowerTools
logger = Logger(service="authorization-service", level=os.getenv("LOG_LEVEL", "WARNING"))
tracer = Tracer(service="authorization-service")
metrics = Metrics(namespace="medialake", service="permission-set-get")

# Initialize DynamoDB client
dynamodb = boto3.resource("dynamodb")


class ErrorResponse(BaseModel):
    status: str = Field(..., description="Error status code")
    message: str = Field(..., description="Error message")
    data: Dict = Field(default={}, description="Empty data object for errors")


class PermissionSetResponse(BaseModel):
    status: str = Field(..., description="Success status code")
    message: str = Field(..., description="Success message")
    data: Dict[str, Any] = Field(..., description="Permission set data")


@tracer.capture_lambda_handler
@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(
    event: Dict[str, Any], context: LambdaContext
) -> Dict[str, Any]:
    """
    Lambda handler to get a specific permission set from DynamoDB
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

        # Fetch the permission set from DynamoDB
        permission_set = _get_permission_set(auth_table_name, permission_set_id)
        
        if not permission_set:
            logger.warning(f"Permission set not found", extra={"permission_set_id": permission_set_id})
            metrics.add_metric(name="PermissionSetNotFound", unit=MetricUnit.Count, value=1)
            return _create_error_response(404, f"Permission set with ID {permission_set_id} not found")

        # Create success response
        response = PermissionSetResponse(
            status="200",
            message="Permission set retrieved successfully",
            data=permission_set,
        )

        logger.info("Successfully retrieved permission set", 
                   extra={"permission_set_id": permission_set_id})
        metrics.add_metric(name="SuccessfulPermissionSetLookup", unit=MetricUnit.Count, value=1)

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
    table_name: str, 
    permission_set_id: str
) -> Optional[Dict[str, Any]]:
    """
    Get a specific permission set from DynamoDB
    """
    try:
        table = dynamodb.Table(table_name)
        
        # Get the permission set using the primary key
        response = table.get_item(
            Key={
                "PK": f"PS#{permission_set_id}",
                "SK": "METADATA"
            }
        )
        
        # Check if the item exists
        if "Item" not in response:
            return None
        
        # Transform the item to remove DynamoDB-specific attributes
        item = response["Item"]
        permission_set = {
            "id": item.get("id"),
            "name": item.get("name"),
            "description": item.get("description"),
            "permissions": item.get("permissions", []),
            "isSystem": item.get("isSystem", False),
            "createdBy": item.get("createdBy"),
            "createdAt": item.get("createdAt"),
            "updatedAt": item.get("updatedAt")
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