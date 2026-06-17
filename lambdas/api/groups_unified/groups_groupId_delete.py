"""DELETE /groups/{groupId} - Delete a group"""

import time
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


def _batch_write_with_retry(
    dynamodb, table_name: str, requests: list, logger, max_attempts: int = 5
) -> int:
    """Run BatchWriteItem, retrying any UnprocessedItems with backoff.

    DynamoDB can return some requests as ``UnprocessedItems`` under throttling
    even on a successful (200) call. Without retrying them the corresponding
    rows are silently left behind. Returns the number of requests still
    unprocessed after all attempts (0 on full success).
    """
    pending = requests
    for attempt in range(max_attempts):
        response = dynamodb.batch_write_item(RequestItems={table_name: pending})
        unprocessed = response.get("UnprocessedItems", {}).get(table_name, [])
        if not unprocessed:
            return 0
        pending = unprocessed
        logger.warning(
            f"BatchWriteItem left {len(unprocessed)} unprocessed item(s); "
            f"retrying (attempt {attempt + 1}/{max_attempts})"
        )
        time.sleep(min(2**attempt * 0.05, 1.0))
    return len(pending)


def _delete_group_with_rollback(
    dynamodb,
    table_name: str,
    cognito_user_pool_id: str,
    group_id: str,
    cognito,
    logger,
    metrics,
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
            cognito.delete_group(GroupName=group_id, UserPoolId=cognito_user_pool_id)
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

        # Step 4: Delete the associated Permission Set (if any)
        group_metadata = None
        for item in items:
            if item.get("SK") == "METADATA":
                group_metadata = item
                break

        if group_metadata:
            permission_set_id = group_metadata.get("permissionSetId")
            assigned_ps = group_metadata.get("assignedPermissionSets", [])

            # Collect all permission set IDs to delete
            ps_ids_to_delete = set()
            if permission_set_id:
                ps_ids_to_delete.add(permission_set_id)
            if assigned_ps:
                for ps_id in assigned_ps:
                    ps_ids_to_delete.add(ps_id)

            for ps_id in ps_ids_to_delete:
                try:
                    logger.info(
                        f"Deleting associated permission set: {ps_id}",
                        extra={"group_id": group_id},
                    )
                    table.delete_item(Key={"PK": f"PS#{ps_id}", "SK": "METADATA"})
                    logger.info(
                        f"Successfully deleted permission set: {ps_id}",
                        extra={"group_id": group_id},
                    )
                    metrics.add_metric(
                        name="PermissionSetAutoDeleted",
                        unit=MetricUnit.Count,
                        value=1,
                    )
                except ClientError as ps_error:
                    # Log but don't fail - continue with group deletion
                    logger.warning(
                        f"Failed to delete permission set: {ps_id}: {str(ps_error)}",
                        extra={"group_id": group_id},
                    )

        # Step 5: Delete from DynamoDB in batches.
        # Memberships are stored as a pair: a forward row under the group
        # partition (PK=GROUP#{id}, SK=MEMBERSHIP#USER#{user}) and a reverse row
        # under the user's partition (PK=USER#{user}, SK=MEMBERSHIP#GROUP#{id}).
        # The query above only returned the forward rows, so we derive and delete
        # the matching reverse rows too — otherwise they orphan in each member's
        # partition and keep showing up in that user's group listings.
        delete_keys = [{"PK": item["PK"], "SK": item["SK"]} for item in items]

        membership_prefix = "MEMBERSHIP#USER#"
        for item in items:
            sk = item.get("SK", "")
            if sk.startswith(membership_prefix):
                member_user_id = item.get("userId") or sk[len(membership_prefix) :]
                if member_user_id:
                    delete_keys.append(
                        {
                            "PK": f"USER#{member_user_id}",
                            "SK": f"MEMBERSHIP#GROUP#{group_id}",
                        }
                    )

        logger.info(f"Deleting DynamoDB items for group: {group_id}")
        batch_size = 25  # DynamoDB batch write limit

        unprocessed_total = 0
        for i in range(0, len(delete_keys), batch_size):
            batch_keys = delete_keys[i : i + batch_size]

            # Prepare batch delete request
            delete_requests = [{"DeleteRequest": {"Key": key}} for key in batch_keys]

            # Execute batch delete, retrying any throttled (unprocessed) items
            if delete_requests:
                unprocessed_total += _batch_write_with_retry(
                    dynamodb, table_name, delete_requests, logger
                )

        if unprocessed_total:
            # Best-effort cleanup: don't fail the whole deletion (and trigger a
            # confusing rollback) over a few throttled rows, but make the gap
            # visible via logs + a metric instead of silently dropping them.
            logger.error(
                f"{unprocessed_total} item(s) could not be deleted for group "
                f"{group_id} after retries"
            )
            metrics.add_metric(
                name="GroupDeleteUnprocessedItems",
                unit=MetricUnit.Count,
                value=unprocessed_total,
            )

        logger.info(
            f"Successfully deleted group and {len(delete_keys)} item(s) from DynamoDB",
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
        _delete_group_with_rollback(
            dynamodb, table_name, user_pool_id, group_id, cognito, logger, metrics
        )

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
