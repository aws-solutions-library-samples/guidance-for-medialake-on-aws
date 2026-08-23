"""POST /users/{user_id}/reset-password - Reset a user's password (admin action)"""

import json
from typing import Any, Dict

from aws_lambda_powertools.metrics import MetricUnit
from botocore.exceptions import ClientError
from pydantic import BaseModel, Field


class ResetPasswordRequest(BaseModel):
    user_id: str = Field(
        ..., min_length=1, description="The user ID to reset password for"
    )


def _resend_temporary_password(cognito, user_pool_id: str, username: str) -> None:
    """Resend the invitation email with a fresh temporary password.

    Used for users still in FORCE_CHANGE_PASSWORD status (initial user or
    admin-created users who never completed first sign-in). Cognito rejects
    AdminResetUserPassword for these users, so the supported recovery path is
    AdminCreateUser with MessageAction=RESEND, which generates a new temporary
    password and restarts the validity window.
    """
    cognito.admin_create_user(
        UserPoolId=user_pool_id,
        Username=username,
        MessageAction="RESEND",
    )


def handle_reset_password(
    user_id: str, cognito, user_pool_id: str, logger, metrics, tracer
) -> Dict[str, Any]:
    """
    Admin-initiated password reset for a Cognito user.

    For confirmed users, calls AdminResetUserPassword which invalidates the
    current password and emails a verification code. For users still in
    FORCE_CHANGE_PASSWORD status (never completed first sign-in), resends the
    invitation email with a new temporary password instead, since Cognito does
    not allow a reset in that state.
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

        user = cognito.admin_get_user(UserPoolId=user_pool_id, Username=user_id)
        user_status = user.get("UserStatus")

        if user_status == "FORCE_CHANGE_PASSWORD":
            _resend_temporary_password(cognito, user_pool_id, user_id)
            metrics.add_metric(
                name="TemporaryPasswordResent", unit=MetricUnit.Count, value=1
            )
            logger.info(
                {
                    "message": "User has not completed first sign-in; resent invitation with new temporary password",
                    "user_id": user_id,
                    "operation": "reset_password",
                    "status": "success",
                }
            )
            return {
                "statusCode": 200,
                "body": json.dumps(
                    {
                        "message": "User has not signed in yet. A new temporary password has been emailed to them."
                    }
                ),
            }

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
        error_message = e.response["Error"]["Message"]

        # Race-safety: if the user slipped into FORCE_CHANGE_PASSWORD between
        # the status check and the reset call, fall back to resending the
        # invitation instead of failing.
        if error_code == "NotAuthorizedException" and "current state" in error_message:
            try:
                _resend_temporary_password(cognito, user_pool_id, user_id)
                metrics.add_metric(
                    name="TemporaryPasswordResent", unit=MetricUnit.Count, value=1
                )
                return {
                    "statusCode": 200,
                    "body": json.dumps(
                        {
                            "message": "User has not signed in yet. A new temporary password has been emailed to them."
                        }
                    ),
                }
            except ClientError as resend_error:
                error_code = resend_error.response["Error"]["Code"]
                error_message = resend_error.response["Error"]["Message"]

        logger.error(
            {
                "message": "Cognito client error during password reset",
                "error_code": error_code,
                "error_message": error_message,
                "user_id": user_id,
            }
        )

        metrics.add_metric(
            name="UserPasswordResetError", unit=MetricUnit.Count, value=1
        )

        if error_code == "UserNotFoundException":
            return {"statusCode": 404, "body": '{"message": "User not found"}'}
        if error_code == "InvalidParameterException":
            # BUG-24: this branch previously returned a hard-coded
            # "User may not have a verified email" message, which sent admins
            # down the wrong rabbit hole — the real cause was usually the
            # user still being in FORCE_CHANGE_PASSWORD (handled at the top
            # of this function now). Surface Cognito's own message so the
            # admin sees the actual reason.
            return {
                "statusCode": 400,
                "body": json.dumps(
                    {
                        "message": (
                            f"Cognito rejected the password reset for this "
                            f"user: {error_message}"
                        )
                    }
                ),
            }
        return {"statusCode": 500, "body": '{"message": "Internal server error"}'}

    except Exception:
        logger.exception(
            "Unexpected error during password reset",
            extra={"user_id": user_id},
        )
        metrics.add_metric(name="UnexpectedError", unit=MetricUnit.Count, value=1)
        return {"statusCode": 500, "body": '{"message": "Internal server error"}'}
