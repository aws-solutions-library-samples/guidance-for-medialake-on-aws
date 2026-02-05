import json
import os
import time
from typing import Dict, Any
import boto3
from aws_lambda_powertools import Logger, Tracer, Metrics
from aws_lambda_powertools.logging import correlation_paths
from utils import generate_presigned_url_for_embedded

logger = Logger(service='get-public-share-embed')
tracer = Tracer()
metrics = Metrics(namespace="AssetShares", service="get-public-share-embed")

shares_table = boto3.resource('dynamodb').Table(os.environ['SHARES_TABLE_NAME'])
assets_table = boto3.resource('dynamodb').Table(os.environ['ASSETS_TABLE_NAME'])

def create_redirect_response(url: str) -> Dict[str, Any]:
    """Creates a redirect response to the asset URL."""
    return {
        "statusCode": 302,
        "headers": {
            "Location": url,
            "Access-Control-Allow-Origin": "*",
        },
        "body": "",
    }

def create_error_response(
    status_code: int, message: str
) -> Dict[str, Any]:
    """Creates a standardized error response."""
    body = {
        "status": "error",
        "message": message,
    }
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps(body),
    }

def get_share(share_token: str) -> Dict[str, Any] | None:
    """
    Retrieves share details from DynamoDB.

    Args:
        share_token: The share token

    Returns:
        Share item or None if not found
    """
    try:
        response = shares_table.get_item(Key={"ShareToken": share_token})
        return response.get("Item")
    except Exception as e:
        logger.error(
            f"Error getting share: {str(e)}",
            extra={"share_token": share_token},
        )
        return None

def get_asset(inventory_id: str) -> Dict[str, Any] | None:
    """
    Retrieves asset details from DynamoDB.

    Args:
        inventory_id: The asset inventory ID

    Returns:
        Asset item or None if not found
    """
    try:
        response = assets_table.get_item(Key={"InventoryID": inventory_id})
        return response.get("Item")
    except Exception as e:
        logger.error(
            f"Error getting asset: {str(e)}",
            extra={"inventory_id": inventory_id},
        )
        return None

def is_share_valid(share: Dict[str, Any]) -> tuple[bool, str]:
    """
    Validates if a share is still active and not expired.

    Args:
        share: Share item from DynamoDB

    Returns:
        Tuple of (is_valid, reason_if_invalid)
    """
    if share.get("Status") == "revoked":
        return False, "Share has been revoked"

    expires_at = share.get("ExpiresAt")
    if expires_at and int(expires_at) < int(time.time()):
        return False, "Share has expired"

    return True, ""

@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Serve embed HTML for a shared asset.

    Args:
        event: API Gateway event
        context: Lambda context

    Returns:
        Response with HTML content
    """
    share_token = None
    try:
        share_token = event.get("pathParameters", {}).get("shareToken")
        if not share_token:
            return create_error_response(400, "Share token is required")

        share = get_share(share_token)
        if not share:
            return create_error_response(404, "Share not found")

        is_valid, invalid_reason = is_share_valid(share)
        if not is_valid:
            return create_error_response(410, invalid_reason)

        share_settings = share.get('ShareSettings', {})
        if not share_settings.get('allowEmbedding', True):
            return create_error_response(403, "Embedding is not allowed for this share")

        asset_id = share['AssetID']
        asset = get_asset(asset_id)
        if not asset:
            return create_error_response(404, "Asset not found")

        presigned_url = generate_presigned_url_for_embedded(asset, share_settings)
        if not presigned_url:
            return create_error_response(404, "No valid representation available for embedding")

        metrics.add_metric(name="EmbedServed", unit="Count", value=1)
        return create_redirect_response(presigned_url)

    except Exception as e:
        logger.exception(
            "Error redirecting to asset",
            extra={
                "error": str(e),
                "share_token": share_token or "unknown",
            },
        )
        metrics.add_metric(name="AssetRedirectError", unit="Count", value=1)
        return create_error_response(500, "Error redirecting to asset")
