"""
Collections Routes.

Handles endpoints for listing and creating collections:
- GET /collections - List collections with filtering
- POST /collections - Create a new collection
- GET /collections/shared-with-me - Get shared collections
"""

import json
import os

# Import from common libraries (these are already in the layer/path)
import sys
import uuid
from datetime import datetime

from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.metrics import MetricUnit
from botocore.exceptions import ClientError

sys.path.insert(0, "/opt/python")  # Lambda layer path
from collections_utils import (
    CHILD_SK_PREFIX,
    COLLECTION_PK_PREFIX,
    COLLECTIONS_GSI5_PK,
    METADATA_SK,
    USER_PK_PREFIX,
    apply_field_selection,
    apply_sorting,
    create_cursor,
    create_error_response,
    create_success_response,
    format_collection_item,
    parse_cursor,
)
from user_auth import extract_user_context

# Initialize PowerTools
logger = Logger(service="collections-routes", level=os.environ.get("LOG_LEVEL", "INFO"))
tracer = Tracer(service="collections-routes")
metrics = Metrics(namespace="medialake", service="collections")

# Constants
DEFAULT_LIMIT = 20
MAX_LIMIT = 100
MAX_NAME_LENGTH = 200
MAX_DESCRIPTION_LENGTH = 1000


def register_routes(app, dynamodb, table_name):
    """
    Register collections routes with the app resolver.

    Args:
        app: APIGatewayRestResolver instance
        dynamodb: DynamoDB resource
        table_name: Collections table name
    """

    @app.get("/collections")
    @tracer.capture_method
    def list_collections():
        """Get list of collections with comprehensive filtering and pagination"""
        try:
            # Extract user context
            user_context = extract_user_context(app.current_event.raw_event)
            user_id = user_context.get("user_id")

            # Parse query parameters
            cursor = app.current_event.get_query_string_value("cursor")
            limit = int(
                app.current_event.get_query_string_value("limit", DEFAULT_LIMIT)
            )

            # Filters
            type_filter = app.current_event.get_query_string_value("filter[type]")
            owner_filter = app.current_event.get_query_string_value("filter[ownerId]")
            parent_filter = app.current_event.get_query_string_value("filter[parentId]")
            status_filter = app.current_event.get_query_string_value("filter[status]")
            search_filter = app.current_event.get_query_string_value("filter[search]")

            # Other params
            sort_param = app.current_event.get_query_string_value("sort")
            fields_param = app.current_event.get_query_string_value("fields")

            # Validate limit
            limit = min(max(1, limit), MAX_LIMIT)

            logger.info(
                "Listing collections", extra={"user_id": user_id, "limit": limit}
            )

            table = dynamodb.Table(table_name)

            # Parse cursor for pagination
            start_key = None
            parsed_cursor = parse_cursor(cursor)
            if parsed_cursor:
                start_key = {
                    "PK": parsed_cursor.get("pk"),
                    "SK": parsed_cursor.get("sk"),
                }
                if parsed_cursor.get("gsi_pk"):
                    start_key["GSI1_PK"] = parsed_cursor.get("gsi_pk")
                if parsed_cursor.get("gsi_sk"):
                    start_key["GSI1_SK"] = parsed_cursor.get("gsi_sk")

            # Determine query strategy based on filters
            if parent_filter:
                response = _query_child_collections(
                    table, parent_filter, limit, start_key
                )
            elif owner_filter:
                response = _query_collections_by_owner(
                    table, owner_filter, limit, start_key
                )
            elif type_filter:
                response = _query_collections_by_type(
                    table, type_filter, limit, start_key
                )
            else:
                response = _query_all_collections(table, limit, start_key)

            items = response.get("Items", [])
            has_more = len(items) > limit
            if has_more:
                items = items[:limit]

            # Apply post-query filters
            if status_filter or search_filter:
                items = _apply_post_filters(items, status_filter, search_filter)

            # Format items
            formatted_items = [
                format_collection_item(item, user_context) for item in items
            ]

            # Apply field selection
            if fields_param:
                formatted_items = [
                    apply_field_selection(item, fields_param)
                    for item in formatted_items
                ]

            # Apply sorting
            sorted_items = apply_sorting(formatted_items, sort_param)

            # Create pagination
            pagination = {
                "has_next_page": has_more,
                "has_prev_page": cursor is not None,
                "limit": limit,
            }

            if has_more and items:
                last_item = items[-1]
                gsi_pk = None
                gsi_sk = None

                if owner_filter:
                    gsi_pk = f"{USER_PK_PREFIX}{owner_filter}"
                    gsi_sk = last_item.get("lastAccessed", last_item.get("updatedAt"))
                elif type_filter:
                    gsi_pk = type_filter
                    gsi_sk = last_item["SK"]

                next_cursor = create_cursor(
                    last_item["PK"], last_item["SK"], gsi_pk, gsi_sk
                )
                pagination["next_cursor"] = next_cursor

            # Log metrics
            metrics.add_metric(
                name="SuccessfulCollectionRetrievals", unit=MetricUnit.Count, value=1
            )
            metrics.add_metric(
                name="CollectionsReturned",
                unit=MetricUnit.Count,
                value=len(sorted_items),
            )

            return create_success_response(
                data=sorted_items,
                pagination=pagination,
                request_id=app.current_event.request_context.request_id,
            )

        except ClientError as e:
            logger.error("DynamoDB error", exc_info=e)
            metrics.add_metric(
                name="FailedCollectionRetrievals", unit=MetricUnit.Count, value=1
            )
            return create_error_response(
                error_code=e.response["Error"]["Code"],
                error_message=e.response["Error"]["Message"],
                status_code=500,
                request_id=app.current_event.request_context.request_id,
            )

        except Exception as e:
            logger.exception("Unexpected error", exc_info=e)
            metrics.add_metric(name="UnexpectedErrors", unit=MetricUnit.Count, value=1)
            return create_error_response(
                error_code="InternalServerError",
                error_message="An unexpected error occurred",
                status_code=500,
                request_id=app.current_event.request_context.request_id,
            )

    @app.post("/collections")
    @tracer.capture_method
    def create_collection():
        """Create a new collection"""
        try:
            # Extract user context
            user_context = extract_user_context(app.current_event.raw_event)
            user_id = user_context.get("user_id")

            if not user_id:
                return create_error_response(
                    error_code="AUTHENTICATION_REQUIRED",
                    error_message="Valid authentication is required to create collections",
                    status_code=401,
                    request_id=app.current_event.request_context.request_id,
                )

            request_data = app.current_event.json_body

            # Validate request
            validation_errors = _validate_collection_data(request_data)
            if validation_errors:
                metrics.add_metric(
                    name="ValidationErrors", unit=MetricUnit.Count, value=1
                )
                return create_error_response(
                    error_code="VALIDATION_ERROR",
                    error_message="The request could not be processed due to validation errors",
                    status_code=422,
                    request_id=app.current_event.request_context.request_id,
                )

            dynamodb.Table(table_name)

            # Generate ID and timestamp
            collection_id = f"col_{str(uuid.uuid4())[:8]}"
            current_timestamp = datetime.utcnow().isoformat() + "Z"

            # Build collection item
            collection_item = {
                "PK": f"{COLLECTION_PK_PREFIX}{collection_id}",
                "SK": METADATA_SK,
                "name": request_data["name"],
                "ownerId": user_id,
                "status": "ACTIVE",
                "itemCount": 0,
                "childCollectionCount": 0,
                "isPublic": bool(request_data.get("isPublic", False)),
                "createdAt": current_timestamp,
                "updatedAt": current_timestamp,
                "GSI5_PK": COLLECTIONS_GSI5_PK,
                "GSI5_SK": current_timestamp,
            }

            # Add optional fields
            if request_data.get("description"):
                collection_item["description"] = request_data["description"]
            if request_data.get("collectionTypeId"):
                collection_item["collectionTypeId"] = request_data["collectionTypeId"]
                collection_item["GSI3_PK"] = request_data["collectionTypeId"]
                collection_item["GSI3_SK"] = f"{COLLECTION_PK_PREFIX}{collection_id}"
            if request_data.get("parentId"):
                collection_item["parentId"] = request_data["parentId"]
            if request_data.get("metadata"):
                collection_item["customMetadata"] = request_data["metadata"]
            if request_data.get("tags"):
                collection_item["tags"] = request_data["tags"]

            # User relationship item
            user_relationship_item = {
                "PK": f"{USER_PK_PREFIX}{user_id}",
                "SK": f"{COLLECTION_PK_PREFIX}{collection_id}",
                "relationship": "OWNER",
                "addedAt": current_timestamp,
                "lastAccessed": current_timestamp,
                "isFavorite": False,
                "GSI1_PK": f"{USER_PK_PREFIX}{user_id}",
                "GSI1_SK": current_timestamp,
            }

            # Prepare transactional write
            transact_items = [
                {"Put": {"TableName": table_name, "Item": collection_item}},
                {"Put": {"TableName": table_name, "Item": user_relationship_item}},
            ]

            # Execute transaction
            dynamodb.meta.client.transact_write_items(TransactItems=transact_items)

            logger.info(f"Collection created: {collection_id}")
            metrics.add_metric(
                name="SuccessfulCollectionCreations", unit=MetricUnit.Count, value=1
            )

            # Format response
            response_data = format_collection_item(collection_item, user_context)

            return {
                "statusCode": 201,
                "body": json.dumps(
                    {
                        "success": True,
                        "data": response_data,
                        "meta": {
                            "timestamp": datetime.utcnow().isoformat() + "Z",
                            "version": "v1",
                            "request_id": app.current_event.request_context.request_id,
                        },
                    }
                ),
            }

        except ClientError as e:
            logger.error("DynamoDB error", exc_info=e)
            metrics.add_metric(
                name="FailedCollectionCreations", unit=MetricUnit.Count, value=1
            )
            return create_error_response(
                error_code=e.response["Error"]["Code"],
                error_message=e.response["Error"]["Message"],
                status_code=500,
                request_id=app.current_event.request_context.request_id,
            )

        except Exception as e:
            logger.exception("Unexpected error", exc_info=e)
            metrics.add_metric(name="UnexpectedErrors", unit=MetricUnit.Count, value=1)
            return create_error_response(
                error_code="InternalServerError",
                error_message="An unexpected error occurred",
                status_code=500,
                request_id=app.current_event.request_context.request_id,
            )

    @app.get("/collections/shared-with-me")
    @tracer.capture_method
    def list_shared_collections():
        """Get collections shared with the current user"""
        try:
            user_context = extract_user_context(app.current_event.raw_event)
            user_id = user_context.get("user_id")

            if not user_id:
                return create_error_response(
                    error_code="AUTHENTICATION_REQUIRED",
                    error_message="Authentication required",
                    status_code=401,
                    request_id=app.current_event.request_context.request_id,
                )

            table = dynamodb.Table(table_name)

            # Query user's shared collections
            response = table.query(
                IndexName="UserCollectionsGSI",
                KeyConditionExpression="GSI1_PK = :user_pk",
                FilterExpression="relationship <> :owner",
                ExpressionAttributeValues={
                    ":user_pk": f"{USER_PK_PREFIX}{user_id}",
                    ":owner": "OWNER",
                },
            )

            items = response.get("Items", [])
            formatted_items = [
                format_collection_item(item, user_context) for item in items
            ]

            return create_success_response(
                data=formatted_items,
                request_id=app.current_event.request_context.request_id,
            )

        except Exception as e:
            logger.exception("Error listing shared collections", exc_info=e)
            return create_error_response(
                error_code="InternalServerError",
                error_message="An unexpected error occurred",
                status_code=500,
                request_id=app.current_event.request_context.request_id,
            )


