from decimal import Decimal
import json
import os
import time
from typing import Dict, Any
import boto3
from aws_lambda_powertools import Logger, Tracer, Metrics
from aws_lambda_powertools.logging import correlation_paths
from utils import enrich_asset_for_public_access

logger = Logger(service = 'get-public-share')
tracer = Tracer()
metrics = Metrics(namespace="AssetShares", service="get-public-share")

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
        "body": json.dumps(body, cls=DecimalEncoder),  # Use custom encoder
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
    """Handles public access to shared assets via share tokens"""
    
    try:
        share_token = event['pathParameters']['token']
        # Fetch share details
        share_response = shares_table.get_item(Key={'ShareToken': share_token})
        
        if 'Item' not in share_response:
            return create_response(404, "Share not found")

        share = share_response['Item']
        current_time = int(time.time())

        # Check if share is active
        if share['Status'] != 'active':
            return create_response(410, "Share has been revoked")

        if share.get('ExpiresAt') and current_time > share['ExpiresAt']:
            shares_table.update_item(
                Key={'ShareToken': share_token},
                UpdateExpression='SET #status = :expired',
                ExpressionAttributeNames={'#status': 'Status'},
                ExpressionAttributeValues={':expired': 'expired'}
            )
            return create_response(410, "Share has expired")

        asset_id = share['AssetID']
        asset = get_asset(asset_id)

        if not asset:
            return create_response(404, "Asset not found")

        # Update access tracking
        shares_table.update_item(
            Key={'ShareToken': share_token},
            UpdateExpression='SET AccessCount = AccessCount + :inc, LastAccessedAt = :time',
            ExpressionAttributeValues={':inc': 1, ':time': current_time}
        )

        # Generate presigned URLs for asset access based on shared representation type
        enriched_asset = enrich_asset_for_public_access(asset, share['ShareSettings'])

        # Log access
        logger.info(f"Public access to asset {asset_id} via share {share_token}")
        metrics.add_metric(name="PublicShareAccess", unit="Count", value=1)

        return create_response(200, "Asset retrieved successfully", {
            'asset': enriched_asset,
            'shareInfo': {
                'representationType': share['ShareSettings']['representationType'],
                'expiresAt': share.get('ExpiresAt'),
            }
        })
    except Exception as e:
        logger.error(f"Error creating share: {str(e)}")
        return create_response(500, f"Error: {str(e)}")

