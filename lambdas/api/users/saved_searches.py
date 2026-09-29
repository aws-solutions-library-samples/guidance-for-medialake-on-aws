"""Per-user saved searches.

Routes:
    GET    /users/saved-searches              -> list, most recently updated first
    POST   /users/saved-searches              -> create {name, definition}
    PATCH  /users/saved-searches/{searchId}   -> update {name?, definition?}
    DELETE /users/saved-searches/{searchId}   -> delete

Storage: one row per saved search in the users table,
``userId=USER#{sub}, itemKey=SAVEDSEARCH#{searchId}``, so renaming or deleting
one never rewrites the others. Saving a search whose fingerprint matches an
existing saved search returns that one instead of creating a duplicate.

A saved search stores the *definition*, never results: running it is an
ordinary search, so permissions and personal-asset isolation are evaluated
again every time.
"""

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from auth_utils import get_authenticated_user_id
from aws_lambda_powertools.metrics import MetricUnit
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError
from response_utils import error_response, success_response
from search_definition import SearchDefinitionError, parse_definition

MAX_SAVED_SEARCHES = 50
MAX_NAME_LENGTH = 100
ITEM_PREFIX = "SAVEDSEARCH#"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _pk(user_id: str) -> str:
    return f"USER#{user_id}"


def _to_api(item: Dict[str, Any]) -> Dict[str, Any]:
    try:
        definition = json.loads(item.get("definitionJson") or "{}")
    except (TypeError, ValueError):
        definition = {}
    return {
        "id": item["searchId"],
        "name": item.get("name", ""),
        "definition": definition,
        "fingerprint": item.get("fingerprint", ""),
        "createdAt": item.get("createdAt"),
        "updatedAt": item.get("updatedAt"),
    }


def _list(table, user_id: str) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    kwargs: Dict[str, Any] = {
        "KeyConditionExpression": Key("userId").eq(_pk(user_id))
        & Key("itemKey").begins_with(ITEM_PREFIX),
        "ConsistentRead": True,
    }
    while True:
        response = table.query(**kwargs)
        items.extend(response.get("Items", []))
        if "LastEvaluatedKey" not in response:
            break
        kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]
    saved = [_to_api(i) for i in items if i.get("searchId")]
    return sorted(saved, key=lambda s: s.get("updatedAt") or "", reverse=True)


def _validate_name(raw: Any) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
    if not isinstance(raw, str) or not raw.strip():
        return None, error_response(400, "name is required")
    name = " ".join(raw.split())
    if len(name) > MAX_NAME_LENGTH:
        return None, error_response(
            400, f"name must be at most {MAX_NAME_LENGTH} characters"
        )
    return name, None


def _user_or_error(app, user_table_name, logger, metrics):
    user_id = get_authenticated_user_id(app, logger)
    if not user_id:
        metrics.add_metric(name="MissingUserIdError", unit=MetricUnit.Count, value=1)
        return None, error_response(400, "Unable to identify user")
    if not user_table_name:
        logger.error("USER_TABLE_NAME environment variable not set")
        return None, error_response(500, "Internal configuration error")
    return user_id, None


def _json_body(app):
    try:
        body = app.current_event.json_body
    except Exception:
        return None, error_response(400, "Invalid request body format")
    if not isinstance(body, dict):
        return None, error_response(400, "Request body must be a JSON object")
    return body, None


def handle_get_saved_searches(app, dynamodb, user_table_name, logger, metrics, tracer):
    try:
        user_id, error = _user_or_error(app, user_table_name, logger, metrics)
        if error:
            return error
        saved = _list(dynamodb.Table(user_table_name), user_id)
        return success_response(
            200,
            "Saved searches retrieved",
            {"items": saved, "count": len(saved), "limit": MAX_SAVED_SEARCHES},
        )
    except Exception:
        logger.exception("Error retrieving saved searches")
        metrics.add_metric(name="UnhandledError", unit=MetricUnit.Count, value=1)
        return error_response(500, "Internal server error")


