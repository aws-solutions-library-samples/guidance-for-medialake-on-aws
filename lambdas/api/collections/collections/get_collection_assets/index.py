import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.event_handler import APIGatewayRestResolver, CORSConfig
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.typing import LambdaContext
from botocore.exceptions import ClientError
from collections_utils import (
    ACCESS_LEVELS,
    COLLECTION_PK_PREFIX,
    METADATA_SK,
    create_cursor,
    create_error_response,
    parse_cursor,
    validate_collection_access,
)
from opensearchpy import OpenSearch, RequestsAWSV4SignerAuth, RequestsHttpConnection
from pydantic import BaseModel
from url_utils import generate_cloudfront_urls_batch

# Import centralized utilities
from user_auth import extract_user_context

# Initialize PowerTools with configurable log level
logger = Logger(
    service="collection-assets-retrieval",
    level=os.environ.get("LOG_LEVEL", "WARNING"),
    json_default=str,
)
tracer = Tracer(service="collection-assets-retrieval")
metrics = Metrics(namespace="medialake", service="collection-assets-retrieval")

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

# Initialize clients
dynamodb = boto3.resource("dynamodb")

# Get environment variables
TABLE_NAME = os.environ["COLLECTIONS_TABLE_NAME"]
OPENSEARCH_ENDPOINT = os.environ.get("OPENSEARCH_ENDPOINT", "")
OPENSEARCH_INDEX = os.environ.get("OPENSEARCH_INDEX", "")
DEFAULT_LIMIT = 20
MAX_LIMIT = 100

# Constants
COLLECTION_PK_PREFIX = "COLL#"
ITEM_SK_PREFIX = "ITEM#"
METADATA_SK = "METADATA"
VALID_ITEM_TYPES = ["asset", "workflow", "collection"]
VALID_SORT_OPTIONS = ["score", "-score", "addedAt", "-addedAt", "name", "-name"]

# Cache for OpenSearch client
_opensearch_client = None


class AssetSearchResult(BaseModel):
    """Model for asset search result matching search API format"""

    InventoryID: str
    DigitalSourceAsset: Dict[str, Any]
    DerivedRepresentations: List[Dict[str, Any]]
    FileHash: str
    Metadata: Dict[str, Any]
    score: float
    thumbnailUrl: Optional[str] = None
    proxyUrl: Optional[str] = None
    id: Optional[str] = None
    addedAt: Optional[str] = None
    addedBy: Optional[str] = None


class SearchMetadata(BaseModel):
    """Model for search metadata matching search API format"""

    totalResults: int
    page: int
    pageSize: int
    searchTerm: str = ""
    facets: Optional[Dict[str, Any]] = None
    suggestions: Optional[Dict[str, Any]] = None


@tracer.capture_method
def get_opensearch_client() -> Optional[OpenSearch]:
    """Create and return a cached OpenSearch client"""
    global _opensearch_client

    if not OPENSEARCH_ENDPOINT:
        logger.warning("OpenSearch endpoint not configured")
        return None

    if _opensearch_client is None:
        try:
            host = OPENSEARCH_ENDPOINT.replace("https://", "")
            region = os.environ["AWS_REGION"]
            service_scope = os.environ.get("SCOPE", "es")

            auth = RequestsAWSV4SignerAuth(
                boto3.Session().get_credentials(), region, service_scope
            )

            _opensearch_client = OpenSearch(
                hosts=[{"host": host, "port": 443}],
                http_auth=auth,
                use_ssl=True,
                verify_certs=True,
                connection_class=RequestsHttpConnection,
                region=region,
                timeout=30,
                max_retries=2,
                retry_on_timeout=True,
            )

            logger.info("OpenSearch client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize OpenSearch client: {str(e)}")
            return None

    return _opensearch_client


