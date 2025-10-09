"""DELETE /collections/<collection_id>/share/<user_id> - Remove share."""

import os

from aws_lambda_powertools import Logger, Metrics, Tracer
from collections_utils import (
    COLLECTION_PK_PREFIX,
    USER_PK_PREFIX,
    create_error_response,
    create_success_response,
)

logger = Logger(
    service="collections-ID-share-ID-delete", level=os.environ.get("LOG_LEVEL", "INFO")
)
tracer = Tracer(service="collections-ID-share-ID-delete")
metrics = Metrics(namespace="medialake", service="collection-shares")

PERM_SK_PREFIX = "PERM#"


def register_route(app, dynamodb, table_name):
    """Register DELETE /collections/<collection_id>/share/<user_id> route"""

    @app.delete("/collections/<collection_id>/share/<user_id>")
    @tracer.capture_method
    def collections_ID_share_ID_delete(collection_id: str, user_id: str):
        """Remove share from collection"""
        try:
            # Delete permission and user relationship
            dynamodb.meta.client.transact_write_items(
                TransactItems=[
                    {
                        "Delete": {
                            "TableName": table_name,
                            "Key": {
                                "PK": f"{COLLECTION_PK_PREFIX}{collection_id}",
                                "SK": f"{PERM_SK_PREFIX}{user_id}",
                            },
                        }
                    },
                    {
                        "Delete": {
                            "TableName": table_name,
                            "Key": {
                                "PK": f"{USER_PK_PREFIX}{user_id}",
                                "SK": f"{COLLECTION_PK_PREFIX}{collection_id}",
                            },
                        }
                    },
                ]
            )

            logger.info(
                f"Share removed for user {user_id} from collection {collection_id}"
            )

            return create_success_response(
                data={"userId": user_id, "removed": True},
                request_id=app.current_event.request_context.request_id,
            )

        except Exception as e:
            logger.exception("Error removing share", exc_info=e)
            return create_error_response(
                error_code="InternalServerError",
                error_message="An unexpected error occurred",
                status_code=500,
                request_id=app.current_event.request_context.request_id,
            )