def handle_create_saved_search(app, dynamodb, user_table_name, logger, metrics, tracer):
    try:
        user_id, error = _user_or_error(app, user_table_name, logger, metrics)
        if error:
            return error
        body, error = _json_body(app)
        if error:
            return error

        name, error = _validate_name(body.get("name"))
        if error:
            return error
        if "definition" not in body:
            return error_response(400, "definition is required")
        try:
            definition, fp = parse_definition(body["definition"])
        except SearchDefinitionError as e:
            return error_response(400, str(e))

        table = dynamodb.Table(user_table_name)
        existing = _list(table, user_id)
        duplicate = next((s for s in existing if s["fingerprint"] == fp), None)
        if duplicate:
            return success_response(
                200, "This search is already saved", {**duplicate, "existing": True}
            )
        if len(existing) >= MAX_SAVED_SEARCHES:
            return error_response(
                409,
                f"You can save at most {MAX_SAVED_SEARCHES} searches. "
                "Delete one to save another.",
            )

        now = _now_iso()
        search_id = str(uuid.uuid4())
        item = {
            "userId": _pk(user_id),
            "itemKey": f"{ITEM_PREFIX}{search_id}",
            "itemType": "SAVED_SEARCH",
            "searchId": search_id,
            "name": name,
            "definitionJson": json.dumps(
                definition, separators=(",", ":"), ensure_ascii=False
            ),
            "fingerprint": fp,
            "createdAt": now,
            "updatedAt": now,
        }
        table.put_item(Item=item, ConditionExpression="attribute_not_exists(itemKey)")
        logger.info(
            "Audit: saved search created",
            extra={
                "user_id": user_id,
                "action": "CREATE_SAVED_SEARCH",
                "id": search_id,
            },
        )
        metrics.add_metric(name="SavedSearchCreated", unit=MetricUnit.Count, value=1)
        return success_response(
            201, "Search saved", {**_to_api(item), "existing": False}
        )
    except Exception:
        logger.exception("Error saving search")
        metrics.add_metric(name="UnhandledError", unit=MetricUnit.Count, value=1)
        return error_response(500, "Internal server error")


def handle_update_saved_search(
    search_id: str, app, dynamodb, user_table_name, logger, metrics, tracer
):
    try:
        user_id, error = _user_or_error(app, user_table_name, logger, metrics)
        if error:
            return error
        body, error = _json_body(app)
        if error:
            return error
        if "name" not in body and "definition" not in body:
            return error_response(400, "Provide a name and/or a definition to update")

        names: Dict[str, str] = {"#u": "updatedAt"}
        values: Dict[str, Any] = {":u": _now_iso()}
        sets = ["#u = :u"]
        if "name" in body:
            name, error = _validate_name(body["name"])
            if error:
                return error
            names["#n"] = "name"
            values[":n"] = name
            sets.append("#n = :n")
        if "definition" in body:
            try:
                definition, fp = parse_definition(body["definition"])
            except SearchDefinitionError as e:
                return error_response(400, str(e))
            names["#d"] = "definitionJson"
            names["#f"] = "fingerprint"
            values[":d"] = json.dumps(
                definition, separators=(",", ":"), ensure_ascii=False
            )
            values[":f"] = fp
            sets += ["#d = :d", "#f = :f"]

        table = dynamodb.Table(user_table_name)
        try:
            response = table.update_item(
                Key={"userId": _pk(user_id), "itemKey": f"{ITEM_PREFIX}{search_id}"},
                UpdateExpression="SET " + ", ".join(sets),
                ConditionExpression="attribute_exists(itemKey)",
                ExpressionAttributeNames=names,
                ExpressionAttributeValues=values,
                ReturnValues="ALL_NEW",
            )
        except ClientError as e:
            if (
                e.response.get("Error", {}).get("Code")
                == "ConditionalCheckFailedException"
            ):
                return error_response(404, "Saved search not found")
            raise
        return success_response(
            200, "Saved search updated", _to_api(response["Attributes"])
        )
    except Exception:
        logger.exception("Error updating saved search")
        metrics.add_metric(name="UnhandledError", unit=MetricUnit.Count, value=1)
        return error_response(500, "Internal server error")


def handle_delete_saved_search(
    search_id: str, app, dynamodb, user_table_name, logger, metrics, tracer
):
    try:
        user_id, error = _user_or_error(app, user_table_name, logger, metrics)
        if error:
            return error
        table = dynamodb.Table(user_table_name)
        try:
            table.delete_item(
                Key={"userId": _pk(user_id), "itemKey": f"{ITEM_PREFIX}{search_id}"},
                ConditionExpression="attribute_exists(itemKey)",
            )
        except ClientError as e:
            if (
                e.response.get("Error", {}).get("Code")
                == "ConditionalCheckFailedException"
            ):
                return error_response(404, "Saved search not found")
            raise
        logger.info(
            "Audit: saved search deleted",
            extra={
                "user_id": user_id,
                "action": "DELETE_SAVED_SEARCH",
                "id": search_id,
            },
        )
        return success_response(200, "Saved search deleted", {"id": search_id})
    except Exception:
        logger.exception("Error deleting saved search")
        metrics.add_metric(name="UnhandledError", unit=MetricUnit.Count, value=1)
        return error_response(500, "Internal server error")
