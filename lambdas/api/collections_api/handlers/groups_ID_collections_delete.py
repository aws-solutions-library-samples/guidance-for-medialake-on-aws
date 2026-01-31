"""DELETE /collections/groups/{groupId}/collections - Remove collections from a group."""

import json
import os

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.event_handler.exceptions import (
    BadRequestError,
    ForbiddenError,
    NotFoundError,
)
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.parser import ValidationError, parse
from collection_groups_utils import (
    format_collection_group_item,
    get_collection_group_metadata,
    remove_collection_ids,
)
from collections_utils import create_error_response
from models.group_models import RemoveCollectionsRequest
from user_auth import extract_user_context

dynamodb = boto3.resource("dynamodb")
table_name = os.environ.get("COLLECTIONS_TABLE_NAME", "collections_table_dev")
groups_table = dynamodb.Table(table_name)

logger = Logger(
    service="groups-id-collections-delete", level=os.environ.get("LOG_LEVEL", "INFO")
)
tracer = Tracer(service="groups-id-collections-delete")
metrics = Metrics(namespace="medialake", service="collection-groups")


def register_route(app):
    """Register DELETE /collections/groups/{groupId}/collections route"""

    @app.delete("/collections/groups/<groupId>/collections")
    @tracer.capture_method
    def groups_id_collections_delete(groupId: str):
        """Remove collections from a group"""
        try:
            user_context = extract_user_context(app.current_event.raw_event)
            user_id = user_context.get("user_id")

            if not user_id:
                raise BadRequestError("Authentication required")

            # Check if group exists
            group = get_collection_group_metadata(groups_table, groupId)
            if not group:
                raise NotFoundError(f"Collection group {groupId} not found")

            # Check authorization (owner only for now, pipeline support in Task 17)
            if group.get("ownerId") != user_id:
                raise ForbiddenError(
                    "Only the group owner can remove collections from this group"
                )

            # Parse and validate request
            try:
                request_data = parse(
                    event=app.current_event.json_body,
                    model=RemoveCollectionsRequest,
                )
            except ValidationError as e:
                logger.warning(f"Request validation error: {e}")
                raise BadRequestError(f"Validation error: {str(e)}")

            # Remove collections from group
            remove_collection_ids(groups_table, groupId, request_data.collectionIds)

            # Get updated group
            updated_group = get_collection_group_metadata(groups_table, groupId)
            formatted_group = format_collection_group_item(updated_group, user_context)

            metrics.add_metric(
                name="CollectionsRemovedFromGroup",
                unit=MetricUnit.Count,
                value=len(request_data.collectionIds),
            )

            return {
                "statusCode": 200,
                "body": json.dumps(
                    {
                        "success": True,
                        "data": formatted_group,
                        "meta": {
                            "request_id": app.current_event.request_context.request_id
                        },
                    }
                ),
            }

        except (BadRequestError, ForbiddenError, NotFoundError):
            raise
        except Exception as e:
            logger.exception(
                "Unexpected error removing collections from group", exc_info=e
            )
            metrics.add_metric(name="UnexpectedErrors", unit=MetricUnit.Count, value=1)
            return create_error_response(
                error_code="InternalServerError",
                error_message="An unexpected error occurred",
                status_code=500,
                request_id=app.current_event.request_context.request_id,
            )
