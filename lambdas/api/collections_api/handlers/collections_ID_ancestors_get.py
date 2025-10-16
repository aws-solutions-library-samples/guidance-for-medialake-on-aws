"""GET /collections/<collection_id>/ancestors - Get collection ancestor chain."""

import json
import os

from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.event_handler.exceptions import NotFoundError
from collections_utils import COLLECTION_PK_PREFIX, METADATA_SK, create_error_response
from db_models import CollectionModel
from pynamodb.exceptions import DoesNotExist

logger = Logger(
    service="collections-ID-ancestors-get", level=os.environ.get("LOG_LEVEL", "INFO")
)
tracer = Tracer(service="collections-ID-ancestors-get")


def register_route(app):
    """Register GET /collections/<collection_id>/ancestors route"""

    @app.get("/collections/<collection_id>/ancestors")
    @tracer.capture_method
    def collections_ID_ancestors_get(collection_id: str):
        """Get the ancestor chain for a collection (from root to current)"""
        try:
            ancestors = []
            current_id = collection_id

            logger.info(f"[ANCESTORS] Building ancestor chain for: {collection_id}")

            # Walk up the parent chain
            max_depth = 10  # Prevent infinite loops
            depth = 0

            while current_id and depth < max_depth:
                # Get current collection using PynamoDB
                try:
                    collection = CollectionModel.get(
                        f"{COLLECTION_PK_PREFIX}{current_id}", METADATA_SK
                    )
                except DoesNotExist:
                    logger.warning(f"[ANCESTORS] Collection not found: {current_id}")
                    break

                # Add to ancestors (we'll reverse at the end)
                parent_id = collection.parentId if collection.parentId else None
                logger.info(
                    f"[ANCESTORS] Processing collection {current_id} (name: {collection.name}, parentId: {parent_id})"
                )

                ancestors.append(
                    {
                        "id": current_id,
                        "name": collection.name,
                        "parentId": parent_id,
                    }
                )

                # Move to parent
                current_id = parent_id
                depth += 1

            # Reverse to get root -> current order
            ancestors.reverse()

            logger.info(
                f"[ANCESTORS] Found {len(ancestors)} ancestors for {collection_id}"
            )

            return {
                "statusCode": 200,
                "body": json.dumps(
                    {
                        "success": True,
                        "data": ancestors,
                        "meta": {
                            "request_id": app.current_event.request_context.request_id,
                        },
                    }
                ),
            }

        except NotFoundError:
            raise
        except Exception as e:
            logger.exception(
                f"[ANCESTORS] Error getting ancestors for {collection_id}", exc_info=e
            )
            return create_error_response(
                error_code="InternalServerError",
                error_message="An unexpected error occurred",
                status_code=500,
                request_id=app.current_event.request_context.request_id,
            )
