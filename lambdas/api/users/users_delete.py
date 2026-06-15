"""DELETE /users/{user_id} - Delete a user"""

import json
from typing import Any, Dict

from aws_lambda_powertools.metrics import MetricUnit
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError
from collections_migration import trigger_collection_migration


def _cleanup_user_data(dynamodb, table_name: str, user_id: str, logger) -> int:
    """
    Remove all DynamoDB records for a deleted user (profile, settings, favorites).

    Args:
        dynamodb: boto3 DynamoDB resource
        table_name: The user table name
        user_id: The user's Cognito sub / username
        logger: Logger instance

    Returns:
        Number of items deleted
    """
    formatted_user_id = f"USER#{user_id}"
    table = dynamodb.Table(table_name)
    deleted_count = 0

    try:
        # Query all items for this user
        params = {
            "KeyConditionExpression": Key("userId").eq(formatted_user_id),
        }

        while True:
            response = table.query(**params)
            items = response.get("Items", [])

            # Batch delete all items
            with table.batch_writer() as batch:
                for item in items:
                    batch.delete_item(
                        Key={
                            "userId": item["userId"],
                            "itemKey": item["itemKey"],
                        }
                    )
                    deleted_count += 1

            # Handle pagination
            last_key = response.get("LastEvaluatedKey")
            if not last_key:
                break
            params["ExclusiveStartKey"] = last_key

        if deleted_count > 0:
            logger.info(
                {
                    "message": "Cleaned up user data from DynamoDB",
                    "user_id": user_id,
                    "items_deleted": deleted_count,
                    "operation": "cleanup_user_data",
                }
            )

    except ClientError as e:
        # Log but don't fail the delete — Cognito user is already gone
        logger.error(
            {
                "message": "Failed to clean up user data from DynamoDB",
                "user_id": user_id,
                "error_code": e.response["Error"]["Code"],
                "error_message": e.response["Error"]["Message"],
                "operation": "cleanup_user_data",
            }
        )

    return deleted_count


def handle_delete_user(
    user_id: str,
    cognito,
    user_pool_id: str,
    logger,
    metrics,
    tracer,
    dynamodb=None,
    user_table_name: str = None,
    collections_table_name: str = None,
    new_collection_owner_id: str = None,
) -> Dict[str, Any]:
    """
    Delete a user from Cognito user pool and clean up their DynamoDB data.

    Collections owned by the deleted user are migrated to
    ``new_collection_owner_id`` (the administrator performing the deletion) so
    they are not orphaned.
    """
    try:
        if not user_id:
            logger.error("Missing user_id in path parameters")
            metrics.add_metric(
                name="MissingUserIdError", unit=MetricUnit.Count, value=1
            )
            return {
                "statusCode": 400,
                "body": json.dumps({"message": "Missing user_id parameter"}),
            }

        # Refuse self-deletion. Besides being a footgun, deleting the calling
        # admin would leave their owned collections with nobody to migrate to
        # (the migration's new owner is the caller), orphaning them.
        if new_collection_owner_id and new_collection_owner_id == user_id:
            logger.warning(
                {
                    "message": "User attempted to delete their own account",
                    "user_id": user_id,
                    "operation": "delete_user",
                }
            )
            metrics.add_metric(
                name="SelfDeletionBlocked", unit=MetricUnit.Count, value=1
            )
            return {
                "statusCode": 400,
                "body": json.dumps({"message": "You cannot delete your own account."}),
            }

        # Delete user from Cognito
        cognito.admin_delete_user(UserPoolId=user_pool_id, Username=user_id)

        metrics.add_metric(
            name="UserDeletionSuccessful", unit=MetricUnit.Count, value=1
        )

        logger.info(
            {
                "message": "User deleted successfully from Cognito",
                "user_id": user_id,
                "operation": "delete_user",
                "status": "success",
            }
        )

        # Migrate collections owned by the deleted user to a new owner so they
        # are not orphaned. Offloaded to an async self-invocation so the API
        # call returns promptly regardless of how many collections are owned;
        # failures there are logged and retried by Lambda, never failing the
        # delete (the Cognito user is already gone).
        if collections_table_name:
            trigger_collection_migration(
                user_id,
                new_collection_owner_id,
                logger,
            )

        # Clean up DynamoDB user data if table info is available
        if dynamodb and user_table_name:
            _cleanup_user_data(dynamodb, user_table_name, user_id, logger)

        return {
            "statusCode": 200,
            "body": json.dumps(
                {"message": f"User {user_id} successfully deleted", "userId": user_id}
            ),
        }

    except cognito.exceptions.UserNotFoundException:
        logger.warning(
            {
                "message": "User not found in Cognito user pool",
                "user_id": user_id,
                "operation": "delete_user",
            }
        )
        metrics.add_metric(name="UserDeletionNotFound", unit=MetricUnit.Count, value=1)
        return {
            "statusCode": 404,
            "body": json.dumps({"message": "User not found", "userId": user_id}),
        }

    except ClientError as e:
        logger.error(
            {
                "message": "Failed to delete user",
                "user_id": user_id,
                "error_code": e.response["Error"]["Code"],
                "error_message": e.response["Error"]["Message"],
            }
        )
        metrics.add_metric(name="UserDeletionError", unit=MetricUnit.Count, value=1)
        return {
            "statusCode": 500,
            "body": json.dumps({"message": "Internal server error"}),
        }

    except Exception:
        logger.exception(
            "Unexpected error while deleting user",
            extra={"user_id": user_id},
        )
        metrics.add_metric(name="UnexpectedError", unit=MetricUnit.Count, value=1)
        return {
            "statusCode": 500,
            "body": json.dumps({"message": "Internal server error"}),
        }
