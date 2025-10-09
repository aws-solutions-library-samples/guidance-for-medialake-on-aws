"""
Collection Assets Routes.

Handles retrieving assets from collections with OpenSearch integration:
- GET /collections/{collectionId}/assets - Get collection assets with full details
"""

import json
import os
import sys
from datetime import datetime
from typing import Dict, List, Optional

import boto3
from aws_lambda_powertools import Logger, Tracer
from opensearchpy import OpenSearch, RequestsAWSV4SignerAuth, RequestsHttpConnection

sys.path.insert(0, "/opt/python")
from collections_utils import (
    COLLECTION_PK_PREFIX,
    create_error_response,
)
from url_utils import generate_cloudfront_urls_batch

logger = Logger(service="assets-routes", level=os.environ.get("LOG_LEVEL", "INFO"))
tracer = Tracer(service="assets-routes")

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

    logger.info(
        f"[GET_OS_CLIENT] OPENSEARCH_ENDPOINT={OPENSEARCH_ENDPOINT}, INDEX={OPENSEARCH_INDEX}"
    )

    if not OPENSEARCH_ENDPOINT or not OPENSEARCH_INDEX:
        logger.warning(
            "[GET_OS_CLIENT] OpenSearch not configured - missing endpoint or index"
        )
        return None

    if _opensearch_client is None:
        try:
            host = OPENSEARCH_ENDPOINT.replace("https://", "")
            region = os.environ["AWS_REGION"]

            logger.info(
                f"[GET_OS_CLIENT] Creating client for host={host}, region={region}"
            )

            credentials = boto3.Session().get_credentials()
            auth = RequestsAWSV4SignerAuth(credentials, region, "es")

            _opensearch_client = OpenSearch(
                hosts=[{"host": host, "port": 443}],
                http_auth=auth,
                use_ssl=True,
                verify_certs=True,
                connection_class=RequestsHttpConnection,
                pool_maxsize=20,
            )
            logger.info("[GET_OS_CLIENT] OpenSearch client created successfully")
        except Exception as e:
            logger.error(
                f"[GET_OS_CLIENT] Error creating OpenSearch client: {str(e)}",
                exc_info=e,
            )
            return None

    return _opensearch_client


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
        f"[COLLECT_URLS] CloudFront URL requests collected: {len(url_requests)}"
    )
    return url_requests


