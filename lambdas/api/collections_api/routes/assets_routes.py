"""
Collection Assets Routes.

Handles collection assets retrieval (integration with OpenSearch):
- GET /collections/{collectionId}/assets - Get collection assets with search
"""

import os
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.metrics import MetricUnit
from opensearchpy import OpenSearch, RequestsAWSV4SignerAuth, RequestsHttpConnection

sys.path.insert(0, "/opt/python")
from collections_utils import (
    COLLECTION_PK_PREFIX,
    create_error_response,
)
from url_utils import generate_cloudfront_urls_batch
from user_auth import extract_user_context

logger = Logger(service="assets-routes", level=os.environ.get("LOG_LEVEL", "INFO"))
tracer = Tracer(service="assets-routes")
metrics = Metrics(namespace="medialake", service="collection-assets")

# Constants
ITEM_SK_PREFIX = "ITEM#"
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100

# Environment variables
OPENSEARCH_ENDPOINT = os.environ.get("OPENSEARCH_ENDPOINT", "")
OPENSEARCH_INDEX = os.environ.get("OPENSEARCH_INDEX", "")

# Cache for OpenSearch client
_opensearch_client = None


def get_opensearch_client() -> Optional[OpenSearch]:
    """Create and return a cached OpenSearch client"""
    global _opensearch_client

    # Log environment configuration for debugging
    if _opensearch_client is None:
        logger.info(
            f"[OPENSEARCH_INIT] Initializing OpenSearch client: "
            f"ENDPOINT={OPENSEARCH_ENDPOINT}, INDEX={OPENSEARCH_INDEX}, "
            f"REGION={os.environ.get('AWS_REGION', 'NOT_SET')}, "
            f"SCOPE={os.environ.get('SCOPE', 'NOT_SET')}, "
            f"ENVIRONMENT={os.environ.get('ENVIRONMENT', 'NOT_SET')}"
        )

    if not OPENSEARCH_ENDPOINT:
        logger.error(
            "[OPENSEARCH_INIT] OPENSEARCH_ENDPOINT environment variable not set or empty"
        )
        return None

    if not OPENSEARCH_INDEX:
        logger.error(
            "[OPENSEARCH_INIT] OPENSEARCH_INDEX environment variable not set or empty"
        )
        return None

    if _opensearch_client is None:
        try:
            host = OPENSEARCH_ENDPOINT.replace("https://", "")
            region = os.environ["AWS_REGION"]
            service_scope = os.environ.get("SCOPE", "es")

            logger.info(
                f"[OPENSEARCH_INIT] Connecting to host: {host}, region: {region}, scope: {service_scope}"
            )

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
            logger.error(
                f"[OPENSEARCH_INIT] Failed to initialize OpenSearch client: {str(e)}",
                exc_info=True,
            )
            return None
    else:
        logger.debug("[OPENSEARCH_INIT] Using cached OpenSearch client")

    return _opensearch_client


@tracer.capture_method(capture_response=False)
def fetch_assets_from_opensearch(asset_ids: List[str]) -> Dict[str, Dict]:
    """Fetch full asset data from OpenSearch for given asset IDs"""
    if not asset_ids:
        logger.debug("[OPENSEARCH_FETCH] No asset IDs provided, returning empty dict")
        return {}

    logger.info(f"[OPENSEARCH_FETCH] Starting fetch for {len(asset_ids)} asset IDs")
    logger.debug(f"[OPENSEARCH_FETCH] Asset IDs: {asset_ids}")

    client = get_opensearch_client()
    if not client:
        logger.error(
            "[OPENSEARCH_FETCH] OpenSearch client not available, cannot fetch assets"
        )
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

        logger.debug(
            f"[OPENSEARCH_FETCH] Executing query on index '{OPENSEARCH_INDEX}'"
        )
        response = client.search(body=search_body, index=OPENSEARCH_INDEX)
        hits = response.get("hits", {}).get("hits", [])
        total_hits = response.get("hits", {}).get("total", {}).get("value", 0)

        logger.info(
            f"[OPENSEARCH_FETCH] Query returned {len(hits)} hits (total: {total_hits})"
        )

        # Build lookup dictionary by InventoryID
        assets_data = {}
        for idx, hit in enumerate(hits):
            source = hit["_source"]
            inventory_id = source.get("InventoryID")
            if inventory_id:
                assets_data[inventory_id] = source
                derived_reps = source.get("DerivedRepresentations", [])
                logger.debug(
                    f"[OPENSEARCH_FETCH] Hit {idx + 1}: InventoryID={inventory_id}, "
                    f"has_DigitalSourceAsset={bool(source.get('DigitalSourceAsset'))}, "
                    f"DerivedRepresentations_count={len(derived_reps)}"
                )
            else:
                logger.warning(
                    f"[OPENSEARCH_FETCH] Hit {idx + 1} missing InventoryID field"
                )

        logger.info(
            f"[OPENSEARCH_FETCH] Successfully fetched: requested={len(asset_ids)}, "
            f"found={len(assets_data)}, missing={len(asset_ids) - len(assets_data)}"
        )

        # Log any missing assets
        found_ids = set(assets_data.keys())
        requested_ids = set(asset_ids)
        missing_ids = requested_ids - found_ids
        if missing_ids:
            logger.warning(
                f"[OPENSEARCH_FETCH] Assets not found in OpenSearch: {list(missing_ids)}"
            )

        return assets_data

    except Exception as e:
        logger.error(
            f"[OPENSEARCH_FETCH] Failed to fetch assets from OpenSearch: {str(e)}",
            exc_info=True,
        )
        return {}