# Helper functions
@tracer.capture_method
def _query_collections_by_owner(table, user_id, limit, start_key):
    """Query collections by owner using GSI1"""
    query_params = {
        "IndexName": "UserCollectionsGSI",
        "KeyConditionExpression": "GSI1_PK = :gsi1_pk AND begins_with(GSI1_SK, :sk_prefix)",
        "ExpressionAttributeValues": {
            ":gsi1_pk": f"{USER_PK_PREFIX}{user_id}",
            ":sk_prefix": COLLECTION_PK_PREFIX,
        },
        "Limit": limit + 1,
    }
    if start_key:
        query_params["ExclusiveStartKey"] = start_key
    return table.query(**query_params)


@tracer.capture_method
def _query_all_collections(table, limit, start_key):
    """Query all collections using GSI5"""
    query_params = {
        "IndexName": "RecentlyModifiedGSI",
        "KeyConditionExpression": "GSI5_PK = :gsi5_pk",
        "ExpressionAttributeValues": {":gsi5_pk": COLLECTIONS_GSI5_PK},
        "ScanIndexForward": False,
        "Limit": limit + 1,
    }
    if start_key:
        query_params["ExclusiveStartKey"] = start_key
    return table.query(**query_params)


@tracer.capture_method
def _query_collections_by_type(table, collection_type_id, limit, start_key):
    """Query collections by type using GSI3"""
    query_params = {
        "IndexName": "CollectionTypeGSI",
        "KeyConditionExpression": "GSI3_PK = :gsi3_pk",
        "ExpressionAttributeValues": {":gsi3_pk": collection_type_id},
        "Limit": limit + 1,
    }
    if start_key:
        query_params["ExclusiveStartKey"] = start_key
    return table.query(**query_params)


