"""GET /collections/recent - List user's recently modified collections."""

import os

import boto3
from aws_lambda_powertools import Logger, Tracer
from boto3.dynamodb.conditions import Key
from collections_utils import (
    COLLECTION_PK_PREFIX,
    METADATA_SK,
    create_cursor,
    create_success_response,
    format_collection_item,
    get_user_collection_role,
    parse_cursor,
)
from user_auth import extract_user_context

logger = Logger(
    service="collections-recent-get", level=os.environ.get("LOG_LEVEL", "INFO")
)
tracer = Tracer(service="collections-recent-get")

DEFAULT_RECENT_PAGE_SIZE = 5
MAX_RECENT_PAGE_SIZE = 50

_dynamodb = boto3.resource("dynamodb")
_user_table = _dynamodb.Table(os.environ.get("USER_TABLE_NAME", "user_table_dev"))
_collections_table = _dynamodb.Table(
    os.environ.get("COLLECTIONS_TABLE_NAME", "collections_table_dev")
)


def _cursor_to_start_key(parsed):
    """Rebuild the GSI4 ExclusiveStartKey from a parsed cursor.

    A GSI4 query's start key needs the base-table keys (userId, itemKey) AND the
    index keys (gsi4Pk, gsi4Sk). GSI4 projects ALL, so every returned row carries
    all four.
    """
    if not parsed:
        return None
    return {
        "userId": parsed["pk"],
        "itemKey": parsed["sk"],
        "gsi4Pk": parsed["gsi_pk"],
        "gsi4Sk": parsed["gsi_sk"],
    }


def _get_collection_metadata(collection_id):
    """Fetch collection METADATA row from the collections table."""
    try:
        resp = _collections_table.get_item(
            Key={"PK": f"{COLLECTION_PK_PREFIX}{collection_id}", "SK": METADATA_SK}
        )
        return resp.get("Item")
    except Exception as e:
        logger.warning(
            "Failed to get collection metadata",
            extra={"collection_id": collection_id, "error": str(e)},
        )
        return None


def register_route(app):
    """Register GET /collections/recent route."""

    @app.get("/collections/recent")
    @tracer.capture_method
    def collections_recent_get():
        user_context = extract_user_context(app.current_event.raw_event)
        user_id = user_context.get("user_id")

        # Clamp (do not reject) an over-large requested size to MAX_RECENT_PAGE_SIZE.
        try:
            requested = int(
                app.current_event.get_query_string_value(
                    "pageSize", str(DEFAULT_RECENT_PAGE_SIZE)
                )
                or DEFAULT_RECENT_PAGE_SIZE
            )
        except (ValueError, TypeError):
            requested = DEFAULT_RECENT_PAGE_SIZE
        page_size = max(1, min(requested, MAX_RECENT_PAGE_SIZE))

        cursor_str = app.current_event.get_query_string_value("cursor", None)
        start_key = _cursor_to_start_key(parse_cursor(cursor_str))

        results = []
        last_row = None  # last row APPENDED to results (cursor anchor)

        # Over-fetch from GSI4 (per-user partition, ordered by recency) and
        # filter until the page is full.
        while len(results) < page_size:
            query_kwargs = dict(
                IndexName="GSI4",
                KeyConditionExpression=Key("gsi4Pk").eq(f"USER#{user_id}"),
                ScanIndexForward=True,  # reverse-ts asc == most-recent first
                Limit=page_size * 3,  # headroom for filtering
            )
            if start_key:
                query_kwargs["ExclusiveStartKey"] = start_key

            resp = _user_table.query(**query_kwargs)

            for row in resp["Items"]:
                collection = _get_collection_metadata(row["collectionId"])
                if not collection or collection.get("status") == "DELETED":
                    continue
                role = get_user_collection_role(collection, user_id)
                if role not in ("OWNER", "EDITOR", "ADMIN"):
                    continue
                results.append(format_collection_item(collection, user_context))
                last_row = row  # anchor on the row we actually returned
                if len(results) == page_size:
                    break

            # Advance the scan WITHIN this request only; this batch boundary is NOT the cursor.
            start_key = resp.get("LastEvaluatedKey")
            if len(results) == page_size or not start_key:
                break

        # Cursor is derived from the GSI4 key of the LAST ROW APPENDED to results
        # (userId + itemKey + gsi4Pk + gsi4Sk), never from the over-fetch batch
        # LastEvaluatedKey.
        next_cursor = (
            create_cursor(
                pk=last_row["userId"],
                sk=last_row["itemKey"],
                gsi_pk=last_row["gsi4Pk"],
                gsi_sk=last_row["gsi4Sk"],
            )
            if len(results) == page_size and last_row is not None
            else None
        )

        return create_success_response(
            data=results,
            pagination={
                "pageSize": page_size,
                "nextCursor": next_cursor,
                "hasNextPage": bool(next_cursor),
            },
            request_id=app.current_event.request_context.request_id,
        )
