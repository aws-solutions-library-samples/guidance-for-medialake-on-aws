"""POST /collections - Create a new collection."""

import json
import os
import uuid
from datetime import datetime

from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.event_handler.exceptions import BadRequestError
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.parser import ValidationError, parse
from collections_utils import (
    COLLECTION_PK_PREFIX,
    COLLECTIONS_GSI5_PK,
    METADATA_SK,
    USER_PK_PREFIX,
    format_collection_item,
)
from models import CreateCollectionRequest
from user_auth import extract_user_context

logger = Logger(service="collections-post", level=os.environ.get("LOG_LEVEL", "INFO"))
tracer = Tracer(service="collections-post")
metrics = Metrics(namespace="medialake", service="collections")


def register_route(app, dynamodb, table_name):
    """Register POST /collections route"""

    @app.post("/collections")
    @tracer.capture_method
    def collections_post():
        """Create a new collection with Pydantic V2 validation"""
        try:
            user_context = extract_user_context(app.current_event.raw_event)
            user_id = user_context.get("user_id")

            if not user_id:
                raise BadRequestError(
                    "Valid authentication is required to create collections"
                )

            # Parse and validate request body using Pydantic
            try:
                request_data = parse(
                    event=app.current_event.json_body,
                    model=CreateCollectionRequest,
                )
            except ValidationError as e:
                logger.warning(f"Request validation error: {e}")
                metrics.add_metric(
                    name="ValidationErrors", unit=MetricUnit.Count, value=1
                )
                raise BadRequestError(f"Validation error: {str(e)}")

            # Generate ID and timestamp
            collection_id = f"col_{str(uuid.uuid4())[:8]}"
            current_timestamp = datetime.utcnow().isoformat() + "Z"

            # Build collection item from validated Pydantic model
            collection_item = {
                "PK": f"{COLLECTION_PK_PREFIX}{collection_id}",
                "SK": METADATA_SK,
                "name": request_data.name,
                "ownerId": user_id,
                "status": "ACTIVE",
                "itemCount": 0,
                "childCollectionCount": 0,
                "isPublic": request_data.isPublic,
                "createdAt": current_timestamp,
                "updatedAt": current_timestamp,
                "GSI5_PK": COLLECTIONS_GSI5_PK,
                "GSI5_SK": current_timestamp,
            }

            # Add optional fields from Pydantic model
            if request_data.description:
                collection_item["description"] = request_data.description
            if request_data.collectionTypeId:
                collection_item["collectionTypeId"] = request_data.collectionTypeId
                collection_item["GSI3_PK"] = request_data.collectionTypeId
                collection_item["GSI3_SK"] = f"{COLLECTION_PK_PREFIX}{collection_id}"
            if request_data.parentId:
                collection_item["parentId"] = request_data.parentId
            if request_data.metadata:
                collection_item["customMetadata"] = request_data.metadata
            if request_data.tags:
                collection_item["tags"] = request_data.tags

            # User relationship item
            user_relationship_item = {
                "PK": f"{USER_PK_PREFIX}{user_id}",
                "SK": f"{COLLECTION_PK_PREFIX}{collection_id}",
                "relationship": "OWNER",
                "addedAt": current_timestamp,
                "lastAccessed": current_timestamp,
                "isFavorite": False,
                "GSI1_PK": f"{USER_PK_PREFIX}{user_id}",
                "GSI1_SK": current_timestamp,
            }

            # Prepare transactional write
            transact_items = [
                {"Put": {"TableName": table_name, "Item": collection_item}},
                {"Put": {"TableName": table_name, "Item": user_relationship_item}},
            ]

            # Execute transaction
            dynamodb.meta.client.transact_write_items(TransactItems=transact_items)

            logger.info(
                f"Collection created: {collection_id}",
                extra={"collection_id": collection_id},
            )
            metrics.add_metric(
                name="SuccessfulCollectionCreations", unit=MetricUnit.Count, value=1
            )

            # Format response
            response_data = format_collection_item(collection_item, user_context)

            return {
                "statusCode": 201,
                "body": json.dumps(
                    {
                        "success": True,
                        "data": response_data,
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
            logger.exception("Unexpected error creating collection", exc_info=e)
            metrics.add_metric(name="UnexpectedErrors", unit=MetricUnit.Count, value=1)
            from collections_utils import create_error_response

            return create_error_response(
                error_code="InternalServerError",
                error_message="An unexpected error occurred",
                status_code=500,
                request_id=app.current_event.request_context.request_id,
            )
