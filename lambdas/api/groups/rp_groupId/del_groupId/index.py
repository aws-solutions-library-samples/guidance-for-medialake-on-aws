import json
import os
from typing import Any, Dict

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.utilities.validation import validate
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError
from pydantic import BaseModel, Field

# Initialize AWS PowerTools
logger = Logger(service="groups-service", level=os.getenv("LOG_LEVEL", "WARNING"))
tracer = Tracer(service="groups-service")
metrics = Metrics(namespace="medialake", service="groups-delete")

# Initialize AWS clients
dynamodb = boto3.resource("dynamodb")
cognito_client = boto3.client("cognito-idp")


class ErrorResponse(BaseModel):
    status: str = Field(..., description="Error status code")
    message: str = Field(..., description="Error message")
    data: Dict = Field(default={}, description="Empty data object for errors")


class SuccessResponse(BaseModel):
    status: str = Field(..., description="Success status code")
    message: str = Field(..., description="Success message")
    data: Dict[str, Any] = Field(
        default={}, description="Empty data object for success"
    )


# Validation schema for request
input_schema = {
    "type": "object",
    "properties": {
        "pathParameters": {
            "type": "object",
            "properties": {"groupId": {"type": "string"}},
            "required": ["groupId"],
        }
    },
    "required": ["pathParameters"],
}


@tracer.capture_lambda_handler
@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
@metrics.log_metrics(capture_cold_start_metric=True)
@validate(inbound_schema=input_schema)
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """
    Lambda handler to delete a group from both DynamoDB and Cognito

    This function handles requests to delete a group with:
    - DynamoDB cleanup (group metadata and memberships)
    - Cognito group deletion
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

        # Delete the group with rollback handling
        _delete_group_with_rollback(auth_table_name, cognito_user_pool_id, group_id)

        # Create success response
        response = SuccessResponse(
            status="200", message="Group deleted successfully", data={}
        )

        logger.info("Successfully deleted group", extra={"group_id": group_id})
        metrics.add_metric(
            name="SuccessfulGroupDeletion", unit=MetricUnit.Count, value=1
        )

        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token",
                "Access-Control-Allow-Methods": "OPTIONS,GET,PUT,POST,DELETE,PATCH",
            },
            "body": response.model_dump_json(),
        }

    except Exception as e:
        logger.exception("Error processing request")
        metrics.add_metric(name="UnhandledError", unit=MetricUnit.Count, value=1)
        return _create_error_response(500, f"Internal server error: {str(e)}")


@tracer.capture_method
def _delete_group_with_rollback(
    table_name: str, cognito_user_pool_id: str, group_id: str
) -> None:
    """
    Delete a group from both DynamoDB and Cognito with rollback handling

    This function ensures that if either operation fails, the other is rolled back
    to maintain consistency.
    """
    dynamodb_backup = None
    cognito_deleted = False

    try:
        table = dynamodb.Table(table_name)

        # Step 1: Verify the group exists and backup its data
        logger.info(f"Checking if group exists: {group_id}")
        response = table.get_item(Key={"PK": f"GROUP#{group_id}", "SK": "METADATA"})

        if "Item" not in response:
            logger.error(f"Group not found", extra={"group_id": group_id})
            metrics.add_metric(
                name="GroupNotFoundError", unit=MetricUnit.Count, value=1
            )
            raise ValueError(f"Group with ID '{group_id}' not found")

        # Step 2: Get all related items for backup (group metadata and memberships)
        logger.info(f"Getting all related items for group: {group_id}")
        response = table.query(KeyConditionExpression=Key("PK").eq(f"GROUP#{group_id}"))

        items = response.get("Items", [])

        # Process pagination if there are more results
        while "LastEvaluatedKey" in response:
            response = table.query(
                KeyConditionExpression=Key("PK").eq(f"GROUP#{group_id}"),
                ExclusiveStartKey=response["LastEvaluatedKey"],
            )
            items.extend(response.get("Items", []))

        dynamodb_backup = items
        logger.info(f"Backed up {len(items)} items for group: {group_id}")

        # Step 3: Delete from Cognito first
        logger.info(f"Deleting Cognito group: {group_id}")
        try:
            cognito_client.delete_group(
                GroupName=group_id, UserPoolId=cognito_user_pool_id
            )
            cognito_deleted = True
            logger.info(f"Successfully deleted Cognito group: {group_id}")
            metrics.add_metric(
                name="CognitoGroupDeleted", unit=MetricUnit.Count, value=1
            )
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            if error_code == "ResourceNotFoundException":
                logger.warning(
                    f"Cognito group not found (may have been deleted already): {group_id}"
                )
                # Continue with DynamoDB deletion even if Cognito group doesn't exist
            else:
                logger.error(f"Failed to delete Cognito group: {str(e)}")
                metrics.add_metric(
                    name="CognitoGroupDeletionError", unit=MetricUnit.Count, value=1
                )
                raise

        # Step 4: Delete from DynamoDB in batches
        logger.info(f"Deleting DynamoDB items for group: {group_id}")
        batch_size = 25  # DynamoDB batch write limit

        for i in range(0, len(items), batch_size):
            batch_items = items[i : i + batch_size]

            # Prepare batch delete request
            delete_requests = []
            for item in batch_items:
                delete_requests.append(
                    {"DeleteRequest": {"Key": {"PK": item["PK"], "SK": item["SK"]}}}
                )

            # Execute batch delete
            if delete_requests:
                dynamodb.batch_write_item(RequestItems={table_name: delete_requests})

        logger.info(
            f"Successfully deleted group and {len(items)} related items from DynamoDB",
            extra={"group_id": group_id},
        )
        metrics.add_metric(name="DynamoDBGroupDeleted", unit=MetricUnit.Count, value=1)

    except Exception as e:
        logger.error(f"Error during group deletion: {str(e)}")
        metrics.add_metric(name="GroupDeletionError", unit=MetricUnit.Count, value=1)

        # Rollback: Restore DynamoDB items if Cognito was deleted but DynamoDB deletion failed
        if cognito_deleted and dynamodb_backup:
            try:
                logger.info(f"Rolling back: recreating Cognito group: {group_id}")

                # Find the group metadata to get description
                group_metadata = None
                for item in dynamodb_backup:
                    if item.get("SK") == "METADATA":
                        group_metadata = item
                        break

                if group_metadata:
                    cognito_client.create_group(
                        GroupName=group_id,
                        UserPoolId=cognito_user_pool_id,
                        Description=group_metadata.get("description", "Restored group"),
                    )
                    logger.info(f"Successfully rolled back Cognito group: {group_id}")
                    metrics.add_metric(
                        name="CognitoRollbackSuccess", unit=MetricUnit.Count, value=1
                    )
                else:
                    logger.error(
                        f"Could not find group metadata for rollback: {group_id}"
                    )
                    metrics.add_metric(
                        name="CognitoRollbackError", unit=MetricUnit.Count, value=1
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
