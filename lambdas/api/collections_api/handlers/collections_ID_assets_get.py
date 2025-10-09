"""
Collection Assets Handler - Migrated to Pydantic V2.

Handles endpoints for retrieving collection assets with full OpenSearch data:
- GET /collections/<collection_id>/assets - Get collection assets with OpenSearch data and CloudFront URLs
"""

import os
import sys
from typing import Any, Dict, List, Optional

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.event_handler.exceptions import (
    BadRequestError,
    NotFoundError,
)
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.parser import ValidationError
from opensearchpy import OpenSearch, RequestsAWSV4SignerAuth, RequestsHttpConnection

sys.path.insert(0, "/opt/python")
from collections_utils import (
    COLLECTION_PK_PREFIX,
    METADATA_SK,
    create_error_response,
    create_success_response,
)

# Import Pydantic models
from models import GetCollectionAssetsQueryParams
from url_utils import collect_cloudfront_url_requests, generate_cloudfront_urls
from user_auth import extract_user_context

logger = Logger(
    service="collection-assets-handler", level=os.environ.get("LOG_LEVEL", "INFO")
)
tracer = Tracer(service="collection-assets-handler")
metrics = Metrics(namespace="medialake", service="collection-assets")

# Constants
ITEM_SK_PREFIX = "ITEM#"
ASSET_SK_PREFIX = "ASSET#"

# Environment variables
OPENSEARCH_ENDPOINT = os.environ.get("OPENSEARCH_ENDPOINT", "")
OPENSEARCH_INDEX = os.environ.get("OPENSEARCH_INDEX", "")

# Cache for OpenSearch client
_opensearch_client = None


def get_opensearch_client() -> Optional[OpenSearch]:
    """Create and return a cached OpenSearch client"""
    global _opensearch_client

    if not OPENSEARCH_ENDPOINT or not OPENSEARCH_INDEX:
        logger.warning("[OPENSEARCH_INIT] OpenSearch not configured")
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

            logger.info("[OPENSEARCH_INIT] OpenSearch client initialized successfully")
        except Exception as e:
            logger.error(f"[OPENSEARCH_INIT] Failed to initialize client: {str(e)}")
            return None

    return _opensearch_client


def fetch_assets_from_opensearch(asset_ids: List[str]) -> Dict[str, Dict]:
    """Fetch asset data from OpenSearch"""
    client = get_opensearch_client()
    if not client:
        logger.warning("[OPENSEARCH_FETCH] OpenSearch client not available")
        return {}

    assets_data = {}
    try:
        response = client.mget(index=OPENSEARCH_INDEX, body={"ids": asset_ids})

        for doc in response.get("docs", []):
            if doc.get("found"):
                inventory_id = doc["_source"].get("InventoryID")
                if inventory_id:
                    assets_data[inventory_id] = doc["_source"]
                    logger.info(f"[OPENSEARCH_FETCH] Retrieved asset: {inventory_id}")
    except Exception as e:
        logger.error(f"[OPENSEARCH_FETCH] Error fetching assets: {str(e)}")

    return assets_data


