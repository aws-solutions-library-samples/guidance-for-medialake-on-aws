"""DELETE /users/{user_id} - Delete a user"""

import json
from typing import Any, Dict

from aws_lambda_powertools.metrics import MetricUnit
from botocore.exceptions import ClientError


def handle_delete_user(
    user_id: str, cognito, user_pool_id: str, logger, metrics, tracer
) -> Dict[str, Any]:
    """
    Delete a user from Cognito user pool

    Args:
        user_id: The user ID to delete

    Returns:
        API Gateway response
    """
    try:
        logger.info(f"Received request to delete user {user_id}")

        if not user_id:
            logger.error("Missing user_id in path parameters")
            metrics.add_metric(
                name="MissingUserIdError", unit=MetricUnit.Count, value=1
            )
            return {
                "statusCode": 400,
                "body": json.dumps({"message": "Missing user_id parameter"}),
            }

        # Delete user from Cognito
        cognito.admin_delete_user(UserPoolId=user_pool_id, Username=user_id)

        metrics.add_metric(
            name="UserDeletionSuccessful", unit=MetricUnit.Count, value=1
        )

        logger.info(
            {
                "message": "User deleted successfully",
                "user_id": user_id,
                "operation": "delete_user",
                "status": "success",
            }
        )

        return {
            "statusCode": 200,
            "body": json.dumps(
                {"message": f"User {user_id} successfully deleted", "userId": user_id}
            ),
        }

    except cognito.exceptions.UserNotFoundException:
        logger.warning(f"User {user_id} not found in Cognito user pool")
        metrics.add_metric(name="UserDeletionNotFound", unit=MetricUnit.Count, value=1)
        return {
            "statusCode": 404,
            "body": json.dumps({"message": "User not found", "userId": user_id}),
        }

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        error_message = e.response["Error"]["Message"]

        logger.error(
            {
                "message": "Failed to delete user",
                "user_id": user_id,
                "error_code": error_code,
                "error_message": error_message,
            }
        )

        metrics.add_metric(name="UserDeletionError", unit=MetricUnit.Count, value=1)
        return {
            "statusCode": 500,
            "body": json.dumps(
                {
                    "message": "Internal server error while deleting user",
                    "userId": user_id,
                }
            ),
        }

    except Exception as e:
        logger.error(
            {
                "message": "Unexpected error while deleting user",
                "error": str(e),
                "user_id": user_id,
            }
        )

        metrics.add_metric(name="UnexpectedError", unit=MetricUnit.Count, value=1)
        return {
            "statusCode": 500,
            "body": json.dumps({"message": "Internal server error"}),
        }
