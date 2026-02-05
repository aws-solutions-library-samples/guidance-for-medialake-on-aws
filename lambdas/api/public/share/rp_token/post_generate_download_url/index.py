from decimal import Decimal
import json
import os
import time
from typing import Dict, Any
import boto3
from aws_lambda_powertools import Logger, Tracer, Metrics
from aws_lambda_powertools.logging import correlation_paths

from utils import generate_download_url_for_share

logger = Logger(service = 'get-public-share-download-url')
tracer = Tracer()
metrics = Metrics(namespace="AssetShares", service="get-public-share-download-url")

shares_table = boto3.resource('dynamodb').Table(os.environ['SHARES_TABLE_NAME'])
assets_table = boto3.resource('dynamodb').Table(os.environ['ASSETS_TABLE_NAME'])

class DecimalEncoder(json.JSONEncoder):
    """Custom JSON encoder for Decimal types."""

    def default(self, obj):
        if isinstance(obj, Decimal):
            return str(obj)
        return super(DecimalEncoder, self).default(obj)

def create_response(
    status_code: int, message: str, data: Dict[str, Any] = None
) -> Dict[str, Any]:
    """Creates a standardized API response."""
    body = {
        "status": "success" if status_code < 400 else "error",
        "message": message,
        "data": data or {},
    }

    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Credentials": True,
        },
        "body": json.dumps(body, cls=DecimalEncoder),
    }

def get_asset(inventory_id: str) -> Dict[str, Any] | None:
    """
    Retrieves asset details from DynamoDB to verify it exists.

    Args:
        inventory_id: The inventory ID of the asset
    Returns:
        Dict containing the asset details. None if asset not found.
    """
    response = assets_table.get_item(Key={'InventoryID': inventory_id})
    return response.get('Item')


@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Handles download URL generation for public shared assets"""
    
    try:
        share_token = event['pathParameters']['shareToken']
        share_response = shares_table.get_item(Key={'ShareToken': share_token})
        
        if 'Item' not in share_response:
            return create_response(404, "Share not found")

        share = share_response['Item']
        current_time = int(time.time())

        if share['Status'] != 'active':
            return create_response(410, "Share has been revoked")

        if share.get('ExpiresAt') and current_time > share['ExpiresAt']:
            return create_response(410, "Share has expired")

        asset_id = share['AssetID']
        asset = get_asset(asset_id)

        if not asset:
            return create_response(404, "Asset not found")

        shares_table.update_item(
            Key={'ShareToken': share_token},
            UpdateExpression='SET DownloadCount = DownloadCount + :inc',
            ExpressionAttributeValues={':inc': 1}
        )

        download_url = generate_download_url_for_share(asset, share['ShareSettings'])

        if not download_url:
            return create_response(500, "Failed to generate download URL")

        logger.info(f"Download URL generated for asset {asset_id} via share {share_token}")
        metrics.add_metric(name="PublicShareDownload", unit="Count", value=1)

        return create_response(200, "Download URL generated successfully", {
            'downloadUrl': download_url
        })
    except Exception as e:
        logger.error(f"Error generating download URL: {str(e)}")
        return create_response(500, f"Error: {str(e)}")

