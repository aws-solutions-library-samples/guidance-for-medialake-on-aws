"""List pipeline executions, newest first, without scanning the table.

The base table is keyed by ``execution_id``, so it offers no way to read
executions in time order. This endpoint used to Scan the whole table with no
limit, materialize every row, sort it in Python and slice out one page — which
timed out as soon as a deployment accumulated a meaningful number of executions.

Reads now go through ``StatusStartTimeIndex`` (partition ``status``, sort
``start_time``):

  * A status filter is a single-partition Query.
  * Listing every status is a k-way merge across the status partitions. Each
    partition is already ordered by ``start_time``, so merging their heads yields
    a globally ordered stream while reading only about one page per partition.
  * ``startDate`` / ``endDate`` become a sort-key range condition. The previous
    implementation accepted both parameters from the UI and silently ignored
    them.
  * ``search`` filters the merged stream with a bounded read-ahead budget, so an
    unmatched term costs a capped number of queries instead of a full scan.

Only ``start_time`` can be ordered server-side, because it is the index's sort
key. Other ``sortBy`` values return start_time order and are sorted client-side
over the loaded rows by the table component. Ordering by an unindexed column
across the whole table is precisely the full-table read this change removes.

``totalResults`` reports the size of the returned page. A true total requires
counting every matching item, which is the other half of the original timeout;
the executions UI does not read the field.
"""

import base64
import json
import os
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.event_handler import APIGatewayRestResolver
from aws_lambda_powertools.event_handler.api_gateway import CORSConfig
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.utilities.data_classes import APIGatewayProxyEvent
from aws_lambda_powertools.utilities.typing import LambdaContext
from boto3.dynamodb.conditions import Key

logger = Logger()
tracer = Tracer()
metrics = Metrics(namespace="Pipelines")

cors_config = CORSConfig(
    allow_origin="*",
    allow_headers=[
        "Content-Type",
        "X-Amz-Date",
        "Authorization",
        "X-Api-Key",
        "X-Amz-Security-Token",
    ],
)

app = APIGatewayRestResolver(
    serializer=lambda x: json.dumps(x, default=str),
    strip_prefixes=["/api"],
    cors=cors_config,
)

DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 100

INDEX_NAME = "StatusStartTimeIndex"

# AWS's Step Functions ExecutionStatus enum. The event processor copies
# ``detail["status"]`` straight from the EventBridge event, so these are the only
# values the attribute can hold — and because status is the index partition key,
# this tuple is what "list every execution" has to fan out across. A status
# outside this set would be invisible to the unfiltered list, so it is pinned
# here rather than discovered per request (discovery would require a scan).
EXECUTION_STATUSES: Tuple[str, ...] = (
    "RUNNING",
    "SUCCEEDED",
    "FAILED",
    "TIMED_OUT",
    "ABORTED",
    "PENDING_REDRIVE",
)

# Read-ahead ceiling for one request, counted in Query calls across all status
# partitions. Without a filter a page needs about one query per status; a
# `search` that matches nothing would otherwise walk the entire index, which is
# the unbounded behaviour this module exists to remove.
MAX_QUERIES_PER_REQUEST = 60

# Fields the free-text `search` parameter matches against.
SEARCHABLE_FIELDS = (
    "pipeline_name",
    "status",
    "execution_id",
    "dsa_type",
    "object_key_name",
    "pipeline_trace_id",
    "stepname",
    "stepresult",
    "stepstatus",
)

TOKEN_VERSION = 2

_TABLE = None


class PipelineExecutionError(Exception):
    """Raised when the executions list cannot be served."""


def _resolve_table_name(raw: str) -> str:
    """Accept either a table name or a full table ARN.

    The stack currently passes ``table_arn`` into the table-name environment
    variable. DynamoDB tolerates an ARN wherever a table name is expected, so
    this works either way, but normalizing keeps the value usable for logging
    and for callers that build index names from it.
    """
    value = (raw or "").strip()
    if value.startswith("arn:") and ":table/" in value:
        # arn:aws:dynamodb:<region>:<account>:table/<name>[/index/<index>]
        return value.split(":table/", 1)[1].split("/")[0]
    return value