def collect_cloudfront_url_requests(assets_data: Dict[str, Dict]) -> List[Dict]:
    """Collect CloudFront URL requests from asset data"""
    logger.info(
        f"[URL_COLLECTION] Starting URL collection for {len(assets_data)} assets"
    )
    url_requests = []

    thumbnail_count = 0
    proxy_count = 0

    for inventory_id, asset_data in assets_data.items():
        derived_representations = asset_data.get("DerivedRepresentations", [])
        logger.debug(
            f"[URL_COLLECTION] Processing asset {inventory_id}: "
            f"found {len(derived_representations)} DerivedRepresentations"
        )

        if not derived_representations:
            logger.warning(
                f"[URL_COLLECTION] Asset {inventory_id} has no DerivedRepresentations"
            )
            continue

        for idx, representation in enumerate(derived_representations):
            purpose = representation.get("Purpose", "unknown")
            rep_storage_info = representation.get("StorageInfo", {}).get(
                "PrimaryLocation", {}
            )
            storage_type = rep_storage_info.get("StorageType", "unknown")

            logger.debug(
                f"[URL_COLLECTION]   Rep {idx}: purpose={purpose}, storage_type={storage_type}"
            )

            if rep_storage_info.get("StorageType") == "s3" and purpose in [
                "thumbnail",
                "proxy",
            ]:
                bucket = rep_storage_info.get("Bucket", "")
                object_key = rep_storage_info.get("ObjectKey", {})
                key = object_key.get("FullPath", "")

                logger.debug(
                    f"[URL_COLLECTION]     S3 {purpose} found: bucket='{bucket}', key='{key}'"
                )

                if bucket and key:
                    request_id = f"{inventory_id}_{purpose}"
                    url_request = {
                        "request_id": request_id,
                        "bucket": bucket,
                        "key": key,
                    }
                    url_requests.append(url_request)

                    if purpose == "thumbnail":
                        thumbnail_count += 1
                    elif purpose == "proxy":
                        proxy_count += 1

                    logger.debug(
                        f"[URL_COLLECTION]     Added URL request: {url_request}"
                    )
                else:
                    logger.warning(
                        f"[URL_COLLECTION]     Missing bucket or key for {purpose}: "
                        f"bucket='{bucket}', key='{key}'"
                    )
            elif purpose in ["thumbnail", "proxy"]:
                logger.debug(
                    f"[URL_COLLECTION]     Skipping {purpose} with non-S3 storage: {storage_type}"
                )

    logger.info(
        f"[URL_COLLECTION] Collection complete: total_requests={len(url_requests)}, "
        f"thumbnails={thumbnail_count}, proxies={proxy_count}"
    )

    if url_requests:
        logger.debug(f"[URL_COLLECTION] URL requests summary: {url_requests}")
    else:
        logger.warning(
            "[URL_COLLECTION] No URL requests collected - check DerivedRepresentations structure"
        )

    return url_requests


