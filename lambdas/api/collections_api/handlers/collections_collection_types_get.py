"""GET /collections/collection-types - List collection types under collections:view permission.

This endpoint returns collection type summaries so that pages gated by
collections:view (CollectionsPage, CollectionGroupDetailPage, CollectionCard)
can display type icons and colors without requiring the separate
collection-types:view permission (which is a settings-level permission).
"""

import os

from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.metrics import MetricUnit
from db_models import CollectionTypeModel

logger = Logger(
    service="collections-collection-types-get",
    level=os.environ.get("LOG_LEVEL", "INFO"),
)
tracer = Tracer(service="collections-collection-types-get")
metrics = Metrics(namespace="medialake", service="collections-collection-types")

SYSTEM_PK = "SYSTEM"
COLLECTION_TYPE_SK_PREFIX = "COLLTYPE#"


def register_route(app):
    """Register GET /collections/collection-types route"""

    @app.get("/collections/collection-types")
    @tracer.capture_method
    def collections_collection_types_get():
        """Return collection type summaries under collections:view permission."""
        request_id = app.current_event.request_context.request_id

        try:
            items = []
            results = CollectionTypeModel.query(
                SYSTEM_PK,
                CollectionTypeModel.SK.startswith(COLLECTION_TYPE_SK_PREFIX),
            )

            for item in results:
                items.append(
                    {
                        "id": item.SK.replace(COLLECTION_TYPE_SK_PREFIX, ""),
                        "name": item.name,
                        "description": item.description if item.description else None,
                        "color": item.color if hasattr(item, "color") else "#1976d2",
                        "icon": item.icon if hasattr(item, "icon") else "Folder",
                        "isActive": item.isActive,
                        "isSystem": (
                            item.isSystem if hasattr(item, "isSystem") else False
                        ),
                        "createdAt": item.createdAt,
                        "updatedAt": item.updatedAt,
                    }
                )

            logger.info(f"Returned {len(items)} collection type summaries")
            metrics.add_metric(
                name="CollectionTypeSummaryRequests",
                unit=MetricUnit.Count,
                value=1,
            )

            return {
                "success": True,
                "data": items,
                "pagination": {
                    "has_next_page": False,
                    "has_prev_page": False,
                    "limit": len(items),
                },
                "meta": {
                    "timestamp": "",
                    "version": "v1",
                    "request_id": request_id,
                },
            }

        except Exception as e:
            logger.exception("Error fetching collection types", exc_info=e)
            return {
                "statusCode": 500,
                "body": {
                    "success": False,
                    "error": {
                        "code": "INTERNAL_SERVER_ERROR",
                        "message": "An unexpected error occurred",
                    },
                    "meta": {"request_id": request_id},
                },
            }
