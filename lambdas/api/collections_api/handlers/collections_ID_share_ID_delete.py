"""DELETE /collections/<collection_id>/share/<user_id> - Remove share."""

import os

from aws_lambda_powertools import Logger, Metrics, Tracer
from collections_utils import (
    COLLECTION_PK_PREFIX,
    PERM_SK_PREFIX,
    USER_PK_PREFIX,
    create_error_response,
    create_success_response,
)
from db_models import ShareModel, UserRelationshipModel
from pynamodb.connection import Connection
from pynamodb.exceptions import DoesNotExist
from pynamodb.transactions import TransactWrite

logger = Logger(
    service="collections-ID-share-ID-delete", level=os.environ.get("LOG_LEVEL", "INFO")
)
tracer = Tracer(service="collections-ID-share-ID-delete")
metrics = Metrics(namespace="medialake", service="collection-shares")


def register_route(app):
    """Register DELETE /collections/<collection_id>/share/<user_id> route"""

    @app.delete("/collections/<collection_id>/share/<user_id>")
    @tracer.capture_method
    def collections_ID_share_ID_delete(collection_id: str, user_id: str):
        """Remove share from collection"""
        try:
            # Get the items to delete
            share_pk = f"{COLLECTION_PK_PREFIX}{collection_id}"
            share_sk = f"{PERM_SK_PREFIX}{user_id}"
            user_pk = f"{USER_PK_PREFIX}{user_id}"
            user_sk = f"{COLLECTION_PK_PREFIX}{collection_id}"

            # Try to get both items to ensure they exist
            try:
                share = ShareModel.get(share_pk, share_sk)
                user_rel = UserRelationshipModel.get(user_pk, user_sk)
            except DoesNotExist:
                logger.warning(
                    f"Share not found for user {user_id} and collection {collection_id}"
                )
                return create_error_response(
                    error_code="NotFound",
                    error_message="Share not found",
                    status_code=404,
                    request_id=app.current_event.request_context.request_id,
                )

            # Delete both items in a transaction
            connection = Connection(region=os.environ.get("AWS_REGION", "us-east-1"))
            with TransactWrite(connection=connection) as transaction:
                transaction.delete(share)
                transaction.delete(user_rel)

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