@tracer.capture_method
def _query_child_collections(table, parent_id, limit, start_key):
    """Query child collections by parent ID"""
    query_params = {
        "KeyConditionExpression": "PK = :pk AND begins_with(SK, :sk_prefix)",
        "ExpressionAttributeValues": {
            ":pk": f"{COLLECTION_PK_PREFIX}{parent_id}",
            ":sk_prefix": CHILD_SK_PREFIX,
        },
        "Limit": limit + 1,
    }
    if start_key:
        query_params["ExclusiveStartKey"] = start_key

    response = table.query(**query_params)

    # Get full collection data for each child
    child_items = []
    for child_ref in response.get("Items", []):
        child_id = child_ref.get("childCollectionId")
        if child_id:
            try:
                child_response = table.get_item(
                    Key={"PK": f"{COLLECTION_PK_PREFIX}{child_id}", "SK": METADATA_SK}
                )
                if "Item" in child_response:
                    child_items.append(child_response["Item"])
            except Exception as e:
                logger.warning(f"Failed to get child collection {child_id}: {e}")

    return {"Items": child_items, "LastEvaluatedKey": response.get("LastEvaluatedKey")}


@tracer.capture_method
def _apply_post_filters(items, status_filter, search_filter):
    """Apply post-query filters"""
    filtered_items = []
    for item in items:
        if status_filter and item.get("status") != status_filter:
            continue
        if search_filter:
            search_term = search_filter.lower()
            name_match = search_term in item.get("name", "").lower()
            desc_match = search_term in item.get("description", "").lower()
            if not (name_match or desc_match):
                continue
        filtered_items.append(item)
    return filtered_items


@tracer.capture_method
def _validate_collection_data(request_data):
    """Validate collection creation request data"""
    errors = []
    if not request_data.get("name"):
        errors.append(
            {
                "field": "name",
                "message": "Collection name is required",
                "code": "REQUIRED_FIELD",
            }
        )
    elif len(request_data["name"]) > MAX_NAME_LENGTH:
        errors.append(
            {
                "field": "name",
                "message": f"Name must be {MAX_NAME_LENGTH} characters or less",
                "code": "INVALID_LENGTH",
            }
        )
    return errors
