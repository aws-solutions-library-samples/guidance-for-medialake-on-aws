"""Handler for GET /settings/users endpoint - List all users from Cognito."""

import concurrent.futures
import os
from typing import Any, Dict, List, Optional, Tuple

import boto3
from aws_lambda_powertools import Logger, Tracer
from botocore.config import Config as BotoConfig

logger = Logger(child=True)
tracer = Tracer()

# Cognito caps list_users / list_users_in_group / list_groups at 60 per call.
COGNITO_MAX_PAGE_SIZE = 60

# Upper bound on one response, so an unexpectedly large pool cannot exhaust the
# Lambda or push the payload past API Gateway's limit.
MAX_USERS = max(1, int(os.environ.get("USERS_MAX_ITEMS", "2000")))

# How many groups to resolve memberships for concurrently.
GROUP_FETCH_CONCURRENCY = max(1, int(os.environ.get("USERS_GROUP_CONCURRENCY", "8")))

# Low-level boto3 clients are thread safe, but the connection pool has to be at
# least as large as the worker count or the threads just queue on sockets.
cognito = boto3.client(
    "cognito-idp",
    config=BotoConfig(
        max_pool_connections=max(10, GROUP_FETCH_CONCURRENCY + 4),
        retries={"max_attempts": 5, "mode": "adaptive"},
    ),
)


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
        "groups": [],  # Populated from the group membership map
        "permissions": [],  # Frontend expects this field
    }


@tracer.capture_method
def _drain_users(
    user_pool_id: str, max_users: int, start_token: Optional[str] = None
) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """
    Page through list_users until the pool is exhausted or max_users is reached.

    Cognito pagination is a token chain -- each request needs the previous
    response -- so this part cannot be parallelized. It is the group lookups
    that fan out.

    Returns:
        (users, next_token). next_token is set only when the drain stopped early
        because of the cap, so callers can tell truncation from completion.
    """
    users: List[Dict[str, Any]] = []
    next_token = start_token

    while True:
        params: Dict[str, Any] = {
            "UserPoolId": user_pool_id,
            # Never request past the cap: sizing the final page keeps the
            # returned list and next_token consistent without dropping users.
            "Limit": max(1, min(COGNITO_MAX_PAGE_SIZE, max_users - len(users))),
        }
        if next_token:
            params["PaginationToken"] = next_token

        response = cognito.list_users(**params)
        users.extend(
            _transform_cognito_user(user) for user in response.get("Users", [])
        )

        next_token = response.get("PaginationToken")
        if not next_token:
            # Pool exhausted: there is no further page to report.
            return users, None
        if len(users) >= max_users:
            logger.warning(
                "User list truncated by cap",
                extra={"returned": len(users), "max_users": max_users},
            )
            return users, next_token


def _list_group_names(user_pool_id: str) -> List[str]:
    """Return every group name in the pool, in Cognito's own order."""
    group_names: List[str] = []
    next_token = None

    while True:
        params: Dict[str, Any] = {
            "UserPoolId": user_pool_id,
            "Limit": COGNITO_MAX_PAGE_SIZE,
        }
        if next_token:
            params["NextToken"] = next_token

        response = cognito.list_groups(**params)
        group_names.extend(
            group["GroupName"]
            for group in response.get("Groups", [])
            if group.get("GroupName")
        )

        next_token = response.get("NextToken")
        if not next_token:
            return group_names


def _usernames_in_group(user_pool_id: str, group_name: str) -> List[str]:
    """Return the usernames belonging to a single group."""
    usernames: List[str] = []
    next_token = None

    while True:
        params: Dict[str, Any] = {
            "UserPoolId": user_pool_id,
            "GroupName": group_name,
            "Limit": COGNITO_MAX_PAGE_SIZE,
        }
        if next_token:
            params["NextToken"] = next_token

        response = cognito.list_users_in_group(**params)
        usernames.extend(
            user["Username"]
            for user in response.get("Users", [])
            if user.get("Username")
        )

        next_token = response.get("NextToken")
        if not next_token:
            return usernames