def _table():
    global _TABLE
    if _TABLE is None:
        name = _resolve_table_name(os.environ["PIPELINES_EXECUTIONS_TABLE_NAME"])
        if not name:
            raise PipelineExecutionError(
                "PIPELINES_EXECUTIONS_TABLE_NAME is empty; cannot read executions"
            )
        _TABLE = boto3.resource("dynamodb").Table(name)
    return _TABLE


def _reset_table_cache() -> None:
    """Drop the cached table handle. Used by tests."""
    global _TABLE
    _TABLE = None


# ─────────────────────────────────────────────────────────────────────────────
# Pagination token
# ─────────────────────────────────────────────────────────────────────────────
#
# The token carries one cursor per status partition: the index + table key of
# the last item this endpoint *emitted* from that partition.
#
# It deliberately does not store DynamoDB's LastEvaluatedKey. A merge reads
# ahead, so a partition can hold fetched-but-unemitted items; resuming from
# LastEvaluatedKey would skip them. Resuming from the last emitted item re-reads
# that small remainder instead, which is correct at the cost of a few RCUs.


def _encode_token(cursors: Dict[str, Dict[str, Any]], sort_order: str) -> Optional[str]:
    if not cursors:
        return None
    payload = {
        "v": TOKEN_VERSION,
        "sort_order": sort_order,
        "cursors": cursors,
    }
    return base64.b64encode(json.dumps(payload).encode()).decode()


def _decode_token(token: Optional[str], sort_order: str) -> Dict[str, Dict[str, Any]]:
    """Return per-status cursors, or empty when the token is absent or unusable.

    A token from a different sort direction, or from the pre-index format, is
    discarded rather than misapplied — restarting the list is recoverable,
    resuming at a position that means something else is not.
    """
    if not token:
        return {}
    try:
        payload = json.loads(base64.b64decode(token.encode()).decode())
    except Exception:
        logger.warning("Discarding unreadable pagination token")
        return {}

    if not isinstance(payload, dict) or payload.get("v") != TOKEN_VERSION:
        logger.info("Discarding pagination token from an older format")
        return {}

    if payload.get("sort_order") != sort_order:
        logger.info(
            "Sort order changed since the token was issued; restarting pagination"
        )
        return {}

    cursors = payload.get("cursors")
    if not isinstance(cursors, dict):
        return {}

    cleaned: Dict[str, Dict[str, Any]] = {}
    for status, key in cursors.items():
        if status not in EXECUTION_STATUSES or not isinstance(key, dict):
            continue
        try:
            cleaned[status] = {
                "status": str(key["status"]),
                "start_time": int(key["start_time"]),
                "execution_id": str(key["execution_id"]),
            }
        except (KeyError, TypeError, ValueError):
            logger.warning("Dropping malformed cursor for status %s", status)
    return cleaned


