import json
import os
from typing import Any, Dict, Optional

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.event_handler import APIGatewayRestResolver, CORSConfig
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.typing import LambdaContext
from botocore.exceptions import ClientError
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

# Import centralized utilities
from user_auth import extract_user_context

# Initialize PowerTools with configurable log level
logger = Logger(
    service="collections-retrieval",
    level=os.environ.get("LOG_LEVEL", "DEBUG"),
    json_default=str,
)
tracer = Tracer(service="collections-retrieval")
metrics = Metrics(namespace="medialake", service="collections-retrieval")

# Configure CORS
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

# Initialize API Gateway resolver
app = APIGatewayRestResolver(
    serializer=lambda x: json.dumps(x, default=str),
    strip_prefixes=["/api"],
    cors=cors_config,
)

# Initialize DynamoDB client
dynamodb = boto3.resource("dynamodb")

# Get environment variables
TABLE_NAME = os.environ["COLLECTIONS_TABLE_NAME"]
DEFAULT_LIMIT = 20
MAX_LIMIT = 100


@tracer.capture_method
def query_collections_by_owner(
    table, user_id: str, limit: int, start_key: Optional[Dict]
) -> Dict:
    """
    Query collections by owner using GSI1

    Args:
        table: DynamoDB table resource
        user_id: Owner user ID
        limit: Query limit
        start_key: Pagination start key

    Returns:
        Query response
    """
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

    logger.debug(
        {
            "message": "Querying collections by owner",
            "user_id": user_id,
            "query_params": query_params,
            "operation": "query_collections_by_owner",
        }
    )

    response = table.query(**query_params)

    logger.debug(
        {
            "message": "Owner query response",
            "item_count": len(response.get("Items", [])),
            "operation": "query_collections_by_owner",
        }
    )

    return response


@tracer.capture_method
def query_all_collections(table, limit: int, start_key: Optional[Dict]) -> Dict:
    """
    Query all collections using GSI5

    Args:
        table: DynamoDB table resource
        limit: Query limit
        start_key: Pagination start key

    Returns:
        Query response
    """
    query_params = {
        "IndexName": "RecentlyModifiedGSI",
        "KeyConditionExpression": "GSI5_PK = :gsi5_pk",
        "ExpressionAttributeValues": {":gsi5_pk": COLLECTIONS_GSI5_PK},
        "ScanIndexForward": False,  # Most recent first
        "Limit": limit + 1,
    }

    if start_key:
        query_params["ExclusiveStartKey"] = start_key

    logger.debug(
        {
            "message": "Querying all collections",
            "query_params": query_params,
            "operation": "query_all_collections",
        }
    )

    response = table.query(**query_params)

    logger.debug(
        {
            "message": "All collections query response",
            "item_count": len(response.get("Items", [])),
            "operation": "query_all_collections",
        }
    )

    return response


@tracer.capture_method
def query_collections_by_type(
    table, collection_type_id: str, limit: int, start_key: Optional[Dict]
) -> Dict:
    """
    Query collections by type using GSI3

    Args:
        table: DynamoDB table resource
        collection_type_id: Collection type ID
        limit: Query limit
        start_key: Pagination start key

    Returns:
        Query response
    """
    query_params = {
        "IndexName": "CollectionTypeGSI",
        "KeyConditionExpression": "GSI3_PK = :gsi3_pk",
        "ExpressionAttributeValues": {":gsi3_pk": collection_type_id},
        "Limit": limit + 1,
    }

    if start_key:
        query_params["ExclusiveStartKey"] = start_key

    logger.debug(
        {
            "message": "Querying collections by type",
            "collection_type_id": collection_type_id,
            "query_params": query_params,
            "operation": "query_collections_by_type",
        }
    )

    response = table.query(**query_params)

    logger.debug(
        {
            "message": "Type query response",
            "item_count": len(response.get("Items", [])),
            "operation": "query_collections_by_type",
        }
    )

    return response


@tracer.capture_method
def query_child_collections(
    table, parent_id: str, limit: int, start_key: Optional[Dict]
) -> Dict:
    """
    Query child collections by parent ID

    Args:
        table: DynamoDB table resource
        parent_id: Parent collection ID
        limit: Query limit
        start_key: Pagination start key

    Returns:
        Query response
    """
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

    # Need to get the actual collection metadata for each child
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
                logger.warning(
                    {
                        "message": "Failed to get child collection metadata",
                        "child_id": child_id,
                        "error": str(e),
                        "operation": "query_child_collections",
                    }
                )

    # Reconstruct response format
    return {"Items": child_items, "LastEvaluatedKey": response.get("LastEvaluatedKey")}