def format_asset_as_search_result(
    collection_item: Dict,
    asset_data: Optional[Dict],
    cloudfront_urls: Dict[str, Optional[str]],
) -> Dict[str, Any]:
    """Format asset data as search result with CloudFront URLs"""
    item_id = collection_item["SK"].replace(ITEM_SK_PREFIX, "")
    inventory_id = collection_item.get("itemId", item_id)

    if not asset_data:
        # If asset data not found in OpenSearch, create minimal result
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
        }

    # Get CloudFront URLs
    thumbnail_request_id = f"{inventory_id}_thumbnail"
    proxy_request_id = f"{inventory_id}_proxy"

    thumbnail_url = cloudfront_urls.get(thumbnail_request_id)
    proxy_url = cloudfront_urls.get(proxy_request_id)

    logger.info(
        f"Looking up URLs for {inventory_id}: thumbnail_key={thumbnail_request_id}, "
        f"proxy_key={proxy_request_id}, thumbnail_url={thumbnail_url}, proxy_url={proxy_url}"
    )
    logger.info(f"Available CloudFront URL keys: {list(cloudfront_urls.keys())}")

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
    }

    logger.info(
        f"Asset formatted: inventory_id={inventory_id}, has_thumbnail={thumbnail_url is not None}, "
        f"has_proxy={proxy_url is not None}"
    )

    return result


