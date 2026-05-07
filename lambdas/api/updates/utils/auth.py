"""
Authentication and authorization utilities for the auto-upgrade system.
"""

import json
import logging
from typing import Any, Dict

from aws_lambda_powertools.event_handler.exceptions import UnauthorizedError

logger = logging.getLogger(__name__)


def validate_super_admin_access(event: Dict[str, Any]) -> str:
    """
    Validate that the user has superAdministrators group membership.

    Args:
        event: Lambda event containing request context

    Returns:
        User email if authorized

    Raises:
        UnauthorizedError: If user is not authorized
    """
    try:
        # Extract user information from the request context
        request_context = event.get("requestContext", {})
        authorizer = request_context.get("authorizer", {})

        # DEBUG: Log the entire authorizer context
        logger.info(f"DEBUG: Full authorizer context keys: {list(authorizer.keys())}")
        logger.info(f"DEBUG: Authorizer context: {json.dumps(authorizer, default=str)}")

        # The custom authorizer stores claims as a JSON string
        claims_str = authorizer.get("claims", "{}")
        logger.info(
            f"DEBUG: Raw claims string: {claims_str[:200]}..."
        )  # First 200 chars

        try:
            claims = (
                json.loads(claims_str) if isinstance(claims_str, str) else claims_str
            )
            logger.info(
                f"DEBUG: Parsed claims keys: {list(claims.keys()) if isinstance(claims, dict) else 'not a dict'}"
            )
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse claims JSON: {e}, claims_str: {claims_str}")
            claims = {}

        # Get user groups from cognito:groups claim
        user_groups = claims.get("cognito:groups", [])
        logger.info(
            f"DEBUG: Raw user_groups from cognito:groups: {user_groups}, type: {type(user_groups)}"
        )

        if isinstance(user_groups, str):
            # Sometimes groups might be a JSON string
            try:
                user_groups = json.loads(user_groups)
                logger.info(
                    f"DEBUG: Parsed user_groups from JSON string: {user_groups}"
                )
            except json.JSONDecodeError:
                user_groups = [user_groups]
                logger.info(f"DEBUG: Wrapped user_groups as list: {user_groups}")

        # Get user email from claims
        user_email = claims.get(
            "email",
            claims.get("cognito:username", authorizer.get("username", "unknown")),
        )

        logger.info(
            f"Authorization check for user: {user_email}, groups: {user_groups}"
        )

        # Check if user is in superAdministrators group
        if "superAdministrators" not in user_groups:
            logger.warning(
                f"Access denied for user {user_email}. "
                f"Required group: superAdministrators, User groups: {user_groups}, "
                f"All claims: {list(claims.keys())}"
            )
            raise UnauthorizedError(
                "Access denied. Requires superAdministrators group membership."
            )

        logger.info(f"Access granted for super administrator: {user_email}")
        return user_email

    except UnauthorizedError:
        # Re-raise UnauthorizedError as-is
        raise
    except KeyError as e:
        logger.error(f"Missing required authorization context: {e}")
        logger.error(f"DEBUG: request_context keys: {list(request_context.keys())}")
        raise UnauthorizedError("Invalid authorization context")
    except Exception as e:
        logger.error(f"Authorization validation failed: {e}", exc_info=True)
        raise UnauthorizedError("Authorization validation failed")


def get_user_email(event: Dict[str, Any]) -> str:
    """
    Extract user email from the request context.

    Args:
        event: Lambda event containing request context

    Returns:
        User email
    """
    try:
        request_context = event.get("requestContext", {})
        authorizer = request_context.get("authorizer", {})
        return authorizer.get("email", "unknown")
    except Exception:
        return "unknown"
