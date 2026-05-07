"""Formatting utilities for Collections API responses."""

from typing import Any, Dict, List, Optional

from aws_lambda_powertools import Logger

logger = Logger(service="formatting-utils")

# Constants
ITEM_SK_PREFIX = "ITEM#"
ASSET_SK_PREFIX = "ASSET#"
RULE_SK_PREFIX = "RULE#"
COLLECTION_TYPE_SK_PREFIX = "COLLTYPE#"


def format_collection_item(item: Dict, clip_boundary: Optional[Dict] = None) -> Dict:
    """Format collection item for API response"""
    sk = item["SK"]

    if sk.startswith(ASSET_SK_PREFIX):
        item_id = sk
    else:
        item_id = sk.replace(ITEM_SK_PREFIX, "")

    return {
        "id": item_id,
        "itemType": item.get("itemType", ""),
        "assetId": item.get("assetId", item.get("itemId", "")),
        "clipBoundary": clip_boundary or item.get("clipBoundary", {}),
        "sortOrder": item.get("sortOrder", 0),
        "metadata": item.get("metadata", {}),
        "addedAt": item.get("addedAt", ""),
        "addedBy": item.get("addedBy", ""),
    }


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


def format_share(item: Dict) -> Dict:
    """Format share item for API response"""
    return {
        "targetId": item.get("targetId", ""),
        "targetType": item.get("targetType", ""),
        "role": item.get("role", ""),
        "grantedBy": item.get("grantedBy", ""),
        "grantedAt": item.get("grantedAt", ""),
        "message": item.get("message"),
    }


def format_rule(item: Dict) -> Dict:
    """Format rule item for API response"""
    rule_id = item["SK"].replace(RULE_SK_PREFIX, "")
    return {
        "id": rule_id,
        "name": item.get("name", ""),
        "description": item.get("description"),
        "ruleType": item.get("ruleType", ""),
        "criteria": item.get("criteria", {}),
        "isActive": item.get("isActive", True),
        "priority": item.get("priority", 0),
        "matchCount": item.get("matchCount", 0),
        "createdAt": item.get("createdAt", ""),
        "updatedAt": item.get("updatedAt", ""),
    }


def format_collection_type(item: Dict) -> Dict:
    """Format collection type for API response"""
    type_id = item["SK"].replace(COLLECTION_TYPE_SK_PREFIX, "")
    return {
        "id": type_id,
        "name": item.get("name", ""),
        "description": item.get("description"),
        "isActive": item.get("isActive", True),
        "allowedItemTypes": item.get("allowedItemTypes", []),
        "schema": item.get("schema"),
        "createdAt": item.get("createdAt", ""),
        "updatedAt": item.get("updatedAt", ""),
    }
