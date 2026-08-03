"""GET /collections/users - List user summaries under collections:edit permission.

This endpoint returns lightweight user summaries so that the ShareManagementModal
can populate its user autocomplete without requiring the separate users:view
permission (which is a settings-level permission). Only the minimal identity
fields needed for the sharing UI are returned (username, email, display name) —
account state such as enabled/status is deliberately excluded.
"""

import os

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.metrics import MetricUnit
from collections_utils import create_error_response
from user_auth import extract_user_context

logger = Logger(
    service="collections-users-get",
    level=os.environ.get("LOG_LEVEL", "INFO"),
)
tracer = Tracer(service="collections-users-get")
metrics = Metrics(namespace="medialake", service="collections-users")

cognito = boto3.client("cognito-idp")


def register_route(app):
    """Register GET /collections/users route"""

    @app.get("/collections/users")
    @tracer.capture_method
    def collections_users_get():
        """Return user summaries under collections:edit permission."""
        request_id = app.current_event.request_context.request_id

        try:
            # Defense in depth: the custom authorizer already gates this route
            # behind collections:edit, but never dump the user directory to a
            # request without an authenticated identity.
            user_context = extract_user_context(app.current_event.raw_event)
            if not user_context.get("user_id"):
                return create_error_response(
                    error_code="Unauthorized",
                    error_message="Authentication required",
                    status_code=401,
                    request_id=request_id,
                )

            user_pool_id = os.environ.get("COGNITO_USER_POOL_ID")
            if not user_pool_id:
                logger.error("COGNITO_USER_POOL_ID not configured")
                return {
                    "success": True,
                    "data": {"users": [], "count": 0},
                    "meta": {"request_id": request_id},
                }

            users = []
            params = {"UserPoolId": user_pool_id, "Limit": 60}

            while True:
                response = cognito.list_users(**params)

                for user in response.get("Users", []):
                    attrs = {a["Name"]: a["Value"] for a in user.get("Attributes", [])}
                    given_name = attrs.get("given_name")
                    family_name = attrs.get("family_name")

                    # Minimal fields only: the sharing UI needs identity and
                    # display name. Account state (enabled/status) is
                    # admin-level information and is deliberately omitted.
                    users.append(
                        {
                            "username": user.get("Username"),
                            "email": attrs.get("email"),
                            "given_name": given_name,
                            "family_name": family_name,
                            "name": (
                                f"{given_name} {family_name}"
                                if given_name and family_name
                                else given_name or family_name or None
                            ),
                        }
                    )

                if "PaginationToken" in response:
                    params["PaginationToken"] = response["PaginationToken"]
                else:
                    break

            logger.info(f"Returned {len(users)} user summaries for collections")
            metrics.add_metric(
                name="CollectionUserSummaryRequests",
                unit=MetricUnit.Count,
                value=1,
            )

            return {
                "success": True,
                "data": {"users": users, "count": len(users)},
                "meta": {"request_id": request_id},
            }

        except Exception as e:
            logger.exception("Error fetching user summaries", exc_info=e)
            return create_error_response(
                error_code="InternalServerError",
                error_message="An unexpected error occurred",
                status_code=500,
                request_id=request_id,
            )
