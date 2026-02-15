"""GET /collections/users - List user summaries under collections:edit permission.

This endpoint returns lightweight user summaries so that the ShareManagementModal
can populate its user autocomplete without requiring the separate users:view
permission (which is a settings-level permission). Only basic identity fields
are returned (username, email, display name).
"""

import os

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.metrics import MetricUnit

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
                            "enabled": user.get("Enabled", True),
                            "status": user.get("UserStatus"),
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
            return {
                "statusCode": 500,
                "body": {
                    "success": False,
                    "error": {
                        "code": "INTERNAL_SERVER_ERROR",
                        "message": "An unexpected error occurred",
                    },
                    "meta": {"request_id": request_id},
                },
            }