@app.get("/collections")
@tracer.capture_method
def list_collections():
    """Get list of collections with comprehensive filtering and pagination"""
    print("hit get")
    try:
        # Extract user context
        user_context = extract_user_context(app.current_event.raw_event)
        user_id = user_context.get("user_id")

        logger.debug(
            {
                "message": "User context extracted",
                "user_id": user_id,
                "username": user_context.get("username"),
                "operation": "list_collections",
            }
        )

        # Parse query parameters
        cursor = app.current_event.get_query_string_value("cursor")
        limit = int(app.current_event.get_query_string_value("limit", DEFAULT_LIMIT))

        # Filter parameters
        type_filter = app.current_event.get_query_string_value("filter[type]")
        owner_filter = app.current_event.get_query_string_value("filter[ownerId]")
        favorite_filter = app.current_event.get_query_string_value("filter[favorite]")
        status_filter = app.current_event.get_query_string_value("filter[status]")
        search_filter = app.current_event.get_query_string_value("filter[search]")
        parent_filter = app.current_event.get_query_string_value("filter[parentId]")

        # Other parameters
        sort_param = app.current_event.get_query_string_value("sort")
        fields_param = app.current_event.get_query_string_value("fields")
        include_param = app.current_event.get_query_string_value("include")

        # Validate limit
        limit = min(max(1, limit), MAX_LIMIT)

        logger.debug(
            {
                "message": "Processing collections retrieval request",
                "cursor": cursor,
                "limit": limit,
                "filters": {
                    "type": type_filter,
                    "ownerId": owner_filter,
                    "favorite": favorite_filter,
                    "status": status_filter,
                    "search": search_filter,
                    "parentId": parent_filter,
                },
                "sort": sort_param,
                "fields": fields_param,
                "include": include_param,
                "operation": "list_collections",
            }
        )

        table = dynamodb.Table(TABLE_NAME)

        # Parse cursor for pagination
        start_key = None
        parsed_cursor = parse_cursor(cursor)
        if parsed_cursor:
            start_key = {"PK": parsed_cursor.get("pk"), "SK": parsed_cursor.get("sk")}
            # Add GSI keys if present
            if parsed_cursor.get("gsi_pk"):
                start_key["GSI1_PK"] = parsed_cursor.get("gsi_pk")
            if parsed_cursor.get("gsi_sk"):
                start_key["GSI1_SK"] = parsed_cursor.get("gsi_sk")

        # Determine query strategy based on filters
        if parent_filter:
            # Query child collections
            response = query_child_collections(table, parent_filter, limit, start_key)
        elif owner_filter:
            # Query collections by owner
            response = query_collections_by_owner(table, owner_filter, limit, start_key)
        elif type_filter:
            # Query collections by type
            response = query_collections_by_type(table, type_filter, limit, start_key)
        else:
            # Query all collections
            response = query_all_collections(table, limit, start_key)

        items = response.get("Items", [])

        logger.info(
            {
                "message": "Collections retrieved from DynamoDB",
                "item_count": len(items),
                "has_more": len(items) > limit,
                "operation": "list_collections",
            }
        )

        # Check if we have more results
        has_more = len(items) > limit
        if has_more:
            items = items[:limit]  # Remove the extra item

        # Apply additional filters that couldn't be done at query level
        filters = {"status": status_filter, "search": search_filter}

        # Note: filter_expression is built but applied manually below for flexibility

        if status_filter or search_filter:
            filtered_items = []
            for item in items:
                # Apply status filter
                if status_filter and item.get("status") != status_filter:
                    continue

                # Apply search filter
                if search_filter:
                    search_term = search_filter.lower()
                    name_match = search_term in item.get("name", "").lower()
                    desc_match = search_term in item.get("description", "").lower()
                    if not (name_match or desc_match):
                        continue

                filtered_items.append(item)

            items = filtered_items

            logger.info(
                {
                    "message": "Applied post-query filters",
                    "filtered_count": len(items),
                    "operation": "list_collections",
                }
            )

        # Format items for API response
        formatted_items = [format_collection_item(item, user_context) for item in items]

        # Apply field selection
        if fields_param:
            formatted_items = [
                apply_field_selection(item, fields_param) for item in formatted_items
            ]

        # Apply sorting
        sorted_items = apply_sorting(formatted_items, sort_param)

        # Create pagination info
        pagination = {
            "has_next_page": has_more,
            "has_prev_page": cursor is not None,
            "limit": limit,
        }

        # Add next cursor if there are more results
        if has_more and items:
            last_item = items[-1]  # Use original DynamoDB item for cursor

            # Determine GSI keys based on query type
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

        # Log success metrics
        metrics.add_metric(
            name="SuccessfulCollectionRetrievals", unit=MetricUnit.Count, value=1
        )
        metrics.add_metric(
            name="CollectionsReturned", unit=MetricUnit.Count, value=len(sorted_items)
        )
        print("right before response")
        # Create response using centralized function
        response_data = create_success_response(
            data=sorted_items,
            pagination=pagination,
            request_id=app.current_event.request_context.request_id,
        )

        logger.info(
            {
                "message": "Collections retrieved successfully",
                "total_returned": len(sorted_items),
                "has_next_page": has_more,
                "operation": "list_collections",
            }
        )

        print(response_data)
        return response_data

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        error_message = e.response["Error"]["Message"]

        logger.error(
            {
                "message": "DynamoDB client error during collections retrieval",
                "error_code": error_code,
                "error_message": error_message,
                "operation": "list_collections",
                "status": "failed",
            }
        )

        metrics.add_metric(
            name="FailedCollectionRetrievals", unit=MetricUnit.Count, value=1
        )

        return create_error_response(
            error_code=error_code,
            error_message=error_message,
            status_code=500,
            request_id=app.current_event.request_context.request_id,
        )

    except Exception as e:
        logger.error(
            {
                "message": "Unexpected error during collections retrieval",
                "error_type": type(e).__name__,
                "error_message": str(e),
                "operation": "list_collections",
                "status": "failed",
            }
        )

        metrics.add_metric(name="UnexpectedErrors", unit=MetricUnit.Count, value=1)

        return create_error_response(
            error_code="InternalServerError",
            error_message="An unexpected error occurred",
            status_code=500,
            request_id=app.current_event.request_context.request_id,
        )


@metrics.log_metrics(capture_cold_start_metric=True)
@tracer.capture_lambda_handler
@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """Lambda handler"""
    logger.debug(
        {
            "message": "Lambda handler invoked",
            "event": event,
            "operation": "lambda_handler",
        }
    )
    print("Lambda handler called with event:", event)
    print("Lambda handler called with context:", context)
    return app.resolve(event, context)