def _key_of(item: Dict[str, Any]) -> Dict[str, Any]:
    """The index + base-table key identifying an item, for use as a cursor."""
    return {
        "status": str(item["status"]),
        "start_time": int(item["start_time"]),
        "execution_id": str(item["execution_id"]),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Per-status cursor stream
# ─────────────────────────────────────────────────────────────────────────────


class _StatusStream:
    """One status partition, read lazily in pages and filtered in place."""

    def __init__(
        self,
        status: str,
        *,
        ascending: bool,
        key_condition_extra: Optional[Any],
        search: Optional[str],
        chunk_size: int,
        start_cursor: Optional[Dict[str, Any]],
        budget: "_QueryBudget",
    ) -> None:
        self.status = status
        self._ascending = ascending
        self._key_condition_extra = key_condition_extra
        self._search = search
        self._chunk_size = chunk_size
        self._budget = budget
        self._buffer: List[Dict[str, Any]] = []
        self._next_start_key: Optional[Dict[str, Any]] = (
            dict(start_cursor) if start_cursor else None
        )
        self._exhausted = False
        # Where the next page should resume: the last item handed out, or the
        # incoming cursor while nothing has been emitted yet.
        self.resume_cursor: Optional[Dict[str, Any]] = (
            dict(start_cursor) if start_cursor else None
        )

    def _key_condition(self):
        condition = Key("status").eq(self.status)
        if self._key_condition_extra is not None:
            condition = condition & self._key_condition_extra
        return condition

    def _fetch(self) -> None:
        """Pull one page into the buffer, applying the search filter."""
        while not self._exhausted and not self._buffer:
            if not self._budget.consume():
                # Out of read-ahead. Treat as exhausted for this request; the
                # caller still returns a token so the client can continue.
                self._exhausted = True
                return

            kwargs: Dict[str, Any] = {
                "IndexName": INDEX_NAME,
                "KeyConditionExpression": self._key_condition(),
                "ScanIndexForward": self._ascending,
                "Limit": self._chunk_size,
            }
            if self._next_start_key:
                kwargs["ExclusiveStartKey"] = self._next_start_key

            response = _table().query(**kwargs)
            items = response.get("Items", []) or []
            self._next_start_key = response.get("LastEvaluatedKey")
            if not self._next_start_key:
                self._exhausted = True

            if self._search:
                items = [i for i in items if _matches_search(i, self._search)]
            self._buffer.extend(items)

    def head(self) -> Optional[Dict[str, Any]]:
        self._fetch()
        return self._buffer[0] if self._buffer else None

    def pop(self) -> Dict[str, Any]:
        item = self._buffer.pop(0)
        self.resume_cursor = _key_of(item)
        return item

    def has_pending(self) -> bool:
        return bool(self._buffer) or not self._exhausted


class _QueryBudget:
    """Caps the Query calls a single request may issue."""

    def __init__(self, limit: int) -> None:
        self._remaining = limit
        self.used = 0

    def consume(self) -> bool:
        if self._remaining <= 0:
            return False
        self._remaining -= 1
        self.used += 1
        return True

    @property
    def exhausted(self) -> bool:
        return self._remaining <= 0


def _matches_search(item: Dict[str, Any], term: str) -> bool:
    lowered = term.lower()
    for field in SEARCHABLE_FIELDS:
        value = item.get(field)
        if value is None:
            continue
        if lowered in str(value).lower():
            return True
    return False


def _sort_value(item: Dict[str, Any]) -> Tuple[int, str]:
    """Total order within a partition: start_time, then execution_id for ties."""
    try:
        start = int(item.get("start_time") or 0)
    except (TypeError, ValueError):
        start = 0
    return (start, str(item.get("execution_id") or ""))


def _build_range_condition(
    start_ts: Optional[int], end_ts: Optional[int]
) -> Optional[Any]:
    if start_ts is not None and end_ts is not None:
        return Key("start_time").between(start_ts, end_ts)
    if start_ts is not None:
        return Key("start_time").gte(start_ts)
    if end_ts is not None:
        return Key("start_time").lte(end_ts)
    return None


def _parse_epoch(raw: Optional[str], *, label: str) -> Optional[int]:
    """Parse a date filter into a unix timestamp.

    Accepts epoch seconds, epoch milliseconds, or an ISO-8601 date/datetime,
    because the UI has sent this value through without the backend ever reading
    it and no single format was established.
    """
    if raw is None or raw == "":
        return None

    text = str(raw).strip()
    if text.isdigit():
        value = int(text)
        # Anything this large is milliseconds; start_time is stored in seconds.
        return value // 1000 if value > 10_000_000_000 else value

    normalized = text.replace("Z", "+00:00")
    for parse in (
        lambda s: datetime.fromisoformat(s),
        lambda s: datetime.strptime(s, "%Y-%m-%d"),
    ):
        try:
            parsed = parse(normalized)
        except ValueError:
            continue
        if parsed.tzinfo is None:
            # A bare date or datetime is treated as UTC rather than as the
            # host's local time. Lambda runs in UTC so both agree in
            # production, but leaving it implicit makes the same query return
            # different windows depending on where it executes.
            parsed = parsed.replace(tzinfo=timezone.utc)
        return int(parsed.timestamp())

    logger.warning("Ignoring unparseable %s filter: %r", label, raw)
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Response shaping
# ─────────────────────────────────────────────────────────────────────────────


def _stringify(value: Any) -> str:
    if isinstance(value, Decimal):
        # Numbers are stored as integers (epoch seconds, durations); avoid the
        # trailing ".0" that str(Decimal) would produce for whole values.
        return str(int(value)) if value == value.to_integral_value() else str(value)
    return str(value)


@tracer.capture_method
def format_execution_response(item: Dict[str, Any]) -> Dict[str, Any]:
    """Shape one DynamoDB item into the API's execution object.

    Numeric fields are emitted as strings, matching what the previous PynamoDB
    implementation produced, so the frontend contract is unchanged.
    """
    response: Dict[str, Any] = {
        "execution_id": item.get("execution_id"),
        "start_time": _stringify(item.get("start_time")),
        "start_time_iso": item.get("start_time_iso"),
        "pipeline_name": item.get("pipeline_name"),
        "status": item.get("status"),
        "state_machine_arn": item.get("state_machine_arn"),
        "execution_arn": item.get("execution_arn"),
        "last_updated": item.get("last_updated"),
        "ttl": _stringify(item.get("ttl")) if item.get("ttl") is not None else None,
    }

    if item.get("end_time") is not None:
        response["end_time"] = _stringify(item["end_time"])
    if item.get("end_time_iso") is not None:
        response["end_time_iso"] = item["end_time_iso"]

    # Duration: prefer the stored value, fall back to end - start.
    if item.get("duration_seconds") is not None:
        response["duration_seconds"] = _stringify(item["duration_seconds"])
    elif item.get("end_time") is not None:
        try:
            response["duration_seconds"] = str(
                int(item["end_time"]) - int(item["start_time"])
            )
        except (TypeError, ValueError):
            response["duration_seconds"] = "0"

    for field in (
        "dsa_type",
        "inventory_id",
        "object_key_name",
        "pipeline_trace_id",
        "stepname",
        "stepresult",
        "stepstatus",
    ):
        if item.get(field) is not None:
            response[field] = item[field]

    if item.get("metadata") is not None:
        response["metadata"] = item["metadata"]

    return response


# ─────────────────────────────────────────────────────────────────────────────
# Core read
# ─────────────────────────────────────────────────────────────────────────────


@tracer.capture_method
def get_pipeline_executions(
    page_size: int,
    next_token: str = None,
    status: str = None,
    sort_by: str = "start_time",
    sort_order: str = "desc",
    search: str = None,
    start_date: str = None,
    end_date: str = None,
) -> Dict[str, Any]:
    """Read one page of executions from StatusStartTimeIndex."""
    ascending = str(sort_order or "desc").lower() == "asc"
    normalized_sort_order = "asc" if ascending else "desc"

    if sort_by and sort_by != "start_time":
        # Only the index sort key can be ordered server-side; see module docstring.
        logger.info(
            "sortBy=%s is not server-sortable; returning start_time order",
            sort_by,
        )

    statuses = (status,) if status else EXECUTION_STATUSES
    if status and status not in EXECUTION_STATUSES:
        # Still queried: an unknown value returns an empty partition rather than
        # an error, which is what a stale UI filter should do.
        logger.warning("Querying unrecognized status filter %r", status)

    start_ts = _parse_epoch(start_date, label="startDate")
    end_ts = _parse_epoch(end_date, label="endDate")
    if start_ts is not None and end_ts is not None and start_ts > end_ts:
        logger.warning(
            "startDate (%s) is after endDate (%s); returning no results",
            start_ts,
            end_ts,
        )
        return _envelope([], page_size, None)

    range_condition = _build_range_condition(start_ts, end_ts)
    cursors = _decode_token(next_token, normalized_sort_order)
    budget = _QueryBudget(MAX_QUERIES_PER_REQUEST)

    # Read one page per partition at a time. With a search term the filter can
    # empty a chunk, so ask for a larger slice to reduce round trips.
    chunk_size = page_size if not search else min(MAX_PAGE_SIZE, page_size * 5)

    streams = [
        _StatusStream(
            s,
            ascending=ascending,
            key_condition_extra=range_condition,
            search=search,
            chunk_size=max(1, chunk_size),
            start_cursor=cursors.get(s),
            budget=budget,
        )
        for s in statuses
    ]

    try:
        collected = _merge(streams, page_size, ascending)
    except Exception as exc:
        logger.exception("Failed to read pipeline executions")
        metrics.add_metric(name="FailedQueries", unit="Count", value=1)
        raise PipelineExecutionError(
            f"Failed to retrieve pipeline executions: {exc}"
        ) from exc

    has_more = any(s.has_pending() for s in streams)
    token = (
        _encode_token(
            {s.status: s.resume_cursor for s in streams if s.resume_cursor},
            normalized_sort_order,
        )
        if has_more
        else None
    )

    if budget.exhausted:
        logger.warning(
            "Read-ahead budget of %s queries exhausted (search=%r); returning a "
            "partial page with a continuation token",
            MAX_QUERIES_PER_REQUEST,
            search,
        )

    logger.info(
        "Served %s executions using %s queries (statuses=%s, search=%r)",
        len(collected),
        budget.used,
        len(statuses),
        search,
    )
    metrics.add_metric(name="SuccessfulQueries", unit="Count", value=1)
    metrics.add_metric(name="ExecutionQueryCount", unit="Count", value=budget.used)

    return _envelope(collected, page_size, token)


def _merge(
    streams: List[_StatusStream], page_size: int, ascending: bool
) -> List[Dict[str, Any]]:
    """K-way merge of per-status partitions into one ordered page.

    Each partition is already sorted by start_time in the requested direction,
    so repeatedly taking the best head yields a globally ordered result while
    reading only about one page per partition.
    """
    collected: List[Dict[str, Any]] = []
    while len(collected) < page_size:
        best: Optional[_StatusStream] = None
        best_value: Optional[Tuple[int, str]] = None

        for stream in streams:
            head = stream.head()
            if head is None:
                continue
            value = _sort_value(head)
            if best_value is None:
                best, best_value = stream, value
            elif (value < best_value) if ascending else (value > best_value):
                best, best_value = stream, value

        if best is None:
            break
        collected.append(best.pop())

    return collected


def _envelope(
    items: List[Dict[str, Any]], page_size: int, token: Optional[str]
) -> Dict[str, Any]:
    return {
        "status": "200",
        "message": "ok",
        "data": {
            "searchMetadata": {
                # Size of this page. A true total means counting every match,
                # which is the full-table read this endpoint no longer does.
                "totalResults": len(items),
                "pageSize": page_size,
                "nextToken": token,
            },
            "executions": [format_execution_response(i) for i in items],
        },
    }


@app.get("/pipelines/executions")
@tracer.capture_method
def handle_get_executions() -> Dict[str, Any]:
    """GET /pipelines/executions"""
    try:
        query_string = app.current_event.query_string_parameters or {}

        try:
            page_size = int(query_string.get("pageSize", DEFAULT_PAGE_SIZE))
            page_size = max(1, min(MAX_PAGE_SIZE, page_size))
        except (ValueError, TypeError):
            page_size = DEFAULT_PAGE_SIZE

        return get_pipeline_executions(
            page_size,
            query_string.get("nextToken"),
            query_string.get("status"),
            query_string.get("sortBy", "start_time"),
            query_string.get("sortOrder", "desc"),
            query_string.get("search"),
            query_string.get("startDate"),
            query_string.get("endDate"),
        )
    except PipelineExecutionError as e:
        logger.exception("Error processing pipeline executions request")
        return {
            "status": "500",
            "message": str(e),
            "data": {
                "searchMetadata": {
                    "totalResults": 0,
                    "pageSize": DEFAULT_PAGE_SIZE,
                    "nextToken": None,
                },
                "executions": [],
            },
        }


@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(
    event: APIGatewayProxyEvent, context: LambdaContext
) -> Dict[str, Any]:
    """Main Lambda handler"""
    try:
        return app.resolve(event, context)
    except Exception:
        logger.exception("Error in lambda handler")
        return {
            "statusCode": 500,
            "body": {
                "status": "500",
                "message": "Internal server error",
                "data": {
                    "searchMetadata": {
                        "totalResults": 0,
                        "pageSize": DEFAULT_PAGE_SIZE,
                        "nextToken": None,
                    },
                    "executions": [],
                },
            },
        }