def register_routes(app, dynamodb, table_name):
    """Register collection assets routes"""

    @app.get("/collections/<collection_id>/assets")
    @tracer.capture_method(capture_response=False)
    def get_collection_assets(collection_id: str):
        """Get collection assets formatted as search results with rich asset data"""
        try:
            extract_user_context(app.current_event.raw_event)

            # Parse query parameters - use page and pageSize for frontend compatibility
            page = int(app.current_event.get_query_string_value("page", "1"))
            page_size = int(
                app.current_event.get_query_string_value(
                    "pageSize", str(DEFAULT_PAGE_SIZE)
                )
            )
            page_size = min(max(1, page_size), MAX_PAGE_SIZE)

            app.current_event.get_query_string_value("search", "")
            app.current_event.get_query_string_value("sortBy", "addedAt")
            app.current_event.get_query_string_value("sortOrder", "desc")

            logger.info(
                f"Processing collection assets retrieval: collection_id={collection_id}, "
                f"page={page}, pageSize={page_size}"
            )

            table = dynamodb.Table(table_name)

            # Get collection items from DynamoDB
            response = table.query(
                KeyConditionExpression="PK = :pk AND begins_with(SK, :sk_prefix)",
                ExpressionAttributeValues={
                    ":pk": f"{COLLECTION_PK_PREFIX}{collection_id}",
                    ":sk_prefix": ITEM_SK_PREFIX,
                },
                Limit=page_size * page,  # Get up to current page
            )

            items = response.get("Items", [])

            # Filter for asset items only
            asset_items = [item for item in items if item.get("itemType") == "asset"]

            # Apply pagination (simple approach - for large collections, use cursor-based pagination)
            start_idx = (page - 1) * page_size
            end_idx = start_idx + page_size
            paginated_items = asset_items[start_idx:end_idx]

            # Extract asset IDs from paginated items
            asset_ids = []
            for item in paginated_items:
                asset_id = item.get("itemId")
                if asset_id:
                    asset_ids.append(asset_id)

            logger.info(f"Found {len(asset_ids)} asset IDs to fetch from OpenSearch")

            # Fetch full asset data from OpenSearch
            logger.info(
                f"[ASSETS_HANDLER] Fetching {len(asset_ids)} assets from OpenSearch"
            )
            assets_data = {}
            if asset_ids:
                assets_data = fetch_assets_from_opensearch(asset_ids)
                logger.info(
                    f"[ASSETS_HANDLER] Fetched {len(assets_data)} assets from OpenSearch"
                )

                # Log representation summary for debugging
                for inv_id, data in assets_data.items():
                    reps = data.get("DerivedRepresentations", [])
                    rep_purposes = [r.get("Purpose", "unknown") for r in reps]
                    logger.debug(
                        f"[ASSETS_HANDLER] Asset {inv_id}: {len(reps)} reps with purposes: {rep_purposes}"
                    )
            else:
                logger.warning("[ASSETS_HANDLER] No asset IDs to fetch")

            # Collect CloudFront URL requests
            logger.info("[ASSETS_HANDLER] Collecting CloudFront URL requests")
            url_requests = collect_cloudfront_url_requests(assets_data)
            logger.info(
                f"[ASSETS_HANDLER] Collected {len(url_requests)} CloudFront URL requests"
            )

            if url_requests:
                logger.debug(f"[ASSETS_HANDLER] URL requests details: {url_requests}")
            else:
                logger.warning(
                    "[ASSETS_HANDLER] No URL requests collected. "
                    "This means no S3-based thumbnails or proxies were found in DerivedRepresentations"
                )

            # Generate CloudFront URLs in batch
            logger.info("[ASSETS_HANDLER] Generating CloudFront URLs")
            cloudfront_urls = {}
            if url_requests:
                try:
                    logger.info(
                        f"[ASSETS_HANDLER] Calling generate_cloudfront_urls_batch with {len(url_requests)} requests"
                    )
                    cloudfront_urls = generate_cloudfront_urls_batch(url_requests)

                    successful_urls = sum(
                        1 for url in cloudfront_urls.values() if url is not None
                    )
                    failed_urls = len(cloudfront_urls) - successful_urls

                    logger.info(
                        f"[ASSETS_HANDLER] CloudFront URL generation complete: "
                        f"total={len(cloudfront_urls)}, successful={successful_urls}, failed={failed_urls}"
                    )

                    if cloudfront_urls:
                        logger.debug(
                            f"[ASSETS_HANDLER] Generated URLs: {cloudfront_urls}"
                        )

                    if failed_urls > 0:
                        failed_requests = [
                            k for k, v in cloudfront_urls.items() if v is None
                        ]
                        logger.warning(
                            f"[ASSETS_HANDLER] Failed to generate URLs for: {failed_requests}"
                        )

                except Exception as e:
                    logger.exception(
                        f"[ASSETS_HANDLER] Exception during CloudFront URL generation: {str(e)}"
                    )
                    logger.error(
                        "[ASSETS_HANDLER] CloudFront URL generation failed completely. "
                        "Check SSM parameter for CloudFront domain and IAM permissions."
                    )
            else:
                logger.info("[ASSETS_HANDLER] Skipping URL generation - no requests")

            # Format items as search results
            logger.info(
                f"[ASSETS_HANDLER] Formatting {len(paginated_items)} items as search results"
            )
            results = []
            assets_with_thumbnails = 0
            assets_with_proxies = 0

            for item in paginated_items:
                item_id = item["SK"].replace(ITEM_SK_PREFIX, "")
                inventory_id = item.get("itemId", item_id)
                asset_data = assets_data.get(inventory_id)

                result = format_asset_as_search_result(
                    item, asset_data, cloudfront_urls
                )
                results.append(result)

                if result.get("thumbnailUrl"):
                    assets_with_thumbnails += 1
                if result.get("proxyUrl"):
                    assets_with_proxies += 1

            logger.info(
                f"[ASSETS_HANDLER] Formatted results: total={len(results)}, "
                f"with_thumbnails={assets_with_thumbnails}, with_proxies={assets_with_proxies}"
            )

            # Create search metadata to match search API format
            search_metadata = {
                "totalResults": len(asset_items),
                "page": page,
                "pageSize": page_size,
            }

            # Log success metrics
            metrics.add_metric(
                name="SuccessfulCollectionAssetRetrievals",
                unit=MetricUnit.Count,
                value=1,
            )
            metrics.add_metric(
                name="CollectionAssetsReturned",
                unit=MetricUnit.Count,
                value=len(results),
            )
            metrics.add_metric(
                name="AssetsWithThumbnails",
                unit=MetricUnit.Count,
                value=assets_with_thumbnails,
            )
            metrics.add_metric(
                name="AssetsWithProxies",
                unit=MetricUnit.Count,
                value=assets_with_proxies,
            )

            logger.info(
                f"[ASSETS_HANDLER] Request complete: collection_id={collection_id}, "
                f"total_assets={len(results)}, page={page}, "
                f"thumbnails={assets_with_thumbnails}, proxies={assets_with_proxies}"
            )

            # Return response in the format expected by frontend
            return {
                "success": True,
                "data": {
                    "results": results,
                    "searchMetadata": search_metadata,
                },
                "meta": {
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "version": "v1",
                    "request_id": app.current_event.request_context.request_id,
                },
            }

        except Exception as e:
            logger.exception("Error retrieving collection assets", exc_info=e)
            metrics.add_metric(
                name="FailedCollectionAssetRetrievals", unit=MetricUnit.Count, value=1
            )
            return create_error_response(
                error_code="InternalServerError",
                error_message="An unexpected error occurred",
                status_code=500,
                request_id=app.current_event.request_context.request_id,
            )
