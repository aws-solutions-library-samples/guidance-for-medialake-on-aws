"""POST /users/{user_id}/reset-password - Reset a user's password (admin action)"""

from typing import Any, Dict

from aws_lambda_powertools.metrics import MetricUnit
from botocore.exceptions import ClientError
from pydantic import BaseModel, Field


class ResetPasswordRequest(BaseModel):
    user_id: str = Field(
        ..., min_length=1, description="The user ID to reset password for"
    )


def handle_reset_password(
    user_id: str, cognito, user_pool_id: str, logger, metrics, tracer
) -> Dict[str, Any]:
    """
    Admin-initiated password reset for a Cognito user.

    Calls AdminResetUserPassword which invalidates the user's current password
    and sends them a password reset verification code/link via email.
    """
    try:
        if not user_id:
            logger.error("Missing user_id in path parameters")
            return {
                "statusCode": 400,
                "body": '{"message": "Missing user_id parameter"}',
            }

        ResetPasswordRequest(user_id=user_id)

        logger.debug(
            {
                "message": "Attempting to reset user password",
                "user_id": user_id,
                "user_pool_id": user_pool_id,
            }
        )

        cognito.admin_reset_user_password(UserPoolId=user_pool_id, Username=user_id)

        metrics.add_metric(name="UserPasswordReset", unit=MetricUnit.Count, value=1)

        logger.info(
            {
                "message": "Successfully initiated password reset",
                "user_id": user_id,
                "operation": "reset_password",
                "status": "success",
            }
        )

        return {
            "statusCode": 200,
            "body": '{"message": "Password reset initiated. User will receive an email with instructions."}',
        }

    except ClientError as e:
        error_code = e.response["Error"]["Code"]

        logger.error(
            {
                "message": "Cognito client error during password reset",
                "error_code": error_code,
                "error_message": e.response["Error"]["Message"],
                "user_id": user_id,
            }
        )

        metrics.add_metric(
            name="UserPasswordResetError", unit=MetricUnit.Count, value=1
        )

        if error_code == "UserNotFoundException":
            return {"statusCode": 404, "body": '{"message": "User not found"}'}
        if error_code == "InvalidParameterException":
            return {
                "statusCode": 400,
                "body": '{"message": "Cannot reset password. User may not have a verified email."}',
            }
        return {"statusCode": 500, "body": '{"message": "Internal server error"}'}

    except Exception:
        logger.exception(
            "Unexpected error during password reset",
            extra={"user_id": user_id},
        )
        metrics.add_metric(name="UnexpectedError", unit=MetricUnit.Count, value=1)
        return {"statusCode": 500, "body": '{"message": "Internal server error"}'}
