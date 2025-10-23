"""
User authentication utilities for MediaLake Lambda functions.

This module provides standardized user authentication and authorization
functions that can be used across all Lambda functions in the MediaLake platform.
"""

import json
from functools import wraps
from typing import Any, Callable, Dict, Optional

from aws_lambda_powertools import Logger, Tracer

# Initialize PowerTools
logger = Logger(service="user-auth")
tracer = Tracer(service="user-auth")


@tracer.capture_method
def extract_user_context(event: Dict[str, Any]) -> Dict[str, Optional[str]]:
    """
    Extract user information from JWT token in event context.

    This function handles the standardized extraction of user information
    from API Gateway Lambda proxy integration events that include JWT claims
    from Cognito authorization.

    Args:
        event: Lambda event from API Gateway

    Returns:
        Dictionary with user_id and username, or None values if not found

    Example:
        >>> user_context = extract_user_context(event)
        >>> user_id = user_context.get("user_id")
        >>> username = user_context.get("username")
    """
    try:
        request_context = event.get("requestContext")
        if not isinstance(request_context, dict):
            logger.debug(
                {
                    "message": "No valid requestContext found",
                    "request_context_type": type(request_context).__name__,
                    "operation": "extract_user_context",
                }
            )
            return {"user_id": None, "username": None}

        authorizer = request_context.get("authorizer")
        if not isinstance(authorizer, dict):
            logger.debug(
                {
                    "message": "No valid authorizer found",
                    "authorizer_type": type(authorizer).__name__,
                    "operation": "extract_user_context",
                }
            )
            return {"user_id": None, "username": None}

        claims = authorizer.get("claims")

        # Handle claims as either dict or JSON string
        if isinstance(claims, str):
            try:
                claims = json.loads(claims)
                logger.debug(
                    {
                        "message": "Parsed claims from JSON string",
                        "operation": "extract_user_context",
                    }
                )
            except (json.JSONDecodeError, ValueError) as e:
                logger.warning(
                    {
                        "message": "Failed to parse claims JSON string",
                        "error": str(e),
                        "claims_preview": (
                            claims[:200]
                            if isinstance(claims, str)
                            else str(claims)[:200]
                        ),
                        "operation": "extract_user_context",
                    }
                )
                return {"user_id": None, "username": None}
        elif not isinstance(claims, dict):
            logger.debug(
                {
                    "message": "Claims is neither dict nor string",
                    "claims_type": type(claims).__name__,
                    "operation": "extract_user_context",
                }
            )
            return {"user_id": None, "username": None}

        user_id = claims.get("sub")
        username = claims.get("cognito:username")

        logger.debug(
            {
                "message": "User context extracted",
                "user_id": user_id,
                "username": username,
                "operation": "extract_user_context",
            }
        )

        return {"user_id": user_id, "username": username}

    except Exception as e:
        logger.warning(
            {
                "message": "Failed to extract user context",
                "error": str(e),
                "operation": "extract_user_context",
                "event_keys": (
                    list(event.keys()) if isinstance(event, dict) else "event_not_dict"
                ),
            }
        )
        return {"user_id": None, "username": None}


@tracer.capture_method
def require_authentication(func: Callable) -> Callable:
    """
    Decorator that ensures a user is authenticated before executing the function.

    This decorator extracts user context from the Lambda event and passes it
    to the decorated function. If no valid user is found, it returns an
    authentication error response.

    Args:
        func: The function to decorate

    Returns:
        Decorated function that includes user authentication

    Example:
        >>> @require_authentication
        >>> def my_lambda_handler(event, context, user_context):
        >>>     user_id = user_context.get("user_id")
        >>>     # ... function logic
    """

    @wraps(func)
    def wrapper(event: Dict[str, Any], context: Any, *args, **kwargs):
        user_context = extract_user_context(event)
        user_id = user_context.get("user_id")

        if not user_id:
            logger.warning(
                {
                    "message": "Authentication required but no valid user found",
                    "operation": "require_authentication",
                    "function": func.__name__,
                }
            )
            return {
                "statusCode": 401,
                "body": json.dumps(
                    {
                        "success": False,
                        "error": {
                            "code": "AUTHENTICATION_REQUIRED",
                            "message": "Valid authentication is required to access this resource",
                        },
                        "meta": {
                            "timestamp": "2024-01-01T00:00:00Z",  # Will be overridden by actual timestamp
                            "version": "v1",
                        },
                    }
                ),
            }

        # Pass user_context to the decorated function
        return func(event, context, user_context, *args, **kwargs)

    return wrapper


@tracer.capture_method
def get_user_permissions(
    user_id: str, resource_type: str, resource_id: str
) -> Dict[str, Any]:
    """
    Get user permissions for a specific resource.

    This function is a placeholder for future role-based access control (RBAC)
    implementation. Currently returns basic permissions based on ownership.

    Args:
        user_id: The user ID to check permissions for
        resource_type: Type of resource (e.g., 'collection', 'asset')
        resource_id: ID of the specific resource

    Returns:
        Dictionary containing permission information

    Note:
        This is a placeholder implementation. Future versions will integrate
        with a proper permissions system.
    """
    logger.debug(
        {
            "message": "Getting user permissions (placeholder implementation)",
            "user_id": user_id,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "operation": "get_user_permissions",
        }
    )

    # Placeholder implementation - always return basic permissions
    # TODO: Implement proper RBAC system
    return {
        "can_read": True,
        "can_write": False,  # Will be determined by ownership or explicit grants
        "can_delete": False,
        "can_share": False,
        "role": "viewer",  # Default role
    }


@tracer.capture_method
def is_resource_owner(user_id: str, resource_owner_id: str) -> bool:
    """
    Check if a user is the owner of a resource.

    Args:
        user_id: The user ID to check
        resource_owner_id: The owner ID of the resource

    Returns:
        True if the user is the owner, False otherwise
    """
    is_owner = user_id == resource_owner_id

    logger.debug(
        {
            "message": "Checked resource ownership",
            "user_id": user_id,
            "resource_owner_id": resource_owner_id,
            "is_owner": is_owner,
            "operation": "is_resource_owner",
        }
    )

    return is_owner
