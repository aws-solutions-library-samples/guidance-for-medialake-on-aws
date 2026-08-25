"""POST /collections/<collection_id>/items - Add item to collection."""

import json
import os
from datetime import datetime

from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.event_handler.exceptions import (
    BadRequestError,
    NotFoundError,
)
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.parser import ValidationError, parse
from collection_activity import record_collection_activity
from collection_events import publish_collection_assets_added
from collections_utils import (
    COLLECTION_PK_PREFIX,
    create_error_response,
    require_collection_role,
)
from custom_exceptions import ForbiddenError
from db_models import CollectionItemModel, CollectionModel
from models import MAX_ITEMS_PER_REQUEST, AddItemToCollectionRequest
from pynamodb.exceptions import PutError
from user_auth import extract_user_context
from utils.formatting_utils import format_collection_item
from utils.item_utils import ITEM_SK_PREFIX, generate_asset_sk
from utils.opensearch_utils import get_all_clips_for_asset

logger = Logger(
    service="collections-ID-items-post", level=os.environ.get("LOG_LEVEL", "INFO")
)
tracer = Tracer(service="collections-ID-items-post")
metrics = Metrics(namespace="medialake", service="collection-items")

# Upper bound on legacy ITEM# rows read when checking for cross-format duplicates. Keeps one
# unusually large legacy collection from turning every add into a long paginated read; past
# the bound the check is simply incomplete, matching the previous behaviour.
MAX_LEGACY_ROWS_SCANNED = 2000


# Milliseconds of Lambda budget to keep in reserve rather than starting another write.
#
# The item cap bounds how many writes are queued, not how long each takes, so it cannot on its
# own keep a request inside API Gateway's 29s window — a few hundred slow writes still would
# not fit. Stopping while there is budget left turns being killed mid-loop, where the caller
# gets nothing back and cannot tell what persisted, into an ordinary response that names the
# items nothing was attempted for. The reserve covers finishing the loop, the metadata update
# and serialising the response.
def _env_int(name, default):
    """Parse a positive int from the environment, falling back on anything unusable.

    Runs at import time, so raising here would fail every request with an init error before
    any handler code runs — a misconfigured tuning value should not be able to take the
    endpoint down.
    """
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except (TypeError, ValueError):
        logger.warning(f"Invalid {name}={raw!r}; falling back to {default}")
        return default
    if value < 1:
        logger.warning(f"Invalid {name}={raw!r}; falling back to {default}")
        return default
    return value


WRITE_DEADLINE_RESERVE_MS = _env_int("WRITE_DEADLINE_RESERVE_MS", 5000)


def _is_conditional_check_failure(error: PutError) -> bool:
    """True when a PutError was caused by the SK-does-not-exist condition failing.

    Reads PynamoDB's structured cause code (``cause_response_code``, which resolves to the
    wrapped botocore ``Error.Code``) rather than the exception's message text.

    An error that cannot be classified is deliberately *not* treated as a duplicate. The two
    misclassifications are not equally costly: reporting "already present" for a write that
    actually failed tells the caller the asset is in the collection when it isn't, silently
    dropping what they asked for, whereas reporting a failure prompts a retry — and retrying
    a genuine duplicate is a harmless no-op now that the conditional write makes adds
    idempotent. Matching on message text could only ever produce the unsafe direction, since
    PynamoDB embeds the botocore string in the message for every wrapped error, not just this
    one.
    """
    return (
        getattr(error, "cause_response_code", None) == "ConditionalCheckFailedException"
    )


def _reject_oversized_expansion(items_to_add):
    """Reject a request that resolves to more rows than one synchronous call should write.

    The request-level cap bounds the assets asked for, but ``addAllClips`` expands one asset
    into one item per clip, so the resolved count is what actually decides how many writes
    follow. Checked here, before the first write, because the alternative is exhausting API
    Gateway's 29s window partway through the loop: the caller gets no response while part of
    its selection has already been persisted, and a retry sees that partial state.
    """
    if len(items_to_add) > MAX_ITEMS_PER_REQUEST:
        raise BadRequestError(
            f"Request resolves to {len(items_to_add)} items, "
            f"which exceeds the {MAX_ITEMS_PER_REQUEST} limit. "
            "Add fewer assets per request, or select specific clips "
            "instead of using addAllClips."
        )


