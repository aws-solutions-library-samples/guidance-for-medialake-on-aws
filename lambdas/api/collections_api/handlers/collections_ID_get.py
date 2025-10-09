"""GET /collections/<collection_id> - Get collection details."""

import os
import sys

from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.event_handler.exceptions import NotFoundError
from aws_lambda_powertools.metrics import MetricUnit

sys.path.insert(0, "/opt/python")
from collections_utils import (
    COLLECTION_PK_PREFIX,
    METADATA_SK,
    create_error_response,
    create_success_response,
    format_collection_item,
)
from user_auth import extract_user_context

logger = Logger(service="collections-ID-get", level=os.environ.get("LOG_LEVEL", "INFO"))
tracer = Tracer(service="collections-ID-get")
metrics = Metrics(namespace="medialake", service="collection-detail")


def register_route(app, dynamodb, table_name):
    """Register GET /collections/<collection_id> route"""

    @app.get("/collections/<collection_id>")
    @tracer.capture_method
    def collections_ID_get(collection_id: str):
        """Get collection details with optional includes"""
        try:
            user_context = extract_user_context(app.current_event.raw_event)
            table = dynamodb.Table(table_name)

            response = table.get_item(
                Key={"PK": f"{COLLECTION_PK_PREFIX}{collection_id}", "SK": METADATA_SK}
            )

            if "Item" not in response:
                raise NotFoundError(f"Collection '{collection_id}' not found")

            collection_item = response["Item"]
            formatted_collection = format_collection_item(collection_item, user_context)

            metrics.add_metric(
                name="SuccessfulCollectionRetrievals", unit=MetricUnit.Count, value=1
            )

            return create_success_response(
                data=formatted_collection,
                request_id=app.current_event.request_context.request_id,
            )

        except NotFoundError:
            raise
        except Exception as e:
            logger.exception("Error retrieving collection", exc_info=e)
            return create_error_response(
                error_code="InternalServerError",
                error_message="An unexpected error occurred",
                status_code=500,
                request_id=app.current_event.request_context.request_id,
            )
