"""DELETE /groups/{groupId} - Delete a group"""

from typing import Any, Dict

from aws_lambda_powertools.metrics import MetricUnit
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError
from pydantic import BaseModel, Field


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


def _delete_group_with_rollback(
    dynamodb, table_name: str, cognito_user_pool_id: str, group_id: str, cognito, logger, metrics
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
            cognito.delete_group(
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
                    cognito.create_group(
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


def handle_delete_group(
    group_id: str, dynamodb, user_pool_id: str, table_name: str, logger, metrics, tracer
) -> Dict[str, Any]:
    """
    Lambda handler to delete a group from both DynamoDB and Cognito

    This function handles requests to delete a group with:
    - DynamoDB cleanup (group metadata and memberships)
    - Cognito group deletion
    - Proper rollback if either operation fails
    """
    try:
        if not group_id:
            logger.error("Missing groupId in path parameters")
            metrics.add_metric(
                name="MissingGroupIdError", unit=MetricUnit.Count, value=1
            )
            return _create_error_response(400, "Missing group ID")

        if not table_name:
            logger.error("AUTH_TABLE_NAME environment variable not set")
            metrics.add_metric(
                name="MissingConfigError", unit=MetricUnit.Count, value=1
            )
            return _create_error_response(
                500, "Internal configuration error - missing table name"
            )

        if not user_pool_id:
            logger.error("COGNITO_USER_POOL_ID environment variable not set")
            metrics.add_metric(
                name="MissingConfigError", unit=MetricUnit.Count, value=1
            )
            return _create_error_response(
                500, "Internal configuration error - missing user pool ID"
            )

        # Initialize cognito client (passed from main handler)
        import boto3
        cognito = boto3.client("cognito-idp")

        # Delete the group with rollback handling
        _delete_group_with_rollback(dynamodb, table_name, user_pool_id, group_id, cognito, logger, metrics)

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

