"""POST /users/profile/change-password - Change the authenticated user's password"""

import json
from typing import Any, Dict

from auth_utils import get_authenticated_user_id
from aws_lambda_powertools.metrics import MetricUnit
from botocore.exceptions import ClientError
from response_utils import error_response, success_response


def handle_change_password(
    app, cognito, user_pool_id: str, logger, metrics, tracer
) -> Dict[str, Any]:
    """
    Self-service password change for the currently authenticated user.

    Expects JSON body: { "current_password": "...", "new_password": "..." }
    Uses AdminInitiateAuth to verify the current password, then
    AdminSetUserPassword to set the new one.
    """
    try:
        user_id = get_authenticated_user_id(app, logger)
        if not user_id:
            return error_response(401, "Unable to identify authenticated user")

        body = json.loads(app.current_event.body or "{}")
        current_password = body.get("current_password", "").strip()
        new_password = body.get("new_password", "").strip()

        if not current_password or not new_password:
            return error_response(
                400, "Both current_password and new_password are required"
            )

        if current_password == new_password:
            return error_response(
                400, "New password must be different from current password"
            )

        # Verify current password via AdminInitiateAuth
        try:
            cognito.admin_initiate_auth(
                UserPoolId=user_pool_id,
                ClientId=_get_client_id(cognito, user_pool_id),
                AuthFlow="ADMIN_USER_PASSWORD_AUTH",
                AuthParameters={
                    "USERNAME": user_id,
                    "PASSWORD": current_password,
                },
            )
        except ClientError as e:
            code = e.response["Error"]["Code"]
            if code in ("NotAuthorizedException", "UserNotFoundException"):
                metrics.add_metric(
                    name="ChangePasswordWrongCurrent",
                    unit=MetricUnit.Count,
                    value=1,
                )
                return error_response(403, "Current password is incorrect")
            raise

        # Set the new password
        cognito.admin_set_user_password(
            UserPoolId=user_pool_id,
            Username=user_id,
            Password=new_password,
            Permanent=True,
        )

        metrics.add_metric(name="ChangePasswordSuccess", unit=MetricUnit.Count, value=1)
        logger.info("Password changed successfully", extra={"user_id": user_id})

        return success_response(200, "Password changed successfully")

    except ClientError as e:
        code = e.response["Error"]["Code"]
        logger.error(
            "Cognito error during password change",
            extra={"error_code": code, "error": str(e)},
        )
        metrics.add_metric(name="ChangePasswordError", unit=MetricUnit.Count, value=1)
        if code == "InvalidPasswordException":
            return error_response(
                400,
                "New password does not meet requirements. "
                "Must be at least 8 characters with uppercase, lowercase, number, and symbol.",
            )
        return error_response(500, "Internal server error")

    except Exception:
        logger.exception("Unexpected error during password change")
        metrics.add_metric(name="ChangePasswordError", unit=MetricUnit.Count, value=1)
        return error_response(500, "Internal server error")


def _get_client_id(cognito, user_pool_id: str) -> str:
    """Get the first app client ID for the user pool."""
    resp = cognito.list_user_pool_clients(UserPoolId=user_pool_id, MaxResults=1)
    clients = resp.get("UserPoolClients", [])
    if not clients:
        raise RuntimeError("No app client found for user pool")
    return clients[0]["ClientId"]