def register_routes(app, dynamodb, table_name):
    """Register collection assets routes"""

    logger.info("[REGISTER_ROUTES] Registering assets routes")

    @app.get("/collections/<collection_id>/assets")
    def get_collection_assets(collection_id: str):
        """Get collection assets with full OpenSearch details"""
        try:
            logger.info(
                f"[GET_ASSETS] ========== START: Collection {collection_id} =========="
            )

            # Extract query parameters
            page = int(app.current_event.get_query_string_value("page", "1"))
            page_size = int(app.current_event.get_query_string_value("pageSize", "50"))

            logger.info(f"[GET_ASSETS] Query params: page={page}, pageSize={page_size}")

            table = dynamodb.Table(table_name)

            # Step 1: Get all items from the collection (both old ITEM# and new ASSET# formats)
            logger.info("[GET_ASSETS] Step 1: Querying DynamoDB for collection items")
            all_items = []

            # Query for old ITEM# format
            logger.info("[GET_ASSETS] Querying for ITEM# prefix items")
            response = table.query(
                KeyConditionExpression="PK = :pk AND begins_with(SK, :sk_prefix)",
                ExpressionAttributeValues={
                    ":pk": f"{COLLECTION_PK_PREFIX}{collection_id}",
                    ":sk_prefix": ITEM_SK_PREFIX,
                },
            )
            item_count = len(response.get("Items", []))
            logger.info(f"[GET_ASSETS] Found {item_count} items with ITEM# prefix")
            all_items.extend(response.get("Items", []))

            # Query for new ASSET# format
            logger.info("[GET_ASSETS] Querying for ASSET# prefix items")
            response = table.query(
                KeyConditionExpression="PK = :pk AND begins_with(SK, :sk_prefix)",
                ExpressionAttributeValues={
                    ":pk": f"{COLLECTION_PK_PREFIX}{collection_id}",
                    ":sk_prefix": ASSET_SK_PREFIX,
                },
            )
            asset_count = len(response.get("Items", []))
            logger.info(f"[GET_ASSETS] Found {asset_count} items with ASSET# prefix")
            all_items.extend(response.get("Items", []))

            # Filter for asset items only
            asset_items = [
                item for item in all_items if item.get("itemType") == "asset"
            ]
            logger.info(f"[GET_ASSETS] Total asset items: {len(asset_items)}")

            if not asset_items:
                logger.info("[GET_ASSETS] No assets found in collection")
                return {
                    "statusCode": 200,
                    "body": json.dumps(
                        {
                            "success": True,
                            "data": {
                                "results": [],
                                "searchMetadata": {
                                    "totalResults": 0,
                                    "page": page,
                                    "pageSize": page_size,
                                },
                            },
                            "meta": {
                                "timestamp": datetime.utcnow().isoformat() + "Z",
                                "version": "v1",
                                "request_id": app.current_event.request_context.request_id,
                            },
                        }
                    ),
                }

            # Step 2: Apply pagination
            logger.info("[GET_ASSETS] Step 2: Applying pagination")
            start_idx = (page - 1) * page_size
            end_idx = start_idx + page_size
            paginated_items = asset_items[start_idx:end_idx]
            logger.info(
                f"[GET_ASSETS] Paginated items: {len(paginated_items)} (from {start_idx} to {end_idx})"
            )

            # Step 3: Extract unique asset IDs
            logger.info("[GET_ASSETS] Step 3: Extracting unique asset IDs")
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

            logger.info(f"[GET_ASSETS] Unique asset IDs: {len(asset_ids)}")
            logger.info(
                f"[GET_ASSETS] Asset IDs: {asset_ids[:5]}..."
                if len(asset_ids) > 5
                else f"[GET_ASSETS] Asset IDs: {asset_ids}"
            )

            # Step 4: Fetch asset data from OpenSearch
            logger.info("[GET_ASSETS] Step 4: Fetching from OpenSearch")
            assets_data = {}

            client = get_opensearch_client()
            if client and asset_ids:
                try:
                    logger.info(
                        f"[GET_ASSETS] Querying OpenSearch for {len(asset_ids)} assets"
                    )

                    # Build match_phrase queries for text field (InventoryID is type "text", not "keyword")
                    should_clauses = []
                    for asset_id in asset_ids:
                        should_clauses.append(
                            {"match_phrase": {"InventoryID": asset_id}}
                        )

                    query = {
                        "query": {
                            "bool": {
                                "should": should_clauses,
                                "minimum_should_match": 1,
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

                    logger.info(f"[GET_ASSETS] OpenSearch query: {json.dumps(query)}")
                    response = client.search(body=query, index=OPENSEARCH_INDEX)

                    hits = response.get("hits", {}).get("hits", [])
                    logger.info(f"[GET_ASSETS] OpenSearch returned {len(hits)} results")

                    for hit in hits:
                        source = hit["_source"]
                        inventory_id = source.get("InventoryID")
                        assets_data[inventory_id] = source
                        logger.info(f"[GET_ASSETS] Mapped asset: {inventory_id}")

                except Exception as e:
                    logger.error(
                        f"[GET_ASSETS] OpenSearch query error: {str(e)}", exc_info=e
                    )
            else:
                logger.warning(
                    f"[GET_ASSETS] Skipping OpenSearch query - client={client is not None}, asset_ids={len(asset_ids)}"
                )

            # Step 5: Collect CloudFront URL requests
            logger.info("[GET_ASSETS] Step 5: Collecting CloudFront URL requests")
            cloudfront_url_requests = collect_cloudfront_url_requests(assets_data)
            logger.info(
                f"[GET_ASSETS] Collected {len(cloudfront_url_requests)} CloudFront URL requests"
            )

            # Step 6: Get CloudFront URLs
            logger.info("[GET_ASSETS] Step 6: Fetching CloudFront URLs")
            cloudfront_urls = {}
            if cloudfront_url_requests:
                try:
                    cloudfront_urls = generate_cloudfront_urls_batch(
                        cloudfront_url_requests
                    )
                    logger.info(
                        f"[GET_ASSETS] Retrieved {len(cloudfront_urls)} CloudFront URLs"
                    )
                except Exception as e:
                    logger.error(
                        f"[GET_ASSETS] Failed to generate CloudFront URLs: {str(e)}",
                        exc_info=e,
                    )
            else:
                logger.warning("[GET_ASSETS] No CloudFront URL requests to process")

            # Step 7: Format results
            logger.info("[GET_ASSETS] Step 7: Formatting results")
            results = []
            for item in paginated_items:
                if item["SK"].startswith(ASSET_SK_PREFIX):
                    inventory_id = item.get("assetId", "")
                else:
                    item_id = item["SK"].replace(ITEM_SK_PREFIX, "")
                    inventory_id = item.get("itemId", item_id)

                asset_data = assets_data.get(inventory_id)
                clip_boundary = item.get("clipBoundary", {})

                logger.info(
                    f"[GET_ASSETS] Formatting item: inventory_id={inventory_id}, has_asset_data={asset_data is not None}, clip_boundary={clip_boundary}"
                )

                if not asset_data:
                    logger.warning(
                        f"[GET_ASSETS] Asset data not found in OpenSearch for {inventory_id}"
                    )
                    result = {
                        "InventoryID": inventory_id,
                        "DigitalSourceAsset": {},
                        "DerivedRepresentations": [],
                        "FileHash": "",
                        "Metadata": {},
                        "score": 1.0,
                        "thumbnailUrl": None,
                        "proxyUrl": None,
                        "id": (
                            inventory_id.split(":")[-1]
                            if ":" in inventory_id
                            else inventory_id
                        ),
                        "addedAt": item.get("addedAt", ""),
                        "addedBy": item.get("addedBy", ""),
                        "clipBoundary": clip_boundary,
                    }
                else:
                    # Get CloudFront URLs
                    thumbnail_request_id = f"{inventory_id}_thumbnail"
                    proxy_request_id = f"{inventory_id}_proxy"
                    thumbnail_url = cloudfront_urls.get(thumbnail_request_id)
                    proxy_url = cloudfront_urls.get(proxy_request_id)

                    logger.info(
                        f"[GET_ASSETS] URLs for {inventory_id}: thumbnail={thumbnail_url is not None}, proxy={proxy_url is not None}"
                    )

                    asset_id = (
                        inventory_id.split(":")[-1]
                        if ":" in inventory_id
                        else inventory_id
                    )

                    result = {
                        "InventoryID": inventory_id,
                        "DigitalSourceAsset": asset_data.get("DigitalSourceAsset", {}),
                        "DerivedRepresentations": asset_data.get(
                            "DerivedRepresentations", []
                        ),
                        "FileHash": asset_data.get("FileHash", ""),
                        "Metadata": asset_data.get("Metadata", {}),
                        "score": 1.0,
                        "thumbnailUrl": thumbnail_url,
                        "proxyUrl": proxy_url,
                        "id": asset_id,
                        "addedAt": item.get("addedAt", ""),
                        "addedBy": item.get("addedBy", ""),
                        "clipBoundary": clip_boundary,
                    }

                    # If this is a clip item, add clip information
                    if clip_boundary and clip_boundary.get("startTime"):
                        result["clips"] = [
                            {
                                "start_timecode": clip_boundary.get("startTime"),
                                "end_timecode": clip_boundary.get("endTime"),
                                "score": 1.0,
                            }
                        ]
                        logger.info(
                            f"[GET_ASSETS] Added clip info to result for {inventory_id}"
                        )

                results.append(result)
                logger.info(
                    f"[GET_ASSETS] Result added: id={result['id']}, has_clips={bool(result.get('clips'))}"
                )

            logger.info(f"[GET_ASSETS] Total results formatted: {len(results)}")

            # Step 8: Return response
            logger.info("[GET_ASSETS] Step 8: Returning response")
            response_data = {
                "success": True,
                "data": {
                    "results": results,
                    "searchMetadata": {
                        "totalResults": len(asset_items),
                        "page": page,
                        "pageSize": page_size,
                    },
                },
                "meta": {
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "version": "v1",
                    "request_id": app.current_event.request_context.request_id,
                },
            }

            logger.info(
                f"[GET_ASSETS] ========== END: Returning {len(results)} results =========="
            )

            return {
                "statusCode": 200,
                "body": json.dumps(response_data),
            }

        except Exception as e:
            logger.exception(
                f"[GET_ASSETS] ERROR in get_collection_assets: {str(e)}", exc_info=e
            )
            return create_error_response(
                error_code="InternalServerError",
                error_message=f"An unexpected error occurred: {str(e)}",
                status_code=500,
                request_id=app.current_event.request_context.request_id,
            )

    logger.info("[REGISTER_ROUTES] Assets routes registered successfully")
