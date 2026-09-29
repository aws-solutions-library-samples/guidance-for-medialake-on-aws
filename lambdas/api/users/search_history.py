"""Per-user search history: the most recent distinct searches, newest first.

Routes:
    GET    /users/search-history                -> list
    POST   /users/search-history                -> record {definition}
    DELETE /users/search-history                -> clear everything
    DELETE /users/search-history/{fingerprint}  -> remove one entry

Storage: a single row per user in the users table,
``userId=USER#{sub}, itemKey=SEARCH_HISTORY``, holding at most
``MAX_HISTORY_ENTRIES`` entries. A repeated search moves to the top instead of
being duplicated. Writes are guarded by a ``version`` attribute and retried on
conflict, so two tabs recording at once cannot drop each other's entries.

The browser only records *committed* searches (Enter, the Search button, or
replaying a recent/saved search), never the debounced search that runs while
typing.
"""

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from auth_utils import get_authenticated_user_id
from aws_lambda_powertools.metrics import MetricUnit
from botocore.exceptions import ClientError
from response_utils import error_response, success_response
from search_definition import SearchDefinitionError, is_blank, parse_definition

MAX_HISTORY_ENTRIES = 5
HISTORY_ITEM_KEY = "SEARCH_HISTORY"
_MAX_WRITE_ATTEMPTS = 3


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _key(user_id: str) -> Dict[str, str]:
    return {"userId": f"USER#{user_id}", "itemKey": HISTORY_ITEM_KEY}


def _load(table, user_id: str):
    """Return (entries, version) for the user's history row."""
    item = table.get_item(Key=_key(user_id), ConsistentRead=True).get("Item")
    if not item:
        return [], None
    try:
        entries = json.loads(item.get("entriesJson") or "[]")
    except (TypeError, ValueError):
        entries = []
    return entries, int(item.get("version", 0))


def _save(table, user_id: str, entries: List[Dict[str, Any]], version) -> None:
    """Write the history row, failing if someone else wrote since we read it."""
    item = {
        **_key(user_id),
        "itemType": "SEARCH_HISTORY",
        # Stored as JSON text: definitions can carry floats, which boto3 will
        # not write as DynamoDB numbers, and the exact shape must round-trip.
        "entriesJson": json.dumps(entries, separators=(",", ":"), ensure_ascii=False),
        "version": (version or 0) + 1,
        "updatedAt": _now_iso(),
    }
    if version is None:
        condition = "attribute_not_exists(userId)"
        values = None
    else:
        condition = "version = :expected"
        values = {":expected": version}
    kwargs: Dict[str, Any] = {"Item": item, "ConditionExpression": condition}
    if values:
        kwargs["ExpressionAttributeValues"] = values
    table.put_item(**kwargs)


def _update(table, user_id: str, change) -> List[Dict[str, Any]]:
    """Read-modify-write with optimistic concurrency. ``change`` maps old -> new."""
    for attempt in range(_MAX_WRITE_ATTEMPTS):
        entries, version = _load(table, user_id)
        updated = change(entries)
        if updated == entries:
            return entries
        try:
            _save(table, user_id, updated, version)
            return updated
        except ClientError as e:
            code = e.response.get("Error", {}).get("Code")
            if code != "ConditionalCheckFailedException" or attempt == (
                _MAX_WRITE_ATTEMPTS - 1
            ):
                raise
    return updated  # pragma: no cover - loop always returns or raises


def _user_or_error(app, user_table_name, logger, metrics):
    user_id = get_authenticated_user_id(app, logger)
    if not user_id:
        metrics.add_metric(name="MissingUserIdError", unit=MetricUnit.Count, value=1)
        return None, error_response(400, "Unable to identify user")
    if not user_table_name:
        logger.error("USER_TABLE_NAME environment variable not set")
        return None, error_response(500, "Internal configuration error")
    return user_id, None


def _payload(entries: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {"items": entries[:MAX_HISTORY_ENTRIES], "limit": MAX_HISTORY_ENTRIES}


def handle_get_search_history(app, dynamodb, user_table_name, logger, metrics, tracer):
    try:
        user_id, error = _user_or_error(app, user_table_name, logger, metrics)
        if error:
            return error
        entries, _ = _load(dynamodb.Table(user_table_name), user_id)
        return success_response(200, "Search history retrieved", _payload(entries))
    except Exception:
        logger.exception("Error retrieving search history")
        metrics.add_metric(name="UnhandledError", unit=MetricUnit.Count, value=1)
        return error_response(500, "Internal server error")


def handle_record_search(app, dynamodb, user_table_name, logger, metrics, tracer):
    try:
        user_id, error = _user_or_error(app, user_table_name, logger, metrics)
        if error:
            return error

        try:
            body = app.current_event.json_body
        except Exception:
            return error_response(400, "Invalid request body format")
        if not isinstance(body, dict) or "definition" not in body:
            return error_response(400, "Request body must contain a 'definition'")

        try:
            definition, fp = parse_definition(body["definition"])
        except SearchDefinitionError as e:
            return error_response(400, str(e))

        table = dynamodb.Table(user_table_name)
        if is_blank(definition):
            entries, _ = _load(table, user_id)
            return success_response(
                200, "Blank searches are not recorded", _payload(entries)
            )

        entry = {"fingerprint": fp, "definition": definition, "searchedAt": _now_iso()}

        def prepend(entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
            rest = [e for e in entries if e.get("fingerprint") != fp]
            return [entry, *rest][:MAX_HISTORY_ENTRIES]

        entries = _update(table, user_id, prepend)
        metrics.add_metric(name="SearchRecorded", unit=MetricUnit.Count, value=1)
        return success_response(200, "Search recorded", _payload(entries))
    except Exception:
        logger.exception("Error recording search")
        metrics.add_metric(name="UnhandledError", unit=MetricUnit.Count, value=1)
        return error_response(500, "Internal server error")


def handle_delete_search_history(
    app,
    dynamodb,
    user_table_name,
    logger,
    metrics,
    tracer,
    fingerprint: Optional[str] = None,
):
    """Remove one entry, or the whole history when no fingerprint is given."""
    try:
        user_id, error = _user_or_error(app, user_table_name, logger, metrics)
        if error:
            return error
        table = dynamodb.Table(user_table_name)

        if fingerprint is None:
            table.delete_item(Key=_key(user_id))
            logger.info(
                "Audit: search history cleared",
                extra={"user_id": user_id, "action": "CLEAR_SEARCH_HISTORY"},
            )
            return success_response(200, "Search history cleared", _payload([]))

        entries = _update(
            table,
            user_id,
            lambda current: [e for e in current if e.get("fingerprint") != fingerprint],
        )
        return success_response(200, "Search removed from history", _payload(entries))
    except Exception:
        logger.exception("Error deleting search history")
        metrics.add_metric(name="UnhandledError", unit=MetricUnit.Count, value=1)
        return error_response(500, "Internal server error")
