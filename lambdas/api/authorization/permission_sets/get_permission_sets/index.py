from typing import Dict, Any, Optional, List
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
from boto3.dynamodb.conditions import Key

# Initialize AWS PowerTools
logger = Logger(service="authorization-service", level=os.getenv("LOG_LEVEL", "WARNING"))
tracer = Tracer(service="authorization-service")
metrics = Metrics(namespace="medialake", service="permission-sets-list")

# Initialize DynamoDB client
dynamodb = boto3.resource("dynamodb")


class ErrorResponse(BaseModel):
    status: str = Field(..., description="Error status code")
    message: str = Field(..., description="Error message")
    data: Dict = Field(default={}, description="Empty data object for errors")


class PermissionSetsResponse(BaseModel):
    status: str = Field(..., description="Success status code")
    message: str = Field(..., description="Success message")
    data: Dict[str, Any] = Field(..., description="Permission sets data")


@tracer.capture_lambda_handler
@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(
    event: Dict[str, Any], context: LambdaContext
) -> Dict[str, Any]:
    """
    Lambda handler to list all permission sets from DynamoDB
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

        # Get query parameters
        query_string_parameters = event.get("queryStringParameters", {}) or {}
        
        # Fetch permission sets from DynamoDB
        permission_sets = _list_permission_sets(auth_table_name, query_string_parameters)

        # Create success response
        response = PermissionSetsResponse(
            status="200",
            message="Permission sets retrieved successfully",
            data={"permissionSets": permission_sets},
        )

        logger.info("Successfully retrieved permission sets", 
                   extra={"count": len(permission_sets)})
        metrics.add_metric(name="SuccessfulPermissionSetsLookup", unit=MetricUnit.Count, value=1)

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
def _list_permission_sets(
    table_name: str, 
    query_params: Dict[str, str]
) -> List[Dict[str, Any]]:
    """
    List all permission sets from DynamoDB
    
    We can use the GSI1 to query all permission sets efficiently
    """
    try:
        table = dynamodb.Table(table_name)
        
        # Query the GSI1 for all permission sets
        # GSI1PK = "PERMISSION_SETS" and GSI1SK starts with "PS#"
        response = table.query(
            IndexName="GSI1",
            KeyConditionExpression=Key("GSI1PK").eq("PERMISSION_SETS")
        )
        
        items = response.get("Items", [])
        
        # Process pagination if there are more results
        while "LastEvaluatedKey" in response:
            response = table.query(
                IndexName="GSI1",
                KeyConditionExpression=Key("GSI1PK").eq("PERMISSION_SETS"),
                ExclusiveStartKey=response["LastEvaluatedKey"]
            )
            items.extend(response.get("Items", []))
        
        # Transform the items to remove DynamoDB-specific attributes
        permission_sets = []
        for item in items:
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
            permission_sets.append(permission_set)
        
        return permission_sets

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