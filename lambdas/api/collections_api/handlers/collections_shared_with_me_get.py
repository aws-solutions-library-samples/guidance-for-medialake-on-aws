"""GET /collections/shared-with-me - Get collections shared with current user."""

import os

from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.event_handler.exceptions import BadRequestError
from collections_utils import (
    USER_PK_PREFIX,
    create_error_response,
    create_success_response,
    format_collection_item,
)
from user_auth import extract_user_context

logger = Logger(
    service="collections-shared-with-me-get", level=os.environ.get("LOG_LEVEL", "INFO")
)
tracer = Tracer(service="collections-shared-with-me-get")
metrics = Metrics(namespace="medialake", service="collections")


def register_route(app, dynamodb, table_name):
    """Register GET /collections/shared-with-me route"""

    @app.get("/collections/shared-with-me")
    @tracer.capture_method
    def collections_shared_with_me_get():
        """Get collections shared with the current user"""
        try:
            user_context = extract_user_context(app.current_event.raw_event)
            user_id = user_context.get("user_id")

            if not user_id:
                raise BadRequestError("Authentication required")

            table = dynamodb.Table(table_name)

            # Query user's shared collections
            response = table.query(
                IndexName="UserCollectionsGSI",
                KeyConditionExpression="GSI1_PK = :user_pk",
                FilterExpression="relationship <> :owner",
                ExpressionAttributeValues={
                    ":user_pk": f"{USER_PK_PREFIX}{user_id}",
                    ":owner": "OWNER",
                },
            )

            items = response.get("Items", [])
            formatted_items = [
                format_collection_item(item, user_context) for item in items
            ]

            return create_success_response(
                data=formatted_items,
                request_id=app.current_event.request_context.request_id,
            )

        except BadRequestError:
            raise
        except Exception as e:
            logger.exception("Error listing shared collections", exc_info=e)
            return create_error_response(
                error_code="InternalServerError",
                error_message="An unexpected error occurred",
                status_code=500,
                request_id=app.current_event.request_context.request_id,
            )