def _dedupe_key(asset_id, boundary):
    """Identity of a collection item independent of which SK format stores it.

    Empty strings rather than None for a whole-asset item, so a missing boundary and an
    empty one compare equal.
    """
    boundary = boundary or {}
    return (
        asset_id,
        boundary.get("startTime") or "",
        boundary.get("endTime") or "",
    )


def _legacy_item_keys(collection_id):
    """Dedupe keys for the collection's legacy ``ITEM#{uuid}`` rows.

    Needed because the conditional write can only see the canonical ``ASSET#`` key.
    Collections predating that key store the same asset under ``ITEM#{uuid}``, where the SK
    carries a uuid rather than the asset id, so the only way to recognise one is to read the
    rows and compare attributes.

    Safe to do as a read-then-check: nothing creates ``ITEM#`` rows any more — every writer
    goes through ``generate_asset_sk`` — so this set can only shrink under us, never grow. A
    row deleted between the read and the write just means an add is reported as already
    present; the caller retries and it succeeds.

    One query per request, not per item, and projected down to the three attributes needed.
    Failures are logged and treated as "no legacy rows": this check exists to avoid a
    duplicate, and it must not be the reason an add fails outright.
    """
    keys = set()
    try:
        scanned = 0
        for row in CollectionItemModel.query(
            f"{COLLECTION_PK_PREFIX}{collection_id}",
            CollectionItemModel.SK.startswith(ITEM_SK_PREFIX),
            attributes_to_get=["SK", "assetId", "clipBoundary"],
        ):
            scanned += 1
            if scanned > MAX_LEGACY_ROWS_SCANNED:
                # Bounded so one pathological collection can't turn every add into a long
                # paginated read. Past the bound the dedupe is incomplete, which is the
                # pre-existing behaviour rather than a new failure.
                logger.warning(
                    f"[ADD_ITEM] Legacy dedupe truncated at {MAX_LEGACY_ROWS_SCANNED} "
                    f"rows for {collection_id}; duplicates beyond it are not detected"
                )
                break
            if not row.assetId:
                continue
            boundary = row.clipBoundary.as_dict() if row.clipBoundary else {}
            keys.add(_dedupe_key(row.assetId, boundary))
    except Exception as e:
        logger.warning(
            f"[ADD_ITEM] Could not read legacy items for {collection_id}, "
            f"skipping legacy dedupe: {e}"
        )
    return keys


def _split_out_legacy_duplicates(items_to_add, legacy_keys):
    """Partition resolved items into those to write and those a legacy row already holds.

    Returns ``(to_write, already_present)``. Reported as alreadyPresent rather than written,
    because writing would put the same asset in the collection twice under two key formats
    and count both in itemCount.
    """
    if not legacy_keys:
        return items_to_add, []

    to_write = []
    already_present = []
    for item_data in items_to_add:
        key = _dedupe_key(item_data["assetId"], item_data["clipBoundary"])
        if key in legacy_keys:
            already_present.append(
                {"assetId": item_data["assetId"], "status": "alreadyPresent"}
            )
            logger.info(
                f"[ADD_ITEM] Already present as a legacy item, skipped: "
                f"{item_data['assetId']}"
            )
        else:
            to_write.append(item_data)
    return to_write, already_present


def _out_of_write_time(app):
    """True when too little Lambda budget remains to safely start another write.

    Returns False when the remaining time cannot be determined, so an environment without a
    Lambda context (local runs, tests) behaves exactly as before rather than refusing to
    write anything.
    """
    context = getattr(app, "lambda_context", None)
    remaining = getattr(context, "get_remaining_time_in_millis", None)
    if remaining is None:
        return False
    try:
        return remaining() < WRITE_DEADLINE_RESERVE_MS
    except Exception:  # pragma: no cover - defensive
        return False


