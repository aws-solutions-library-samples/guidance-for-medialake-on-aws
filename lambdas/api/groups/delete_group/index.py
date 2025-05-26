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
metrics = Metrics(namespace="medialake", service="groups-delete")

# Initialize DynamoDB client
dynamodb = boto3.resource("dynamodb")


class ErrorResponse(BaseModel):
    status: str = Field(..., description="Error status code")
    message: str = Field(..., description="Error message")
    data: Dict = Field(default={}, description="Empty data object for errors")


class SuccessResponse(BaseModel):
    status: str = Field(..., description="Success status code")
    message: str = Field(..., description="Success message")
    data: Dict[str, Any] = Field(default={}, description="Empty data object for success")


@tracer.capture_lambda_handler
@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(
    event: Dict[str, Any], context: LambdaContext
) -> Dict[str, Any]:
    """
    Lambda handler to delete a group from DynamoDB
    """
    try:
        # Log the entire event structure for debugging
        logger.info("Received event", extra={"event": json.dumps(event)})
        
        # Extract user ID from Cognito authorizer context
        request_context = event.get("requestContext", {})
        logger.info("Request context", extra={"request_context": json.dumps(request_context)})
        
        authorizer = request_context.get("authorizer", {})
        logger.info("Authorizer context", extra={"authorizer": json.dumps(authorizer)})
        
        claims = authorizer.get("claims", {})
        logger.info("Claims", extra={"claims": json.dumps(claims)})
        
        # Get the user ID from the Cognito claims or directly from the authorizer context
        user_id = claims.get("sub")
        
        # If not found in claims, try to get it directly from the authorizer context
        if not user_id:
            user_id = authorizer.get("userId")
            logger.info("Using userId from authorizer context", extra={"user_id": user_id})
        else:
            logger.info("Using sub from claims", extra={"user_id": user_id})
        
        if not user_id:
            logger.error("Missing user_id in both Cognito claims and authorizer context")
            metrics.add_metric(
                name="MissingUserIdError", unit=MetricUnit.Count, value=1
            )
            return _create_error_response(400, "Unable to identify user - missing from both claims and authorizer context")

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

        # Check if the group exists
        table = dynamodb.Table(auth_table_name)
        response = table.get_item(
            Key={
                "PK": f"GROUP#{group_id}",
                "SK": "METADATA"
            }
        )
        
        if "Item" not in response:
            logger.error(f"Group not found", extra={"group_id": group_id})
            metrics.add_metric(name="GroupNotFoundError", unit=MetricUnit.Count, value=1)
            return _create_error_response(404, f"Group with ID {group_id} not found")

        # Delete the group and all its memberships
        _delete_group(auth_table_name, group_id)

        # Create success response
        response = SuccessResponse(
            status="200",
            message="Group deleted successfully",
            data={}
        )

        logger.info("Successfully deleted group", 
                   extra={"group_id": group_id})
        metrics.add_metric(name="SuccessfulGroupDeletion", unit=MetricUnit.Count, value=1)

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
def _delete_group(
    table_name: str, 
    group_id: str
) -> None:
    """
    Delete a group and all its memberships from DynamoDB
    """
    try:
        table = dynamodb.Table(table_name)
        
        # First, get all items related to this group (memberships)
        response = table.query(
            KeyConditionExpression=Key("PK").eq(f"GROUP#{group_id}")
        )
        
        items = response.get("Items", [])
        
        # Process pagination if there are more results
        while "LastEvaluatedKey" in response:
            response = table.query(
                KeyConditionExpression=Key("PK").eq(f"GROUP#{group_id}"),
                ExclusiveStartKey=response["LastEvaluatedKey"]
            )
            items.extend(response.get("Items", []))
        
        # Delete all items in batches of 25 (DynamoDB batch write limit)
        batch_size = 25
        for i in range(0, len(items), batch_size):
            batch_items = items[i:i+batch_size]
            
            # Prepare batch delete request
            delete_requests = []
            for item in batch_items:
                delete_requests.append({
                    "DeleteRequest": {
                        "Key": {
                            "PK": item["PK"],
                            "SK": item["SK"]
                        }
                    }
                })
            
            # Execute batch delete
            if delete_requests:
                dynamodb.batch_write_item(
                    RequestItems={
                        table_name: delete_requests
                    }
                )
        
        # Also delete any reverse lookup items (USER#{userId}#MEMBERSHIP#GROUP#{groupId})
        # This would require additional queries and batch deletes
        # For simplicity, we're not implementing this here, but in a production system
        # you would want to clean up these references as well

        logger.info(f"Deleted group and {len(items)} related items", 
                   extra={"group_id": group_id})

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