@tracer.capture_method
def get_collection_items(
    table,
    collection_id: str,
    limit: int,
    start_key: Optional[Dict] = None,
    type_filter: Optional[str] = None,
) -> Dict[str, Any]:
    """Get collection items from DynamoDB"""
    query_params = {
        "KeyConditionExpression": "PK = :pk AND begins_with(SK, :sk_prefix)",
        "ExpressionAttributeValues": {
            ":pk": f"{COLLECTION_PK_PREFIX}{collection_id}",
            ":sk_prefix": ITEM_SK_PREFIX,
        },
        "Limit": limit + 1,  # Get one extra to determine if there are more results
    }

    # Add type filter if specified
    if type_filter:
        query_params["FilterExpression"] = "itemType = :item_type"
        query_params["ExpressionAttributeValues"][":item_type"] = type_filter.upper()

    if start_key:
        query_params["ExclusiveStartKey"] = start_key

    # Execute query
    response = table.query(**query_params)
    items = response.get("Items", [])

    logger.info(
        {
            "message": "Collection items retrieved from DynamoDB",
            "collection_id": collection_id,
            "item_count": len(items),
            "has_more": len(items) > limit,
            "operation": "get_collection_items",
        }
    )

    return {
        "items": items,
        "has_more": len(items) > limit,
        "last_evaluated_key": response.get("LastEvaluatedKey"),
    }


@tracer.capture_method
def fetch_assets_from_opensearch(asset_ids: List[str]) -> Dict[str, Dict]:
    """Fetch full asset data from OpenSearch for given asset IDs"""
    if not asset_ids:
        return {}

    client = get_opensearch_client()
    if not client:
        logger.warning("OpenSearch client not available")
        return {}

    try:
        # Build multi-match query for asset IDs
        should_clauses = []
        for asset_id in asset_ids:
            should_clauses.append({"match_phrase": {"InventoryID": asset_id}})

        search_body = {
            "query": {
                "bool": {
                    "should": should_clauses,
                    "minimum_should_match": 1,
                    "must_not": [{"term": {"embedding_scope": "clip"}}],
                }
            },
            "size": len(asset_ids),
            "_source": {
                "includes": [
                    "InventoryID",
                    "DigitalSourceAsset",
                    "DerivedRepresentations",
                    "FileHash",
                    "Metadata",
                ]
            },
        }

        response = client.search(body=search_body, index=OPENSEARCH_INDEX)
        hits = response.get("hits", {}).get("hits", [])

        # Build lookup dictionary by InventoryID
        assets_data = {}
        for hit in hits:
            source = hit["_source"]
            inventory_id = source.get("InventoryID")
            if inventory_id:
                assets_data[inventory_id] = source

        logger.info(
            {
                "message": "Assets fetched from OpenSearch",
                "requested_count": len(asset_ids),
                "found_count": len(assets_data),
                "operation": "fetch_assets_from_opensearch",
            }
        )

        return assets_data

    except Exception as e:
        logger.error(
            {
                "message": "Failed to fetch assets from OpenSearch",
                "error": str(e),
                "asset_ids": asset_ids,
                "operation": "fetch_assets_from_opensearch",
            }
        )
        return {}


@tracer.capture_method
def collect_cloudfront_url_requests(assets_data: Dict[str, Dict]) -> List[Dict]:
    """Collect CloudFront URL requests from asset data"""
    url_requests = []

    for inventory_id, asset_data in assets_data.items():
        derived_representations = asset_data.get("DerivedRepresentations", [])

        for representation in derived_representations:
            purpose = representation.get("Purpose", "unknown")
            rep_storage_info = representation.get("StorageInfo", {}).get(
                "PrimaryLocation", {}
            )

            if rep_storage_info.get("StorageType") == "s3" and purpose in [
                "thumbnail",
                "proxy",
            ]:
                bucket = rep_storage_info.get("Bucket", "")
                object_key = rep_storage_info.get("ObjectKey", {})
                key = object_key.get("FullPath", "")

                if bucket and key:
                    request_id = f"{inventory_id}_{purpose}"
                    url_requests.append(
                        {
                            "request_id": request_id,
                            "bucket": bucket,
                            "key": key,
                        }
                    )

    logger.info(
        {
            "message": "CloudFront URL requests collected",
            "url_requests_count": len(url_requests),
            "operation": "collect_cloudfront_url_requests",
        }
    )

    return url_requests