def _is_total_write_failure(added_items, already_present, failed):
    """True when every write failed and nothing is in the collection as a result.

    Distinguished from a partial failure, which still reports 201 with the per-item counts:
    here there is nothing to report as done, so answering "created" would tell the caller
    their asset is in the collection when it isn't. Items that were already present count as
    not-a-failure — the collection does hold them.
    """
    return bool(failed) and not added_items and not already_present


def _expand_specs_to_items(specs):
    """Flatten the requested assets into the concrete collection items to write.

    One asset can become several items when ``addAllClips`` is set, so this is a
    flat-map rather than a map. Each returned entry is
    ``{"SK", "assetId", "clipBoundary"}``.

    A spec that carries a clip boundary keeps it: a clip selected in the bin lands in the
    collection as that clip, not as the whole asset. ``addAllClips`` is therefore only
    honoured when no explicit boundary was given, matching the previous single-asset
    behaviour.
    """
    items_to_add = []

    for spec in specs:
        # Every addAllClips spec costs a sequential clip lookup, and the request is rejected
        # once the resolved total passes the cap regardless — so stop rather than keep paying
        # for reads whose results are thrown away. Checked here and enforced by the caller,
        # which keeps the rejection in one place.
        if len(items_to_add) > MAX_ITEMS_PER_REQUEST:
            break

        spec_asset_id = spec.assetId
        spec_boundary = spec.clipBoundary or {}

        if spec.addAllClips and not spec_boundary.get("startTime"):
            logger.info(f"[ADD_ITEM] Adding all clips for asset {spec_asset_id}")
            clips = get_all_clips_for_asset(spec_asset_id)

            if clips:
                for clip in clips:
                    items_to_add.append(
                        {
                            "SK": generate_asset_sk(spec_asset_id, clip),
                            "assetId": spec_asset_id,
                            "clipBoundary": clip,
                        }
                    )
                continue

            logger.info(
                f"[ADD_ITEM] No clips found, adding full file for asset {spec_asset_id}"
            )
            items_to_add.append(
                {
                    "SK": generate_asset_sk(spec_asset_id, None),
                    "assetId": spec_asset_id,
                    "clipBoundary": {},
                }
            )
            continue

        items_to_add.append(
            {
                "SK": generate_asset_sk(
                    spec_asset_id, spec_boundary if spec_boundary else None
                ),
                "assetId": spec_asset_id,
                "clipBoundary": spec_boundary if spec_boundary else {},
            }
        )

    return items_to_add


