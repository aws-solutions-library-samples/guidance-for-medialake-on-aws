"""DELETE /collections/<collection_id>/items/<item_id> - Remove item from collection."""

import os
from datetime import datetime
from urllib.parse import unquote

from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.event_handler.exceptions import NotFoundError
from collection_activity import record_collection_activity
from collection_events import publish_collection_assets_removed
from collections_utils import (
    COLLECTION_PK_PREFIX,
    create_error_response,
    create_success_response,
    require_collection_role,
)
from custom_exceptions import ForbiddenError
from db_models import CollectionItemModel, CollectionModel
from pynamodb.exceptions import DeleteError, DoesNotExist, UpdateError
from user_auth import extract_user_context
from utils.item_utils import ASSET_SK_PREFIX, ITEM_SK_PREFIX

logger = Logger(
    service="collections-ID-items-ID-delete", level=os.environ.get("LOG_LEVEL", "INFO")
)
tracer = Tracer(service="collections-ID-items-ID-delete")
metrics = Metrics(namespace="medialake", service="collection-items")


def _is_conditional_check_failure(error: DeleteError) -> bool:
    """True when a DeleteError was caused by the SK-does-not-exist condition failing.

    Reads PynamoDB's structured cause code (``cause_response_code``, which resolves
    to the wrapped botocore ``Error.Code``) rather than the exception's message text,
    mirroring the equivalent helper in ``collections_ID_items_post``.

    An error that cannot be classified is deliberately *not* treated as
    "row absent": it is re-raised. Misclassifying a genuine delete failure as an
    absent row would swallow the failure and report ``removed: true`` for an item
    that is still in the collection.
    """
    return (
        getattr(error, "cause_response_code", None) == "ConditionalCheckFailedException"
    )


def register_route(app):
    """Register DELETE /collections/<collection_id>/items/<item_id> route"""

    @app.delete("/collections/<collection_id>/items/<item_id>")
    @tracer.capture_method
    def collections_ID_items_ID_delete(collection_id: str, item_id: str):
        """Remove item from collection"""
        try:
            current_timestamp = datetime.utcnow().isoformat() + "Z"

            user_context = extract_user_context(app.current_event.raw_event)
            user_id = user_context.get("user_id")

            # Object-level authorization: only the collection owner or an editor
            # may remove items. The custom authorizer only enforces the coarse
            # tenant-wide permission, so this per-collection check is required to
            # stop any holder of collections:remove_assets/collections:edit from
            # removing items from collections they do not own or can edit.
            collection, _ = require_collection_role(
                collection_id, user_id, minimum_role="EDITOR"
            )

            # URL decode the item_id (API Gateway doesn't auto-decode path parameters)
            decoded_item_id = unquote(item_id)

            logger.info(f"[DELETE] Received item_id (raw): {item_id}")
            logger.info(f"[DELETE] Decoded item_id: {decoded_item_id}")
            logger.info(f"[DELETE] Collection: {collection_id}")

            # Support both old ITEM# and new ASSET# formats
            sk = (
                decoded_item_id
                if decoded_item_id.startswith(ASSET_SK_PREFIX)
                or decoded_item_id.startswith(ITEM_SK_PREFIX)
                else f"{ITEM_SK_PREFIX}{decoded_item_id}"
            )

            logger.info(f"[DELETE] Final SK to delete: {sk}")
            logger.info(f"[DELETE] PK: {COLLECTION_PK_PREFIX}{collection_id}")

            # Delete the item using PynamoDB
            #
            # The delete is conditional on the row existing. DynamoDB's DeleteItem
            # is unconditional by nature and reports success even when the key is
            # absent, so PynamoDB raises nothing for an item that was never in the
            # collection — which previously produced a 200 "removed": true for a
            # request that removed nothing.
            item_deleted = False
            try:
                item = CollectionItemModel(f"{COLLECTION_PK_PREFIX}{collection_id}", sk)
                logger.info(
                    f"[DELETE] Attempting to delete item with PK={item.PK}, SK={item.SK}"
                )
                item.delete(condition=CollectionItemModel.SK.exists())
                item_deleted = True
                logger.info(f"[DELETE] Successfully deleted item")
            except DoesNotExist:
                logger.warning(
                    f"[DELETE] Item not found: {decoded_item_id} (SK: {sk}) in collection {collection_id}"
                )
            except DeleteError as e:
                # A failed condition means the row was not there; anything else is a
                # real failure and must not be reported as a successful removal.
                if _is_conditional_check_failure(e):
                    logger.warning(
                        f"[DELETE] Item not present, nothing deleted: {decoded_item_id} "
                        f"(SK: {sk}) in collection {collection_id}"
                    )
                else:
                    logger.error(f"[DELETE] Error deleting item: {e}")
                    raise

            if not item_deleted:
                # Nothing was removed. 404 is the contract this handler already
                # applies to a missing collection (require_collection_role) and how
                # the rest of the collections API reports an absent resource.
                raise NotFoundError(
                    f"Item '{decoded_item_id}' not found in collection '{collection_id}'"
                )

            # Update collection: decrement itemCount atomically and refresh timestamps
            #
            # Only reached when a row was actually deleted (the 404 above returns
            # otherwise), so the stored counter cannot drift below the true item
            # count and updatedAt is not bumped for a request that changed nothing.
            # Note: itemCount is maintained as a stored counter for efficient listing.
            try:
                # Reuse the collection loaded during the authorization check
                # above to avoid a redundant DynamoDB read.
                # Decrement itemCount only when it's > 0 to prevent negatives.
                try:
                    collection.update(
                        actions=[
                            CollectionModel.updatedAt.set(current_timestamp),
                            CollectionModel.itemCount.set(
                                (CollectionModel.itemCount - 1)
                            ),
                        ],
                        condition=(CollectionModel.itemCount > 0),
                    )
                except UpdateError:
                    # itemCount is already 0 — still update timestamps.
                    logger.warning(
                        f"[DELETE] itemCount already 0 for collection {collection_id}, "
                        "skipping decrement"
                    )
                    collection.update(
                        actions=[
                            CollectionModel.updatedAt.set(current_timestamp),
                        ]
                    )
                logger.info(f"[DELETE] Updated collection updatedAt timestamp")
            except Exception as e:
                logger.warning(f"[DELETE] Failed to update collection timestamp: {e}")

            logger.info(f"[DELETE] Item removed from collection {collection_id}")

            # Record activity for the recent-collections tracker (Req 11.2)
            if user_id:
                record_collection_activity(user_id, collection_id)

            # Emit CollectionAssetRemoved referencing the underlying asset id.
            # ASSET# rows encode the asset id as ASSET#{asset_id}#...; legacy
            # ITEM# rows have no clean asset id, so fall back to the item id.
            if sk.startswith(ASSET_SK_PREFIX):
                asset_ref = sk[len(ASSET_SK_PREFIX) :].split("#", 1)[0]
            else:
                asset_ref = decoded_item_id
            publish_collection_assets_removed(
                collection_id,
                [asset_ref],
                collection_name=getattr(collection, "name", None),
                collection_type_id=getattr(collection, "collectionTypeId", None),
                user_id=user_id,
            )

            return create_success_response(
                data={"id": decoded_item_id, "removed": True},
                request_id=app.current_event.request_context.request_id,
            )

        except (ForbiddenError, NotFoundError):
            raise
        except Exception as e:
            logger.exception("Error removing collection item", exc_info=e)
            return create_error_response(
                error_code="InternalServerError",
                error_message="An unexpected error occurred",
                status_code=500,
                request_id=app.current_event.request_context.request_id,
            )
