"""PATCH /collections/<collection_id> - Update collection."""

import json
import os
from datetime import datetime

from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.event_handler.exceptions import BadRequestError
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.parser import ValidationError, parse
from collections_utils import COLLECTION_PK_PREFIX, METADATA_SK, create_error_response
from models import UpdateCollectionRequest
from user_auth import extract_user_context

logger = Logger(
    service="collections-ID-patch", level=os.environ.get("LOG_LEVEL", "INFO")
)
tracer = Tracer(service="collections-ID-patch")
metrics = Metrics(namespace="medialake", service="collection-detail")


def register_route(app, dynamodb, table_name):
    """Register PATCH /collections/<collection_id> route"""

    @app.patch("/collections/<collection_id>")
    @tracer.capture_method
    def collections_ID_patch(collection_id: str):
        """Update collection with Pydantic validation"""
        try:
            user_context = extract_user_context(app.current_event.raw_event)
            user_context.get("user_id")

            # Parse and validate with Pydantic
            try:
                request_data = parse(
                    event=app.current_event.json_body,
                    model=UpdateCollectionRequest,
                )
            except ValidationError as e:
                logger.warning(f"Validation error updating collection: {e}")
                raise BadRequestError(f"Validation error: {str(e)}")

            table = dynamodb.Table(table_name)
            current_timestamp = datetime.utcnow().isoformat() + "Z"

            # Build update expression from validated model
            update_expr_parts = ["updatedAt = :timestamp"]
            expr_attr_values = {":timestamp": current_timestamp}
            expr_attr_names = {}

            if request_data.name is not None:
                update_expr_parts.append("#name = :name")
                expr_attr_values[":name"] = request_data.name
                expr_attr_names["#name"] = "name"

            if request_data.description is not None:
                update_expr_parts.append("description = :description")
                expr_attr_values[":description"] = request_data.description

            if request_data.status is not None:
                update_expr_parts.append("#status = :status")
                expr_attr_values[":status"] = request_data.status.value
                expr_attr_names["#status"] = "status"

            if request_data.isPublic is not None:
                update_expr_parts.append("isPublic = :isPublic")
                expr_attr_values[":isPublic"] = request_data.isPublic

            if request_data.metadata is not None:
                update_expr_parts.append("customMetadata = :metadata")
                expr_attr_values[":metadata"] = request_data.metadata

            if request_data.tags is not None:
                update_expr_parts.append("tags = :tags")
                expr_attr_values[":tags"] = request_data.tags

            # Build update_item parameters
            update_params = {
                "Key": {
                    "PK": f"{COLLECTION_PK_PREFIX}{collection_id}",
                    "SK": METADATA_SK,
                },
                "UpdateExpression": f"SET {', '.join(update_expr_parts)}",
                "ExpressionAttributeValues": expr_attr_values,
            }

            # Only add ExpressionAttributeNames if there are any
            if expr_attr_names:
                update_params["ExpressionAttributeNames"] = expr_attr_names

            table.update_item(**update_params)

            logger.info(f"Collection updated: {collection_id}")
            metrics.add_metric(
                name="SuccessfulCollectionUpdates", unit=MetricUnit.Count, value=1
            )

            return {
                "statusCode": 200,
                "body": json.dumps(
                    {
                        "success": True,
                        "data": {"id": collection_id, "updatedAt": current_timestamp},
                        "meta": {
                            "timestamp": current_timestamp,
                            "version": "v1",
                            "request_id": app.current_event.request_context.request_id,
                        },
                    }
                ),
            }

        except BadRequestError:
            raise
        except Exception as e:
            logger.exception("Error updating collection", exc_info=e)
            return create_error_response(
                error_code="InternalServerError",
                error_message="An unexpected error occurred",
                status_code=500,
                request_id=app.current_event.request_context.request_id,
            )
