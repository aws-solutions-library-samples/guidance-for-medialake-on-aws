"""DELETE /collections/groups/{groupId} - Delete a collection group."""

import os

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.event_handler.exceptions import (
    BadRequestError,
    ForbiddenError,
    NotFoundError,
)
from aws_lambda_powertools.metrics import MetricUnit
from collection_groups_utils import (
    delete_collection_group,
    get_collection_group_metadata,
)
from collections_utils import create_error_response
from user_auth import extract_user_context

dynamodb = boto3.resource("dynamodb")
table_name = os.environ.get("COLLECTIONS_TABLE_NAME", "collections_table_dev")
groups_table = dynamodb.Table(table_name)

logger = Logger(service="groups-id-delete", level=os.environ.get("LOG_LEVEL", "INFO"))
tracer = Tracer(service="groups-id-delete")
metrics = Metrics(namespace="medialake", service="collection-groups")


def register_route(app):
    """Register DELETE /collections/groups/{groupId} route"""

    @app.delete("/collections/groups/<groupId>")
    @tracer.capture_method
    def groups_id_delete(groupId: str):
        """Delete a collection group"""
        try:
            user_context = extract_user_context(app.current_event.raw_event)
            user_id = user_context.get("user_id")

            if not user_id:
                raise BadRequestError("Authentication required")

            # Check if group exists
            group = get_collection_group_metadata(groups_table, groupId)
            if not group:
                raise NotFoundError(f"Collection group {groupId} not found")

            # Check authorization (owner only)
            if group.get("ownerId") != user_id:
                raise ForbiddenError("Only the group owner can delete this group")

            # Delete group
            delete_collection_group(groups_table, groupId)

            metrics.add_metric(
                name="SuccessfulGroupDeletions", unit=MetricUnit.Count, value=1
            )

            return {
                "statusCode": 204,
                "body": "",
            }

        except (BadRequestError, ForbiddenError, NotFoundError):
            raise
        except Exception as e:
            logger.exception("Unexpected error deleting group", exc_info=e)
            metrics.add_metric(name="UnexpectedErrors", unit=MetricUnit.Count, value=1)
            return create_error_response(
                error_code="InternalServerError",
                error_message="An unexpected error occurred",
                status_code=500,
                request_id=app.current_event.request_context.request_id,
            )