@tracer.capture_method
def format_asset_as_search_result(
    collection_item: Dict,
    asset_data: Optional[Dict],
    cloudfront_urls: Dict[str, Optional[str]],
) -> AssetSearchResult:
    """Format asset data as search result with CloudFront URLs"""
    item_id = collection_item["SK"].replace(ITEM_SK_PREFIX, "")
    inventory_id = collection_item.get("itemId", item_id)

    if not asset_data:
        # If asset data not found in OpenSearch, create minimal result
        logger.warning(
            {
                "message": "Asset data not found in OpenSearch",
                "inventory_id": inventory_id,
                "operation": "format_asset_as_search_result",
            }
        )

        return AssetSearchResult(
            InventoryID=inventory_id,
            DigitalSourceAsset={},
            DerivedRepresentations=[],
            FileHash="",
            Metadata={},
            score=1.0,  # Default relevance score for collection items
            thumbnailUrl=None,
            proxyUrl=None,
            id=inventory_id.split(":")[-1] if ":" in inventory_id else inventory_id,
            addedAt=collection_item.get("addedAt", ""),
            addedBy=collection_item.get("addedBy", ""),
        )

    # Get CloudFront URLs
    thumbnail_url = cloudfront_urls.get(f"{inventory_id}_thumbnail")
    proxy_url = cloudfront_urls.get(f"{inventory_id}_proxy")

    # Extract UUID part from inventory ID for id field
    asset_id = inventory_id.split(":")[-1] if ":" in inventory_id else inventory_id

    result = AssetSearchResult(
        InventoryID=inventory_id,
        DigitalSourceAsset=asset_data.get("DigitalSourceAsset", {}),
        DerivedRepresentations=asset_data.get("DerivedRepresentations", []),
        FileHash=asset_data.get("FileHash", ""),
        Metadata=asset_data.get("Metadata", {}),
        score=1.0,  # Default relevance score for collection items
        thumbnailUrl=thumbnail_url,
        proxyUrl=proxy_url,
        id=asset_id,
        addedAt=collection_item.get("addedAt", ""),
        addedBy=collection_item.get("addedBy", ""),
    )

    logger.debug(
        {
            "message": "Asset formatted as search result",
            "inventory_id": inventory_id,
            "has_thumbnail": thumbnail_url is not None,
            "has_proxy": proxy_url is not None,
            "operation": "format_asset_as_search_result",
        }
    )

    return result


@tracer.capture_method
def apply_sorting(
    results: List[AssetSearchResult], sort_param: Optional[str]
) -> List[AssetSearchResult]:
    """Apply sorting to asset results"""
    if not sort_param or not results:
        return results

    # Parse sort direction and field
    descending = sort_param.startswith("-")
    sort_field = sort_param[1:] if descending else sort_param

    logger.debug(
        {
            "message": "Applying sort to collection assets",
            "sort_field": sort_field,
            "descending": descending,
            "result_count": len(results),
            "operation": "apply_sorting",
        }
    )

    # Define sorting key functions
    sort_key_map = {
        "score": lambda x: getattr(x, "score", 0),
        "addedAt": lambda x: getattr(x, "addedAt", ""),
        "name": lambda x: x.DigitalSourceAsset.get("MainRepresentation", {})
        .get("StorageInfo", {})
        .get("PrimaryLocation", {})
        .get("ObjectKey", {})
        .get("Name", ""),
    }

    sort_key_func = sort_key_map.get(sort_field, lambda x: getattr(x, "score", 0))

    try:
        sorted_results = sorted(results, key=sort_key_func, reverse=descending)
        logger.info(
            {
                "message": "Collection assets sorted successfully",
                "sort_field": sort_field,
                "descending": descending,
                "sorted_count": len(sorted_results),
                "operation": "apply_sorting",
            }
        )
        return sorted_results
    except Exception as e:
        logger.error(
            {
                "message": "Failed to sort collection assets",
                "sort_field": sort_field,
                "error": str(e),
                "operation": "apply_sorting",
            }
        )
        return results


