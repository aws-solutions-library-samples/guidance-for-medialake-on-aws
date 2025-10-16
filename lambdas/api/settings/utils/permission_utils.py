"""Permission utilities for settings API."""

import json
from typing import Any, Dict

from aws_lambda_powertools import Logger
from aws_lambda_powertools.event_handler.exceptions import ForbiddenError

logger = Logger(service="permission-utils")


def check_admin_permission(user_context: dict) -> bool:
    """
    Check if user has admin permissions.

    Args:
        user_context: User context from the event

    Returns:
        True if user is admin

    Raises:
        ForbiddenError: If user is not an admin
    """
    # Check if user has admin role
    groups = user_context.get("groups", [])

    # Check for admin, superAdministrators, or administrators group (case-insensitive)
    admin_groups = ["admin", "superadministrators", "administrators"]
    is_admin = any(g.lower() in admin_groups for g in groups)

    if not is_admin:
        logger.warning(
            "Admin permission check failed",
            extra={"user_id": user_context.get("user_id"), "groups": groups},
        )
        raise ForbiddenError("Admin permission required for this operation")

    logger.info(
        "Admin permission check passed", extra={"user_id": user_context.get("user_id")}
    )
    return True


def extract_user_context(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract user context from API Gateway event.
    Uses the same pattern as the common user_auth.py library.

    Args:
        event: API Gateway event

    Returns:
        User context dictionary with user_id, username, email, and groups
    """
    try:
        request_context = event.get("requestContext")
        if not isinstance(request_context, dict):
            logger.debug(
                "No valid requestContext found",
                extra={
                    "request_context_type": type(request_context).__name__,
                    "operation": "extract_user_context",
                },
            )
            return {"user_id": None, "username": None, "email": "", "groups": []}

        authorizer = request_context.get("authorizer")
        if not isinstance(authorizer, dict):
            logger.debug(
                "No valid authorizer found",
                extra={
                    "authorizer_type": type(authorizer).__name__,
                    "operation": "extract_user_context",
                },
            )
            return {"user_id": None, "username": None, "email": "", "groups": []}

        claims = authorizer.get("claims")

        # Handle claims as either dict or JSON string (critical fix!)
        if isinstance(claims, str):
            try:
                claims = json.loads(claims)
                logger.debug(
                    "Parsed claims from JSON string",
                    extra={"operation": "extract_user_context"},
                )
            except (json.JSONDecodeError, ValueError) as e:
                logger.warning(
                    "Failed to parse claims JSON string",
                    extra={
                        "error": str(e),
                        "claims_preview": (
                            claims[:200]
                            if isinstance(claims, str)
                            else str(claims)[:200]
                        ),
                        "operation": "extract_user_context",
                    },
                )
                return {"user_id": None, "username": None, "email": "", "groups": []}
        elif not isinstance(claims, dict):
            logger.debug(
                "Claims is neither dict nor string",
                extra={
                    "claims_type": type(claims).__name__,
                    "operation": "extract_user_context",
                },
            )
            return {"user_id": None, "username": None, "email": "", "groups": []}

        # Extract user information from claims
        user_id = claims.get("sub")
        username = claims.get("cognito:username")
        email = claims.get("email", "")

        # Extract groups - handle both list and string formats
        groups_raw = claims.get("cognito:groups", [])
        if isinstance(groups_raw, str):
            # Sometimes groups come as a JSON string
            try:
                groups = json.loads(groups_raw)
            except (json.JSONDecodeError, ValueError):
                groups = [groups_raw] if groups_raw else []
        elif isinstance(groups_raw, list):
            groups = groups_raw
        else:
            groups = []

        user_context = {
            "user_id": user_id,
            "username": username,
            "email": email,
            "groups": groups,
        }

        logger.debug(
            "User context extracted",
            extra={
                "user_id": user_id,
                "username": username,
                "groups": groups,
                "operation": "extract_user_context",
            },
        )

        return user_context

    except Exception as e:
        logger.warning(
            "Failed to extract user context",
            extra={
                "error": str(e),
                "operation": "extract_user_context",
                "event_keys": (
                    list(event.keys()) if isinstance(event, dict) else "event_not_dict"
                ),
            },
        )
        return {"user_id": None, "username": None, "email": "", "groups": []}
