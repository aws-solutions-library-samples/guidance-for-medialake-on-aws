"""POST /users/password-recovery - Self-service recovery for users with an
expired or lost temporary password (unauthenticated).

Cognito's ForgotPassword flow rejects users who are still in
FORCE_CHANGE_PASSWORD status (the initial user, or any admin-created user who
never completed first sign-in) with "User password cannot be reset in the
current state". This endpoint gives those users a self-service path: it
resends the invitation email with a fresh temporary password.

Security properties:
- Enumeration-safe: every request returns the same generic 200 response,
  whether the user exists, is confirmed, or is in FORCE_CHANGE_PASSWORD.
- Only acts on FORCE_CHANGE_PASSWORD users; confirmed users are directed
  through the normal Cognito ForgotPassword flow by the frontend.
- Rate-limited at the WAF (scoped rate-based rule on this path) and by a
  per-account resend cooldown enforced with an atomic DynamoDB conditional
  write, so a distributed attacker cannot flood a victim's inbox or
  continuously rotate their temporary password.
"""

import json
import time
from typing import Any, Dict

from aws_lambda_powertools.metrics import MetricUnit
from botocore.exceptions import ClientError
from pydantic import BaseModel, Field, ValidationError

# Minimum seconds between temporary-password resends for the same account.
# Blunts targeted inbox-flooding / temp-password rotation abuse that a per-IP
# WAF rule cannot stop (distributed sources).
RESEND_COOLDOWN_SECONDS = 15 * 60

# Generic response returned in all cases to prevent user enumeration.
_GENERIC_RESPONSE = {
    "statusCode": 200,
    "body": json.dumps(
        {
            "message": (
                "If an account exists for this email and requires a new "
                "temporary password, one has been sent."
            )
        }
    ),
}


class PasswordRecoveryRequest(BaseModel):
    email: str = Field(
        ..., min_length=3, max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
    )


def _acquire_resend_cooldown(user_table, user_sub: str) -> bool:
    """Atomically claim the resend cooldown slot for this account.

    Returns True if this request may send a resend email, False if another
    resend happened within the cooldown window. Keyed on the immutable
    Cognito ``sub`` (not email or IP) so the limit follows the account.
    Fails open on infrastructure errors so a DynamoDB issue cannot lock
    users out of recovery.
    """
    now = int(time.time())
    try:
        user_table.put_item(
            Item={
                "userId": f"RECOVERY#{user_sub}",
                "itemKey": "TEMP_PASSWORD_RESEND",
                "lastSentAt": now,
                "expiresAt": now + RESEND_COOLDOWN_SECONDS,
            },
            ConditionExpression=(
                "attribute_not_exists(lastSentAt) OR lastSentAt < :cutoff"
            ),
            ExpressionAttributeValues={":cutoff": now - RESEND_COOLDOWN_SECONDS},
        )
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return False
        # Fail open: cooldown is an abuse mitigation, not a correctness
        # requirement; the WAF rate rule still applies.
        return True


def handle_password_recovery(
    app, cognito, user_table, user_pool_id: str, logger, metrics, tracer
) -> Dict[str, Any]:
    """Resend a temporary password to a FORCE_CHANGE_PASSWORD user."""
    try:
        try:
            request = PasswordRecoveryRequest(**(app.current_event.json_body or {}))
        except (ValidationError, TypeError, ValueError):
            # Invalid input gets the same generic response — no oracle.
            return _GENERIC_RESPONSE

        try:
            user = cognito.admin_get_user(
                UserPoolId=user_pool_id, Username=request.email
            )
        except ClientError as e:
            if e.response["Error"]["Code"] == "UserNotFoundException":
                logger.info(
                    {
                        "message": "Password recovery requested for unknown user",
                        "operation": "password_recovery",
                    }
                )
                return _GENERIC_RESPONSE
            raise

        if user.get("UserStatus") == "FORCE_CHANGE_PASSWORD":
            user_sub = next(
                (
                    attr["Value"]
                    for attr in user.get("UserAttributes", [])
                    if attr["Name"] == "sub"
                ),
                request.email,
            )
            if not _acquire_resend_cooldown(user_table, user_sub):
                # Cooldown active: same generic response, no email sent.
                logger.info(
                    {
                        "message": "Temporary password resend suppressed by cooldown",
                        "operation": "password_recovery",
                    }
                )
                metrics.add_metric(
                    name="TemporaryPasswordResendThrottled",
                    unit=MetricUnit.Count,
                    value=1,
                )
                return _GENERIC_RESPONSE

            cognito.admin_create_user(
                UserPoolId=user_pool_id,
                Username=request.email,
                MessageAction="RESEND",
            )
            metrics.add_metric(
                name="TemporaryPasswordResent", unit=MetricUnit.Count, value=1
            )
            logger.info(
                {
                    "message": "Resent invitation with new temporary password",
                    "operation": "password_recovery",
                    "status": "success",
                }
            )
        else:
            # Confirmed / other statuses: the standard ForgotPassword flow
            # applies; nothing to do here.
            logger.info(
                {
                    "message": "Password recovery requested for user not in FORCE_CHANGE_PASSWORD; no action taken",
                    "user_status": user.get("UserStatus"),
                    "operation": "password_recovery",
                }
            )

        return _GENERIC_RESPONSE

    except Exception:
        # Even on unexpected failure, do not leak details to the caller.
        logger.exception("Unexpected error during password recovery")
        metrics.add_metric(name="PasswordRecoveryError", unit=MetricUnit.Count, value=1)
        return _GENERIC_RESPONSE
