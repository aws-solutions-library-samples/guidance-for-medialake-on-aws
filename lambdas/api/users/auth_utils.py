"""Shared authentication utilities for user service handlers."""

from typing import Optional


def get_authenticated_user_id(app, logger) -> Optional[str]:
    """
    Extract the authenticated user's ID from the request context.

    Checks authorizer.userId first (custom authorizer format),
    then falls back to claims.sub (Cognito authorizer format).

    Args:
        app: The APIGatewayRestResolver instance
        logger: Logger instance

    Returns:
        The user ID string, or None if not found
    """
    request_context = app.current_event.raw_event.get("requestContext", {})
    authorizer = request_context.get("authorizer", {})

    # Custom authorizer puts userId at top level
    user_id = authorizer.get("userId")

    # Cognito authorizer puts it in claims.sub
    if not user_id:
        claims = authorizer.get("claims", {})
        user_id = claims.get("sub")

    if not user_id:
        logger.error(
            {
                "message": "Could not extract user ID from request context",
                "authorizer_keys": list(authorizer.keys()),
                "operation": "get_authenticated_user_id",
            }
        )

    return user_id
