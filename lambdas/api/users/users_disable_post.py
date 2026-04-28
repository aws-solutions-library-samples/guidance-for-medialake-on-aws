"""POST /users/{user_id}/disable - Disable a user"""

from typing import Any, Dict

from aws_lambda_powertools.metrics import MetricUnit
from botocore.exceptions import ClientError
from pydantic import BaseModel, Field


class DisableUserRequest(BaseModel):
    user_id: str = Field(..., min_length=1, description="The user ID to disable")


def handle_disable_user(
    user_id: str, cognito, user_pool_id: str, logger, metrics, tracer
) -> Dict[str, Any]:
    """
    Lambda handler to disable a user in Cognito User Pool
    """
    try:
        if not user_id:
            logger.error("Missing user_id in path parameters")
            return {
                "statusCode": 400,
                "body": '{"message": "Missing user_id parameter"}',
            }

        DisableUserRequest(user_id=user_id)

        logger.debug(
            {
                "message": "Attempting to disable user",
                "user_id": user_id,
                "user_pool_id": user_pool_id,
            }
        )

        cognito.admin_disable_user(UserPoolId=user_pool_id, Username=user_id)

        metrics.add_metric(name="UserDisabled", unit=MetricUnit.Count, value=1)

        logger.info(
            {
                "message": "Successfully disabled user",
                "user_id": user_id,
                "operation": "disable_user",
                "status": "success",
            }
        )

        return {"statusCode": 200, "body": '{"message": "User successfully disabled"}'}

    except ClientError as e:
        error_code = e.response["Error"]["Code"]

        logger.error(
            {
                "message": "Cognito client error",
                "error_code": error_code,
                "error_message": e.response["Error"]["Message"],
                "user_id": user_id,
            }
        )

        metrics.add_metric(name="UserDisableError", unit=MetricUnit.Count, value=1)

        if error_code == "UserNotFoundException":
            return {"statusCode": 404, "body": '{"message": "User not found"}'}

        return {"statusCode": 500, "body": '{"message": "Internal server error"}'}

    except Exception:
        logger.exception(
            "Unexpected error while disabling user",
            extra={"user_id": user_id},
        )
        metrics.add_metric(name="UnexpectedError", unit=MetricUnit.Count, value=1)
        return {"statusCode": 500, "body": '{"message": "Internal server error"}'}
