"""Handler for GET /settings/users endpoint - List all users from Cognito."""

import os
from typing import Any, Dict

import boto3
from aws_lambda_powertools import Logger, Tracer

logger = Logger(child=True)
tracer = Tracer()

# Initialize Cognito client
cognito = boto3.client("cognito-idp")


def _transform_cognito_user(user: Dict[str, Any]) -> Dict[str, Any]:
    """
    Transform Cognito user response to match frontend User type.

    Args:
        user: Raw Cognito user object

    Returns:
        User object matching frontend TypeScript interface
    """
    # Transform user attributes from list to dict
    user_attributes = {
        attr["Name"]: attr["Value"] for attr in user.get("Attributes", [])
    }

    # Get name components
    given_name = user_attributes.get("given_name")
    family_name = user_attributes.get("family_name")

    return {
        "username": user.get("Username"),
        "email": user_attributes.get("email"),
        "enabled": user.get("Enabled", True),
        "status": user.get("UserStatus"),  # Frontend expects "status" not "userStatus"
        "created": (
            user.get("UserCreateDate").isoformat()
            if user.get("UserCreateDate")
            else None
        ),
        "modified": (
            user.get("UserLastModifiedDate").isoformat()
            if user.get("UserLastModifiedDate")
            else None
        ),
        "email_verified": user_attributes.get(
            "email_verified", "false"
        ),  # String, not boolean
        "given_name": given_name,
        "family_name": family_name,
        "name": (
            f"{given_name} {family_name}"
            if given_name and family_name
            else given_name or family_name or None
        ),
        "groups": [],  # Will be populated later
        "permissions": [],  # Frontend expects this field
    }


def _list_cognito_users(
    user_pool_id: str, limit: int = 60, pagination_token: str = None
) -> Dict[str, Any]:
    """
    List all users from Cognito User Pool with pagination support.

    Args:
        user_pool_id: Cognito User Pool ID
        limit: Maximum number of users to return (max 60 for Cognito)
        pagination_token: Token for pagination

    Returns:
        Dict containing users list and pagination token
    """
    try:
        params = {
            "UserPoolId": user_pool_id,
            "Limit": min(limit, 60),  # Cognito max is 60
        }

        if pagination_token:
            params["PaginationToken"] = pagination_token

        response = cognito.list_users(**params)

        # Transform users
        users = [_transform_cognito_user(user) for user in response.get("Users", [])]

        # Get groups for each user (frontend expects array of group names as strings)
        for user in users:
            try:
                groups_response = cognito.admin_list_groups_for_user(
                    UserPoolId=user_pool_id, Username=user["username"]
                )
                # Frontend expects just group names as strings, not objects
                user["groups"] = [
                    group["GroupName"] for group in groups_response.get("Groups", [])
                ]
            except Exception as e:
                logger.warning(
                    f"Failed to get groups for user {user['username']}",
                    extra={"error": str(e)},
                )
                user["groups"] = []

        result = {
            "users": users,
            "count": len(users),
        }

        # Include pagination token if there are more results
        if "PaginationToken" in response:
            result["paginationToken"] = response["PaginationToken"]

        return result

    except Exception:
        logger.exception("Error listing users from Cognito")
        raise


def register_route(app):
    """Register GET /settings/users route"""

    @app.get("/settings/users")
    @tracer.capture_method
    def settings_users_get():
        """Get all users from Cognito User Pool"""
        try:
            user_pool_id = os.environ.get("COGNITO_USER_POOL_ID")

            if not user_pool_id:
                logger.error("COGNITO_USER_POOL_ID environment variable not set")
                return {
                    "status": "error",
                    "message": "Server configuration error: User pool ID not configured",
                    "data": {},
                }

            # Get query parameters for pagination
            query_params = app.current_event.query_string_parameters or {}
            limit = int(query_params.get("limit", 60))
            pagination_token = query_params.get("paginationToken")

            logger.info(
                "Listing users from Cognito",
                extra={
                    "user_pool_id": user_pool_id,
                    "limit": limit,
                    "has_pagination_token": bool(pagination_token),
                },
            )

            # Get users from Cognito
            result = _list_cognito_users(user_pool_id, limit, pagination_token)

            logger.info(
                "Successfully retrieved users",
                extra={
                    "count": result["count"],
                    "has_more": "paginationToken" in result,
                },
            )

            # Prepare response
            response = {
                "status": "success",
                "message": f"Retrieved {result['count']} users",
                "data": result,
            }

            return response

        except Exception as e:
            logger.exception("Error retrieving users from Cognito")
            return {
                "status": "error",
                "message": f"Error retrieving users: {str(e)}",
                "data": {},
            }
