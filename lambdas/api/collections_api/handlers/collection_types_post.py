"""POST /collection-types - Create collection type."""

import json
import os
import uuid
from datetime import datetime

from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.metrics import MetricUnit
from db_models import CollectionTypeModel
from utils.formatting_utils import format_collection_type

logger = Logger(
    service="collection-types-post", level=os.environ.get("LOG_LEVEL", "INFO")
)
tracer = Tracer(service="collection-types-post")
metrics = Metrics(namespace="medialake", service="collection-types")

SYSTEM_PK = "SYSTEM"
COLLECTION_TYPE_SK_PREFIX = "COLLTYPE#"
ALLOWED_ITEM_TYPES = ["asset", "workflow", "collection"]


def register_route(app):
    """Register POST /collection-types route"""

    @app.post("/collection-types")
    @tracer.capture_method
    def collection_types_post():
        """Create a new collection type"""
        try:
            request_data = app.current_event.json_body

            # Validate required fields
            if not request_data.get("name"):
                return {
                    "statusCode": 400,
                    "body": json.dumps(
                        {
                            "success": False,
                            "error": {
                                "code": "VALIDATION_ERROR",
                                "message": "Collection type name is required",
                            },
                        }
                    ),
                }

            current_timestamp = datetime.utcnow().isoformat() + "Z"
            type_id = f"colltype_{str(uuid.uuid4())[:8]}"

            # Create collection type model instance
            collection_type = CollectionTypeModel()
            collection_type.PK = SYSTEM_PK
            collection_type.SK = f"{COLLECTION_TYPE_SK_PREFIX}{type_id}"
            collection_type.name = request_data["name"]
            collection_type.isActive = request_data.get("isActive", True)
            collection_type.allowedItemTypes = request_data.get(
                "allowedItemTypes", ALLOWED_ITEM_TYPES
            )
            collection_type.createdAt = current_timestamp
            collection_type.updatedAt = current_timestamp

            if request_data.get("description"):
                collection_type.description = request_data["description"]

            if request_data.get("schema"):
                collection_type.schema = request_data["schema"]

            # Save to DynamoDB
            collection_type.save()

            logger.info(f"Collection type created: {type_id}")
            metrics.add_metric(
                name="SuccessfulCollectionTypeCreations", unit=MetricUnit.Count, value=1
            )

            # Convert to dict for formatting
            collection_type_dict = {
                "PK": collection_type.PK,
                "SK": collection_type.SK,
                "name": collection_type.name,
                "description": (
                    collection_type.description if collection_type.description else None
                ),
                "isActive": collection_type.isActive,
                "allowedItemTypes": (
                    list(collection_type.allowedItemTypes)
                    if collection_type.allowedItemTypes
                    else []
                ),
                "schema": (
                    dict(collection_type.schema) if collection_type.schema else None
                ),
                "createdAt": collection_type.createdAt,
                "updatedAt": collection_type.updatedAt,
            }

            return {
                "statusCode": 201,
                "body": json.dumps(
                    {
                        "success": True,
                        "data": format_collection_type(collection_type_dict),
                        "meta": {
                            "timestamp": current_timestamp,
                            "version": "v1",
                            "request_id": app.current_event.request_context.request_id,
                        },
                    }
                ),
            }

        except Exception as e:
            logger.exception("Error creating collection type", exc_info=e)
            return {
                "statusCode": 500,
                "body": json.dumps(
                    {
                        "success": False,
                        "error": {
                            "code": "InternalServerError",
                            "message": "An unexpected error occurred",
                        },
                        "meta": {
                            "request_id": app.current_event.request_context.request_id
                        },
                    }
                ),
            }