def register_route(app):
    """Register POST /collections/<collection_id>/items route"""

    @app.post("/collections/<collection_id>/items")
    @tracer.capture_method
    def collections_ID_items_post(collection_id: str):
        """Add item(s) to collection with Pydantic validation and clip boundary support"""
        try:
            user_context = extract_user_context(app.current_event.raw_event)

            # Parse and validate with Pydantic
            try:
                request_data = parse(
                    event=app.current_event.json_body,
                    model=AddItemToCollectionRequest,
                )
            except ValidationError as e:
                logger.warning(f"Validation error adding item: {e}")
                raise BadRequestError(f"Validation error: {str(e)}")

            current_timestamp = datetime.utcnow().isoformat() + "Z"
            user_id = user_context.get("user_id")

            # Object-level authorization: the caller must be the collection
            # owner or an editor. The custom authorizer only checks the coarse
            # tenant-wide permission, so without this check any user holding
            # collections:add_assets/collections:edit could add assets to a
            # collection they do not own or have edit access to.
            collection, _ = require_collection_role(
                collection_id, user_id, minimum_role="EDITOR"
            )

            specs = request_data.resolved_items()

            # (SK, assetId, clipBoundary) triples, flattened across every requested asset.
            items_to_add = _expand_specs_to_items(specs)
            _reject_oversized_expansion(items_to_add)

            # Drop anything a legacy ITEM# row already holds. The conditional write below
            # only guarantees uniqueness of the canonical ASSET# key, so without this the
            # same asset can land in the collection twice under the two formats — both
            # returned by GET, both counted in itemCount.
            items_to_add, already_present = _split_out_legacy_duplicates(
                items_to_add, _legacy_item_keys(collection_id)
            )

            # Add all items to DynamoDB using PynamoDB
            added_items = []
            failed = []
            not_attempted = []
            for index, item_data in enumerate(items_to_add):
                if _out_of_write_time(app):
                    # Out of budget: name the rest rather than being killed mid-loop, which
                    # would leave the caller with no response and no way to tell what landed.
                    not_attempted = [
                        {"assetId": pending["assetId"], "status": "notAttempted"}
                        for pending in items_to_add[index:]
                    ]
                    logger.warning(
                        f"[ADD_ITEM] Stopped before the Lambda deadline with "
                        f"{len(not_attempted)} item(s) unattempted for {collection_id}"
                    )
                    break

                item = CollectionItemModel()
                item.PK = f"{COLLECTION_PK_PREFIX}{collection_id}"
                item.SK = item_data["SK"]
                item.itemType = "asset"
                item.assetId = item_data["assetId"]
                item.clipBoundary = item_data["clipBoundary"]
                item.addedAt = current_timestamp
                item.addedBy = user_id

                if request_data.sortOrder is not None:
                    item.sortOrder = request_data.sortOrder
                if request_data.metadata:
                    item.metadata = request_data.metadata

                # Set GSI2 for reverse lookup (item to collections)
                item.GSI2_PK = item_data["SK"]
                item.GSI2_SK = f"{COLLECTION_PK_PREFIX}{collection_id}"

                try:
                    # Conditional on the row not already existing, so re-adding is a
                    # no-op instead of an overwrite. Two things depend on this:
                    # itemCount below counts only genuinely new rows (it previously
                    # incremented on every add, inflating on repeats), and an asset
                    # already in the collection keeps its original addedAt/addedBy
                    # rather than being silently re-stamped.
                    #
                    # This covers the canonical ASSET# key only; the same asset stored
                    # under a legacy ITEM#{uuid} row is invisible to the condition, which
                    # is why those are filtered out above before the loop.
                    item.save(CollectionItemModel.SK.does_not_exist())

                    # Convert to dict for formatting
                    item_dict = {
                        "PK": item.PK,
                        "SK": item.SK,
                        "itemType": item.itemType,
                        "assetId": item.assetId,
                        "clipBoundary": (
                            item.clipBoundary.as_dict() if item.clipBoundary else {}
                        ),
                        "sortOrder": item.sortOrder if item.sortOrder else 0,
                        "metadata": item.metadata.as_dict() if item.metadata else {},
                        "addedAt": item.addedAt,
                        "addedBy": item.addedBy,
                    }
                    added_items.append(item_dict)
                    logger.info(f"[ADD_ITEM] Added item with SK: {item_data['SK']}")
                except PutError as e:
                    # A failed condition means the item is already in the collection.
                    # PynamoDB surfaces it as a PutError wrapping
                    # ConditionalCheckFailedException, so match on the cause rather than
                    # the message text.
                    if _is_conditional_check_failure(e):
                        already_present.append(
                            {
                                "assetId": item_data["assetId"],
                                "status": "alreadyPresent",
                            }
                        )
                        logger.info(
                            f"[ADD_ITEM] Item already present, skipped: {item_data['SK']}"
                        )
                    else:
                        failed.append(
                            {"assetId": item_data["assetId"], "status": "failed"}
                        )
                        logger.error(f"[ADD_ITEM] Error adding item: {e}")

            # Refresh the collection's updatedAt timestamp. itemCount is also
            # incremented for backward compatibility, but it is deprecated and
            # no longer the source of truth — both the list and detail endpoints
            # now compute item counts dynamically from CollectionItemModel rows.
            # Only newly-created rows are counted, so repeat adds no longer inflate it.
            try:
                # Reuse the collection loaded during the authorization check
                # above to avoid a redundant DynamoDB read.
                actions = [CollectionModel.updatedAt.set(current_timestamp)]
                if added_items:
                    actions.append(
                        CollectionModel.itemCount.set(
                            (CollectionModel.itemCount + len(added_items))
                        )
                    )
                collection.update(actions=actions)
            except Exception as e:
                logger.warning(
                    f"[ADD_ITEM] Failed to update collection metadata "
                    f"(updatedAt/itemCount) for {collection_id}: {e}"
                )

            logger.info(
                f"[ADD_ITEM] Added {len(added_items)} item(s) to collection "
                f"{collection_id} ({len(already_present)} already present, "
                f"{len(failed)} failed, {len(not_attempted)} not attempted)"
            )
            metrics.add_metric(
                name="SuccessfulItemAdditions",
                unit=MetricUnit.Count,
                value=len(added_items),
            )

            # Record activity for the recent-collections tracker (Req 11.1)
            if added_items and user_id:
                record_collection_activity(user_id, collection_id)

            # Emit one batched CollectionAssetAdded referencing the distinct asset
            # ids added in this call (clips of the same asset collapse to one id).
            # Best-effort: never blocks the add-item response.
            if added_items:
                publish_collection_assets_added(
                    collection_id,
                    [item["assetId"] for item in added_items],
                    collection_name=getattr(collection, "name", None),
                    collection_type_id=getattr(collection, "collectionTypeId", None),
                    user_id=user_id,
                )

            from aws_lambda_powertools.event_handler import Response, content_types

            # Every write failed and nothing ended up in the collection. Returning 201 with
            # success: true here would tell a caller their asset was added when it was not —
            # and a legacy single-asset caller checks nothing but the status code.
            #
            # Pre-existing rather than introduced by the bulk shape: main also swallowed
            # PutError and returned 201. It is the same false-success class the duplicate
            # classifier avoids, so it is corrected here. A *partial* failure still returns
            # 201, with failedCount and results describing what did not land.
            if _is_total_write_failure(
                added_items, already_present, failed + not_attempted
            ):
                return create_error_response(
                    error_code="InternalServerError",
                    error_message=(
                        f"Failed to add {len(failed) + len(not_attempted)} "
                        "item(s) to collection"
                    ),
                    status_code=500,
                    request_id=app.current_event.request_context.request_id,
                )

            return Response(
                status_code=201,
                content_type=content_types.APPLICATION_JSON,
                body=json.dumps(
                    {
                        "success": True,
                        "data": {
                            "addedCount": len(added_items),
                            # Present so a bulk caller can report "10 added, 2 already
                            # there, 1 failed" instead of a bare success.
                            "alreadyPresentCount": len(already_present),
                            "failedCount": len(failed),
                            # Non-zero only when the request ran out of Lambda budget; the
                            # named items were never written and are safe to retry.
                            "notAttemptedCount": len(not_attempted),
                            "results": already_present + failed + not_attempted,
                            "items": [
                                format_collection_item(item) for item in added_items
                            ],
                        },
                        "meta": {
                            "timestamp": current_timestamp,
                            "version": "v1",
                            "request_id": app.current_event.request_context.request_id,
                        },
                    }
                ),
            )

        except (BadRequestError, ForbiddenError, NotFoundError):
            raise
        except Exception as e:
            logger.exception("Error adding collection item", exc_info=e)
            return create_error_response(
                error_code="InternalServerError",
                error_message="An unexpected error occurred",
                status_code=500,
                request_id=app.current_event.request_context.request_id,
            )