def format_asset_as_search_result(
    collection_item: Dict,
    asset_data: Optional[Dict],
    cloudfront_urls: Dict[str, Optional[str]],
    all_clips_for_asset: Optional[List[Dict]] = None,
) -> Dict[str, Any]:
    """Format asset data as search result with CloudFront URLs and clip information"""
    sk = collection_item["SK"]

    # Handle both old ITEM# and new ASSET# formats
    if sk.startswith(ASSET_SK_PREFIX):
        inventory_id = collection_item.get("assetId", "")
    else:
        item_id = sk.replace(ITEM_SK_PREFIX, "")
        inventory_id = collection_item.get("itemId", item_id)

    clip_boundary = collection_item.get("clipBoundary", {})

    if not asset_data:
        logger.warning(
            f"Asset data not found in OpenSearch for inventory_id={inventory_id}"
        )
        return {
            "InventoryID": inventory_id,
            "DigitalSourceAsset": {},
            "DerivedRepresentations": [],
            "FileHash": "",
            "Metadata": {},
            "score": 1.0,
            "thumbnailUrl": None,
            "proxyUrl": None,
            "id": inventory_id.split(":")[-1] if ":" in inventory_id else inventory_id,
            "addedAt": collection_item.get("addedAt", ""),
            "addedBy": collection_item.get("addedBy", ""),
            "clipBoundary": clip_boundary,
        }

    # Get CloudFront URLs
    thumbnail_request_id = f"{inventory_id}_thumbnail"
    proxy_request_id = f"{inventory_id}_proxy"

    thumbnail_url = cloudfront_urls.get(thumbnail_request_id)
    proxy_url = cloudfront_urls.get(proxy_request_id)

    # Extract UUID part from inventory ID for id field
    asset_id = inventory_id.split(":")[-1] if ":" in inventory_id else inventory_id

    result = {
        "InventoryID": inventory_id,
        "DigitalSourceAsset": asset_data.get("DigitalSourceAsset", {}),
        "DerivedRepresentations": asset_data.get("DerivedRepresentations", []),
        "FileHash": asset_data.get("FileHash", ""),
        "Metadata": asset_data.get("Metadata", {}),
        "score": 1.0,
        "thumbnailUrl": thumbnail_url,
        "proxyUrl": proxy_url,
        "id": asset_id,
        "addedAt": collection_item.get("addedAt", ""),
        "addedBy": collection_item.get("addedBy", ""),
        "clipBoundary": clip_boundary,
    }

    # If this is a clip item, add clip information to match search results format
    if clip_boundary and clip_boundary.get("startTime"):
        result["clips"] = [
            {
                "start_timecode": clip_boundary.get("startTime"),
                "end_timecode": clip_boundary.get("endTime"),
                "score": 1.0,
            }
        ]
    elif all_clips_for_asset:
        result["clips"] = all_clips_for_asset

    return result


