"""OpenSearch utilities for Collections API."""

import os
from typing import Any, Dict, List, Optional

import boto3
from aws_lambda_powertools import Logger
from opensearchpy import OpenSearch, RequestsAWSV4SignerAuth, RequestsHttpConnection

logger = Logger(service="opensearch-utils")

# Environment variables
OPENSEARCH_ENDPOINT = os.environ.get("OPENSEARCH_ENDPOINT", "")
OPENSEARCH_INDEX = os.environ.get("OPENSEARCH_INDEX", "")

# Cache for OpenSearch client
_opensearch_client = None


def get_opensearch_client() -> Optional[OpenSearch]:
    """Create and return a cached OpenSearch client"""
    global _opensearch_client

    if not OPENSEARCH_ENDPOINT or not OPENSEARCH_INDEX:
        logger.warning("[OPENSEARCH] OpenSearch not configured")
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

            logger.info("[OPENSEARCH] OpenSearch client initialized successfully")
        except Exception as e:
            logger.error(f"[OPENSEARCH] Failed to initialize client: {str(e)}")
            return None

    return _opensearch_client


def get_all_clips_for_asset(asset_id: str) -> List[Dict[str, Any]]:
    """
    Retrieve all clips for a specific asset from OpenSearch.

    Args:
        asset_id: The ID of the asset to retrieve clips for

    Returns:
        List of clip objects with startTime and endTime
    """
    try:
        client = get_opensearch_client()
        if not client:
            logger.warning(
                f"[CLIPS] OpenSearch client not available for asset {asset_id}"
            )
            return []

        # Query for clips associated with this asset
        query = {
            "query": {
                "bool": {
                    "must": [
                        {"term": {"InventoryID": asset_id}},
                        {"term": {"embedding_scope": "clip"}},
                    ]
                }
            },
            "size": 1000,  # Get all clips
            "_source": ["start_timecode", "end_timecode", "score"],
            "sort": [{"start_timecode": {"order": "asc"}}],
        }

        response = client.search(body=query, index=OPENSEARCH_INDEX)

        clips = []
        for hit in response["hits"]["hits"]:
            source = hit["_source"]
            start_time = source.get("start_timecode")
            end_time = source.get("end_timecode")

            if start_time and end_time:
                clips.append(
                    {
                        "startTime": start_time,
                        "endTime": end_time,
                    }
                )

        logger.info(f"[CLIPS] Retrieved {len(clips)} clips for asset {asset_id}")
        return clips

    except Exception as e:
        logger.error(f"[CLIPS] Error retrieving clips for asset {asset_id}: {str(e)}")
        return []


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
