"""
Collection Detail Routes.

Handles operations on individual collections:
- GET /collections/{collectionId} - Get collection details
- PATCH /collections/{collectionId} - Update collection
- DELETE /collections/{collectionId} - Delete collection
"""

import json
import os
import sys
from datetime import datetime

from aws_lambda_powertools import Logger, Metrics, Tracer
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

logger = Logger(
    service="collection-detail-routes", level=os.environ.get("LOG_LEVEL", "INFO")
)
tracer = Tracer(service="collection-detail-routes")
metrics = Metrics(namespace="medialake", service="collection-detail")


def register_routes(app, dynamodb, table_name):
    """Register collection detail routes"""

    @app.get("/collections/<collection_id>")
    @tracer.capture_method
    def get_collection(collection_id: str):
        """Get collection details with optional includes"""
        try:
            user_context = extract_user_context(app.current_event.raw_event)
            table = dynamodb.Table(table_name)

            response = table.get_item(
                Key={"PK": f"{COLLECTION_PK_PREFIX}{collection_id}", "SK": METADATA_SK}
            )

            if "Item" not in response:
                return create_error_response(
                    error_code="COLLECTION_NOT_FOUND",
                    error_message=f"Collection '{collection_id}' not found",
                    status_code=404,
                    request_id=app.current_event.request_context.request_id,
                )

            collection_item = response["Item"]
            formatted_collection = format_collection_item(collection_item, user_context)

            metrics.add_metric(
                name="SuccessfulCollectionRetrievals", unit=MetricUnit.Count, value=1
            )

            return create_success_response(
                data=formatted_collection,
                request_id=app.current_event.request_context.request_id,
            )

        except Exception as e:
            logger.exception("Error retrieving collection", exc_info=e)
            return create_error_response(
                error_code="InternalServerError",
                error_message="An unexpected error occurred",
                status_code=500,
                request_id=app.current_event.request_context.request_id,
            )

    @app.patch("/collections/<collection_id>")
    @tracer.capture_method
    def update_collection(collection_id: str):
        """Update collection"""
        try:
            user_context = extract_user_context(app.current_event.raw_event)
            user_context.get("user_id")
            request_data = app.current_event.json_body

            table = dynamodb.Table(table_name)
            current_timestamp = datetime.utcnow().isoformat() + "Z"

            # Build update expression
            update_expr_parts = ["updatedAt = :timestamp"]
            expr_attr_values = {":timestamp": current_timestamp}

            if "name" in request_data:
                update_expr_parts.append("#name = :name")
                expr_attr_values[":name"] = request_data["name"]

            if "description" in request_data:
                update_expr_parts.append("description = :description")
                expr_attr_values[":description"] = request_data["description"]

            if "status" in request_data:
                update_expr_parts.append("#status = :status")
                expr_attr_values[":status"] = request_data["status"]

            table.update_item(
                Key={"PK": f"{COLLECTION_PK_PREFIX}{collection_id}", "SK": METADATA_SK},
                UpdateExpression=f"SET {', '.join(update_expr_parts)}",
                ExpressionAttributeValues=expr_attr_values,
                ExpressionAttributeNames=(
                    {"#name": "name", "#status": "status"}
                    if "name" in request_data or "status" in request_data
                    else None
                ),
            )

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

        except Exception as e:
            logger.exception("Error updating collection", exc_info=e)
            return create_error_response(
                error_code="InternalServerError",
                error_message="An unexpected error occurred",
                status_code=500,
                request_id=app.current_event.request_context.request_id,
            )

    @app.delete("/collections/<collection_id>")
    @tracer.capture_method
    def delete_collection(collection_id: str):
        """Delete collection (soft delete)"""
        try:
            extract_user_context(app.current_event.raw_event)
            table = dynamodb.Table(table_name)
            current_timestamp = datetime.utcnow().isoformat() + "Z"

            # Soft delete by updating status
            table.update_item(
                Key={"PK": f"{COLLECTION_PK_PREFIX}{collection_id}", "SK": METADATA_SK},
                UpdateExpression="SET #status = :deleted, updatedAt = :timestamp",
                ExpressionAttributeValues={
                    ":deleted": "DELETED",
                    ":timestamp": current_timestamp,
                },
                ExpressionAttributeNames={"#status": "status"},
            )

            logger.info(f"Collection deleted: {collection_id}")
            metrics.add_metric(
                name="SuccessfulCollectionDeletions", unit=MetricUnit.Count, value=1
            )

            return {
                "statusCode": 200,
                "body": json.dumps(
                    {
                        "success": True,
                        "data": {"id": collection_id, "status": "DELETED"},
                        "meta": {
                            "timestamp": current_timestamp,
                            "version": "v1",
                            "request_id": app.current_event.request_context.request_id,
                        },
                    }
                ),
            }

        except Exception as e:
            logger.exception("Error deleting collection", exc_info=e)
            return create_error_response(
                error_code="InternalServerError",
                error_message="An unexpected error occurred",
                status_code=500,
                request_id=app.current_event.request_context.request_id,
            )
