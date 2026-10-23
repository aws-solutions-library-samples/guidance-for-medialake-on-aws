"""POST /collections/membership - Which of the given assets are in a collection."""

import os

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.event_handler.exceptions import BadRequestError
from aws_lambda_powertools.metrics import MetricUnit
from boto3.dynamodb.conditions import Key
from collections_utils import (
    COLLECTION_PK_PREFIX,
    USER_PK_PREFIX,
    create_error_response,
    create_success_response,
)
from user_auth import extract_user_context
from utils.item_utils import ASSET_SK_PREFIX, generate_asset_sk

logger = Logger(
    service="collections-membership-post", level=os.environ.get("LOG_LEVEL", "INFO")
)
tracer = Tracer(service="collections-membership-post")
metrics = Metrics(namespace="medialake", service="collections")

dynamodb = boto3.resource("dynamodb")
table_name = os.environ.get("COLLECTIONS_TABLE_NAME", "collections_table_dev")
collections_table = dynamodb.Table(table_name)

# One GSI query per asset, so cap the batch to keep a request well inside the API timeout.
MAX_ASSET_IDS = 100


def _user_can_see(user_id: str, collection_id: str, cache: dict) -> bool:
    """True when the user has a relationship row (owner/editor/viewer) for the collection."""
    if collection_id not in cache:
        response = collections_table.get_item(
            Key={
                "PK": f"{USER_PK_PREFIX}{user_id}",
                "SK": f"{COLLECTION_PK_PREFIX}{collection_id}",
            },
            ProjectionExpression="PK",
        )
        cache[collection_id] = "Item" in response
    return cache[collection_id]


def _in_visible_collection(gsi2_pk: str, user_id: str, cache: dict) -> bool:
    """True when any collection holding the item (GSI2_PK) is visible to the user."""
    query_kwargs = {
        "IndexName": "ItemCollectionsGSI",
        "KeyConditionExpression": Key("GSI2_PK").eq(gsi2_pk),
    }
    while True:
        response = collections_table.query(**query_kwargs)
        for item in response.get("Items", []):
            collection_id = item["GSI2_SK"][len(COLLECTION_PK_PREFIX) :]
            if _user_can_see(user_id, collection_id, cache):
                return True
        last_key = response.get("LastEvaluatedKey")
        if not last_key:
            return False
        query_kwargs["ExclusiveStartKey"] = last_key


def register_route(app):
    """Register POST /collections/membership route"""

    @app.post("/collections/membership")
    @tracer.capture_method
    def collections_membership_post():
        """Return the subset of the given asset IDs that are in a collection the user can access."""
        try:
            user_context = extract_user_context(app.current_event.raw_event)
            user_id = user_context.get("user_id")
            if not user_id:
                raise BadRequestError("Authentication required")

            body = app.current_event.json_body or {}
            asset_ids = body.get("assetIds")
            if not isinstance(asset_ids, list) or not all(
                isinstance(a, str) and a for a in asset_ids
            ):
                raise BadRequestError("assetIds must be a list of non-empty strings")
            if len(asset_ids) > MAX_ASSET_IDS:
                raise BadRequestError(
                    f"assetIds may contain at most {MAX_ASSET_IDS} entries"
                )

            visibility_cache: dict = {}
            in_collection = []
            for asset_id in dict.fromkeys(asset_ids):
                # Items are written with GSI2_PK equal to their SK. The API and S3 ingest
                # use the #FULL form; the pipeline collection_manager node writes the bare
                # ASSET#{id} form. Clip adds are a different item and don't count here.
                lookup_keys = (
                    generate_asset_sk(asset_id),
                    f"{ASSET_SK_PREFIX}{asset_id}",
                )
                if any(
                    _in_visible_collection(key, user_id, visibility_cache)
                    for key in lookup_keys
                ):
                    in_collection.append(asset_id)

            metrics.add_metric(name="MembershipChecks", unit=MetricUnit.Count, value=1)
            return create_success_response(
                {"inCollection": in_collection},
                request_id=app.current_event.request_context.request_id,
            )
        except BadRequestError:
            raise
        except Exception as e:
            logger.exception("Error checking collection membership", exc_info=e)
            metrics.add_metric(name="MembershipErrors", unit=MetricUnit.Count, value=1)
            return create_error_response(
                error_code="INTERNAL_SERVER_ERROR",
                error_message="Failed to check collection membership",
                status_code=500,
                request_id=app.current_event.request_context.request_id,
            )