@app.get("/collections/<collection_id>/assets")
@tracer.capture_method
def get_collection_assets(collection_id: str):
    """Get collection assets formatted as search results with rich asset data"""
    try:
        # Extract user context
        user_context = extract_user_context(app.current_event.raw_event)
        user_id = user_context.get("user_id")

        # Parse query parameters
        cursor = app.current_event.get_query_string_value("cursor")
        limit = int(app.current_event.get_query_string_value("limit", DEFAULT_LIMIT))
        type_filter = app.current_event.get_query_string_value("filter[type]")
        sort_param = app.current_event.get_query_string_value("sort")
        page = int(app.current_event.get_query_string_value("page", 1))

        # Validate limit
        limit = min(max(1, limit), MAX_LIMIT)

        # Validate sort parameter
        if sort_param and sort_param not in VALID_SORT_OPTIONS:
            logger.warning(
                {
                    "message": "Invalid sort parameter",
                    "sort_param": sort_param,
                    "valid_options": VALID_SORT_OPTIONS,
                    "operation": "get_collection_assets",
                }
            )
            return {
                "success": False,
                "error": {
                    "code": "INVALID_SORT_PARAMETER",
                    "message": f"Invalid sort parameter. Valid options: {', '.join(VALID_SORT_OPTIONS)}",
                },
                "meta": {
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "version": "v1",
                    "request_id": app.current_event.request_context.request_id,
                },
            }, 400

        # Validate type filter
        if type_filter and type_filter not in VALID_ITEM_TYPES:
            logger.warning(
                {
                    "message": "Invalid type filter",
                    "type_filter": type_filter,
                    "valid_types": VALID_ITEM_TYPES,
                    "operation": "get_collection_assets",
                }
            )
            return {
                "success": False,
                "error": {
                    "code": "INVALID_TYPE_FILTER",
                    "message": f"Invalid type filter. Valid options: {', '.join(VALID_ITEM_TYPES)}",
                },
                "meta": {
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "version": "v1",
                    "request_id": app.current_event.request_context.request_id,
                },
            }, 400

        logger.debug(
            {
                "message": "Processing collection assets retrieval request",
                "collection_id": collection_id,
                "cursor": cursor,
                "limit": limit,
                "type_filter": type_filter,
                "sort": sort_param,
                "page": page,
                "user_id": user_id,
                "operation": "get_collection_assets",
            }
        )

        table = dynamodb.Table(TABLE_NAME)

        # Validate collection access
        access_result = validate_collection_access(
            table, collection_id, user_id, ACCESS_LEVELS["READ"]
        )
        if not access_result["valid"]:
            return create_error_response(
                error_code=access_result.get("error_code", "ACCESS_DENIED"),
                error_message=access_result.get(
                    "error", "Collection not found or access denied"
                ),
                status_code=404,
                request_id=app.current_event.request_context.request_id,
            )

        # Parse cursor for pagination
        start_key = None
        parsed_cursor = parse_cursor(cursor)
        if parsed_cursor:
            start_key = {"PK": parsed_cursor.get("pk"), "SK": parsed_cursor.get("sk")}

        # Get collection items from DynamoDB
        collection_data = get_collection_items(
            table, collection_id, limit, start_key, type_filter
        )
        items = collection_data["items"]
        has_more = collection_data["has_more"]

        if has_more:
            items = items[:limit]  # Remove the extra item

        # Extract asset IDs for assets only (not workflows or sub-collections)
        asset_ids = []
        for item in items:
            if item.get("itemType", "").lower() == "asset":
                asset_ids.append(
                    item.get("itemId", item["SK"].replace(ITEM_SK_PREFIX, ""))
                )

        # Fetch full asset data from OpenSearch
        assets_data = {}
        if asset_ids:
            assets_data = fetch_assets_from_opensearch(asset_ids)

        # Collect CloudFront URL requests
        url_requests = collect_cloudfront_url_requests(assets_data)

        # Generate CloudFront URLs in batch
        cloudfront_urls = {}
        if url_requests:
            try:
                cloudfront_urls = generate_cloudfront_urls_batch(url_requests)
            except Exception as e:
                logger.warning(
                    {
                        "message": "Failed to generate CloudFront URLs",
                        "error": str(e),
                        "operation": "get_collection_assets",
                    }
                )

        # Format items as search results
        results = []
        for item in items:
            item_id = item["SK"].replace(ITEM_SK_PREFIX, "")
            inventory_id = item.get("itemId", item_id)
            asset_data = assets_data.get(inventory_id)

            result = format_asset_as_search_result(item, asset_data, cloudfront_urls)
            results.append(result)

        # Apply sorting
        sorted_results = apply_sorting(results, sort_param)

        # Convert to dictionaries for JSON serialization
        formatted_results = [
            result.model_dump(by_alias=True) for result in sorted_results
        ]

        # Create pagination info
        pagination = {
            "has_next_page": has_more,
            "has_prev_page": cursor is not None,
            "limit": limit,
        }

        # Add next cursor if there are more results
        if has_more and items:
            last_item = items[-1]  # Use original DynamoDB item for cursor
            next_cursor = create_cursor(last_item["PK"], last_item["SK"])
            pagination["next_cursor"] = next_cursor

        # Create search metadata to match search API format
        search_metadata = SearchMetadata(
            totalResults=len(
                formatted_results
            ),  # This could be improved with a count query
            page=page,
            pageSize=limit,
            searchTerm=f"collection:{collection_id}",
            facets=None,
            suggestions=None,
        )

        # Log success metrics
        metrics.add_metric(
            name="SuccessfulCollectionAssetRetrievals", unit=MetricUnit.Count, value=1
        )
        metrics.add_metric(
            name="CollectionAssetsReturned",
            unit=MetricUnit.Count,
            value=len(formatted_results),
        )

        # Create response in collections API format (consistent with other collection endpoints)
        response_data = {
            "success": True,
            "data": {
                "results": formatted_results,
                "searchMetadata": search_metadata.model_dump(by_alias=True),
            },
            "meta": {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "version": "v1",
                "request_id": app.current_event.request_context.request_id,
            },
        }

        logger.info(
            {
                "message": "Collection assets retrieved successfully",
                "collection_id": collection_id,
                "total_returned": len(formatted_results),
                "has_next_page": has_more,
                "operation": "get_collection_assets",
            }
        )

        return response_data

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        error_message = e.response["Error"]["Message"]

        logger.error(
            {
                "message": "DynamoDB client error during collection assets retrieval",
                "collection_id": collection_id,
                "error_code": error_code,
                "error_message": error_message,
                "operation": "get_collection_assets",
                "status": "failed",
            }
        )

        metrics.add_metric(
            name="FailedCollectionAssetRetrievals", unit=MetricUnit.Count, value=1
        )

        return {
            "success": False,
            "error": {
                "code": error_code,
                "message": error_message,
            },
            "meta": {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "version": "v1",
                "request_id": app.current_event.request_context.request_id,
            },
        }, 500

    except Exception as e:
        logger.error(
            {
                "message": "Unexpected error during collection assets retrieval",
                "collection_id": collection_id,
                "error_type": type(e).__name__,
                "error_message": str(e),
                "operation": "get_collection_assets",
                "status": "failed",
            }
        )

        metrics.add_metric(name="UnexpectedErrors", unit=MetricUnit.Count, value=1)

        return {
            "success": False,
            "error": {
                "code": "InternalServerError",
                "message": "An unexpected error occurred",
            },
            "meta": {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "version": "v1",
                "request_id": app.current_event.request_context.request_id,
            },
        }, 500


@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """Lambda handler"""
    logger.debug(
        {
            "message": "Lambda handler invoked",
            "event": event,
            "operation": "lambda_handler",
        }
    )
    return app.resolve(event, context)
