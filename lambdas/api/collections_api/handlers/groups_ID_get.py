"""GET /collections/groups/{groupId} - Get a specific collection group."""

import json
import os

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.event_handler.exceptions import NotFoundError
from aws_lambda_powertools.metrics import MetricUnit
from collection_groups_utils import (
    format_collection_group_item,
    get_collection_group_metadata,
)
from collections_utils import create_error_response
from user_auth import extract_user_context

dynamodb = boto3.resource("dynamodb")
table_name = os.environ.get("COLLECTIONS_TABLE_NAME", "collections_table_dev")
groups_table = dynamodb.Table(table_name)

logger = Logger(service="groups-id-get", level=os.environ.get("LOG_LEVEL", "INFO"))
tracer = Tracer(service="groups-id-get")
metrics = Metrics(namespace="medialake", service="collection-groups")


def register_route(app):
    """Register GET /collections/groups/{groupId} route"""

    @app.get("/collections/groups/<groupId>")
    @tracer.capture_method
    def groups_id_get(groupId: str):
        """Get a specific collection group by ID"""
        try:
            user_context = extract_user_context(app.current_event.raw_event)

            group = get_collection_group_metadata(groups_table, groupId)
            if not group:
                raise NotFoundError(f"Collection group {groupId} not found")

            formatted_group = format_collection_group_item(group, user_context)

            metrics.add_metric(
                name="SuccessfulGroupRetrieval", unit=MetricUnit.Count, value=1
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

        except NotFoundError:
            raise
        except Exception as e:
            logger.exception("Unexpected error getting group", exc_info=e)
            metrics.add_metric(name="UnexpectedErrors", unit=MetricUnit.Count, value=1)
            return create_error_response(
                error_code="InternalServerError",
                error_message="An unexpected error occurred",
                status_code=500,
                request_id=app.current_event.request_context.request_id,
            )
