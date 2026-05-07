"""GET /collections/<collection_id>/share - List collection shares."""

import os

from aws_lambda_powertools import Logger, Metrics, Tracer
from collections_utils import (
    COLLECTION_PK_PREFIX,
    PERM_SK_PREFIX,
    create_error_response,
    create_success_response,
)
from db_models import ShareModel
from utils.formatting_utils import format_share

logger = Logger(
    service="collections-ID-share-get", level=os.environ.get("LOG_LEVEL", "INFO")
)
tracer = Tracer(service="collections-ID-share-get")
metrics = Metrics(namespace="medialake", service="collection-shares")


def register_route(app):
    """Register GET /collections/<collection_id>/share route"""

    @app.get("/collections/<collection_id>/share")
    @tracer.capture_method
    def collections_ID_share_get(collection_id: str):
        """Get collection shares"""
        try:
            # Query for shares using PynamoDB
            items = []
            try:
                for share in ShareModel.query(
                    f"{COLLECTION_PK_PREFIX}{collection_id}",
                    ShareModel.SK.startswith(PERM_SK_PREFIX),
                ):
                    share_dict = {
                        "PK": share.PK,
                        "SK": share.SK,
                        "targetType": share.targetType,
                        "targetId": share.targetId,
                        "role": share.role,
                        "grantedBy": share.grantedBy,
                        "grantedAt": share.grantedAt,
                    }
                    if share.message:
                        share_dict["message"] = share.message
                    items.append(share_dict)
            except Exception as e:
                logger.warning(f"Error querying shares: {e}")

            formatted_shares = [format_share(item) for item in items]

            return create_success_response(
                data=formatted_shares,
                request_id=app.current_event.request_context.request_id,
            )

        except Exception as e:
            logger.exception("Error listing collection shares", exc_info=e)
            return create_error_response(
                error_code="InternalServerError",
                error_message="An unexpected error occurred",
                status_code=500,
                request_id=app.current_event.request_context.request_id,
            )