@tracer.capture_method
def _build_group_map(user_pool_id: str) -> Dict[str, List[str]]:
    """
    Build a username -> [group names] map by enumerating groups, not users.

    This replaces a per-user admin_list_groups_for_user call. That approach cost
    one sequential Cognito request per user, so listing 1,000 users was enough
    to exceed API Gateway's integration timeout on its own. Walking the handful
    of groups instead costs roughly (users / 60) requests in total, and those
    run concurrently.
    """
    group_names = _list_group_names(user_pool_id)
    if not group_names:
        return {}

    group_map: Dict[str, List[str]] = {}
    workers = min(GROUP_FETCH_CONCURRENCY, len(group_names))

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [
            (name, pool.submit(_usernames_in_group, user_pool_id, name))
            for name in group_names
        ]

        # Collected in submission order rather than completion order so each
        # user's group list is stable across requests. The UI treats
        # groups[0] as the user's current group, so ordering is load-bearing.
        for group_name, future in futures:
            try:
                for username in future.result():
                    group_map.setdefault(username, []).append(group_name)
            except Exception as e:
                # One unreadable group means missing chips for those users, not
                # a failed request.
                logger.warning(
                    "Failed to list users in group",
                    extra={"group": group_name, "error": str(e)},
                )

    return group_map


@tracer.capture_method
def _list_cognito_users(
    user_pool_id: str,
    max_users: int = MAX_USERS,
    pagination_token: Optional[str] = None,
) -> Dict[str, Any]:
    """
    List users from the Cognito User Pool along with their group memberships.

    Draining users and mapping group membership only depend on the pool id, so
    the two run concurrently and the request costs about as long as the slower
    of the two rather than their sum.

    Args:
        user_pool_id: Cognito User Pool ID
        max_users: Maximum number of users to return
        pagination_token: Optional token to resume a truncated drain

    Returns:
        Dict containing the users list, count, and a paginationToken when the
        result was truncated by max_users.
    """
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            users_future = pool.submit(
                _drain_users, user_pool_id, max_users, pagination_token
            )
            groups_future = pool.submit(_build_group_map, user_pool_id)

            users, next_token = users_future.result()
            group_map = groups_future.result()

        for user in users:
            user["groups"] = group_map.get(user["username"], [])

        result: Dict[str, Any] = {"users": users, "count": len(users)}

        # Only present when the drain stopped at the cap.
        if next_token:
            result["paginationToken"] = next_token

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

            query_params = app.current_event.query_string_parameters or {}

            # `limit` is an optional cap on the total number of users returned.
            # Unset means "everything", which is what the UI needs in order to
            # sort, filter and paginate across the full set. A bad value falls
            # back to the cap instead of raising, which is what the unguarded
            # int() here used to do.
            requested_limit = query_params.get("limit")
            try:
                max_users = (
                    int(requested_limit) if requested_limit is not None else MAX_USERS
                )
            except (ValueError, TypeError):
                logger.warning(
                    "Ignoring invalid limit parameter",
                    extra={"limit": requested_limit},
                )
                max_users = MAX_USERS
            max_users = max(1, min(max_users, MAX_USERS))

            pagination_token = query_params.get("paginationToken")

            logger.info(
                "Listing users from Cognito",
                extra={
                    "user_pool_id": user_pool_id,
                    "max_users": max_users,
                    "has_pagination_token": bool(pagination_token),
                },
            )

            result = _list_cognito_users(user_pool_id, max_users, pagination_token)

            logger.info(
                "Successfully retrieved users",
                extra={
                    "count": result["count"],
                    "truncated": "paginationToken" in result,
                },
            )

            return {
                "status": "success",
                "message": f"Retrieved {result['count']} users",
                "data": result,
            }

        except Exception as e:
            logger.exception("Error retrieving users from Cognito")
            return {
                "status": "error",
                "message": f"Error retrieving users: {str(e)}",
                "data": {},
            }