def register_routes(app, dynamodb, table_name):
    """Register collection assets routes"""

    @app.get("/collections/<collection_id>/assets")
    @tracer.capture_method
    def collections_ID_assets_get(collection_id: str):
        """Get collection assets with OpenSearch data and CloudFront URLs"""
        try:
            extract_user_context(app.current_event.raw_event)
            table = dynamodb.Table(table_name)

            # Parse and validate query parameters with Pydantic
            try:
                page = int(app.current_event.get_query_string_value("page", 1))
                page_size = int(
                    app.current_event.get_query_string_value("pageSize", 50)
                )
                query_params = GetCollectionAssetsQueryParams(
                    page=page, pageSize=page_size
                )
            except ValidationError as e:
                logger.warning(f"Validation error in query parameters: {e}")
                raise BadRequestError(f"Invalid query parameters: {str(e)}")

            logger.info(
                f"[ASSETS_HANDLER] Getting assets for collection {collection_id}, "
                f"page={query_params.page}, pageSize={query_params.pageSize}"
            )

            # Verify collection exists
            collection_response = table.get_item(
                Key={"PK": f"{COLLECTION_PK_PREFIX}{collection_id}", "SK": METADATA_SK}
            )
            if "Item" not in collection_response:
                raise NotFoundError(f"Collection '{collection_id}' not found")

            # Get all items from the collection (both old ITEM# and new ASSET# formats)
            all_items = []

            # Query for old ITEM# format
            response = table.query(
                KeyConditionExpression="PK = :pk AND begins_with(SK, :sk_prefix)",
                ExpressionAttributeValues={
                    ":pk": f"{COLLECTION_PK_PREFIX}{collection_id}",
                    ":sk_prefix": ITEM_SK_PREFIX,
                },
            )
            all_items.extend(response.get("Items", []))

            # Query for new ASSET# format
            response = table.query(
                KeyConditionExpression="PK = :pk AND begins_with(SK, :sk_prefix)",
                ExpressionAttributeValues={
                    ":pk": f"{COLLECTION_PK_PREFIX}{collection_id}",
                    ":sk_prefix": ASSET_SK_PREFIX,
                },
            )
            all_items.extend(response.get("Items", []))

            # Filter for asset items only
            asset_items = [
                item for item in all_items if item.get("itemType") == "asset"
            ]

            # Apply pagination
            start_idx = (query_params.page - 1) * query_params.pageSize
            end_idx = start_idx + query_params.pageSize
            paginated_items = asset_items[start_idx:end_idx]

            # Extract unique asset IDs from paginated items
            asset_ids = []
            seen_asset_ids = set()
            for item in paginated_items:
                if item["SK"].startswith(ASSET_SK_PREFIX):
                    asset_id = item.get("assetId")
                else:
                    asset_id = item.get("itemId")

                if asset_id and asset_id not in seen_asset_ids:
                    asset_ids.append(asset_id)
                    seen_asset_ids.add(asset_id)

            logger.info(f"[ASSETS_HANDLER] Processing {len(asset_ids)} unique assets")

            # Fetch asset data from OpenSearch
            assets_data = {}
            if asset_ids:
                assets_data = fetch_assets_from_opensearch(asset_ids)
                logger.info(
                    f"[ASSETS_HANDLER] Retrieved {len(assets_data)} assets from OpenSearch"
                )

            # Collect CloudFront URL requests
            url_requests = {}
            for item in paginated_items:
                if item["SK"].startswith(ASSET_SK_PREFIX):
                    inventory_id = item.get("assetId", "")
                else:
                    item_id = item["SK"].replace(ITEM_SK_PREFIX, "")
                    inventory_id = item.get("itemId", item_id)

                asset_data = assets_data.get(inventory_id)
                if asset_data:
                    requests = collect_cloudfront_url_requests(asset_data, inventory_id)
                    url_requests.update(requests)

            logger.info(f"[URL_COLLECTION] Collected {len(url_requests)} URL requests")

            # Generate CloudFront URLs
            cloudfront_urls = generate_cloudfront_urls(url_requests)
            logger.info(
                f"[URL_GENERATION] Generated {len(cloudfront_urls)} CloudFront URLs"
            )

            # Format results
            results = []
            for item in paginated_items:
                if item["SK"].startswith(ASSET_SK_PREFIX):
                    inventory_id = item.get("assetId", "")
                else:
                    item_id = item["SK"].replace(ITEM_SK_PREFIX, "")
                    inventory_id = item.get("itemId", item_id)

                asset_data = assets_data.get(inventory_id)
                result = format_asset_as_search_result(
                    item, asset_data, cloudfront_urls
                )
                results.append(result)

            metrics.add_metric(
                name="AssetsRetrieved", unit=MetricUnit.Count, value=len(results)
            )
            metrics.add_metric(
                name="AssetsWithThumbnails",
                unit=MetricUnit.Count,
                value=sum(1 for r in results if r.get("thumbnailUrl")),
            )
            metrics.add_metric(
                name="AssetsWithProxies",
                unit=MetricUnit.Count,
                value=sum(1 for r in results if r.get("proxyUrl")),
            )

            return create_success_response(
                data={
                    "results": results,
                    "searchMetadata": {
                        "page": query_params.page,
                        "pageSize": query_params.pageSize,
                        "totalResults": len(asset_items),
                        "hasMore": end_idx < len(asset_items),
                    },
                },
                request_id=app.current_event.request_context.request_id,
            )

        except (BadRequestError, NotFoundError):
            raise  # Re-raise Powertools exceptions
        except Exception as e:
            logger.exception("Error retrieving collection assets", exc_info=e)
            return create_error_response(
                error_code="InternalServerError",
                error_message="An unexpected error occurred",
                status_code=500,
                request_id=app.current_event.request_context.request_id,
            )
