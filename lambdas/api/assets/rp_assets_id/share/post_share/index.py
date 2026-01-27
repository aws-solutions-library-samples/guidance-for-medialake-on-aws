from decimal import Decimal
from http import HTTPStatus
import json
import os
import uuid
import time
from typing import Dict, Any
from aws_lambda_powertools.logging import correlation_paths
import boto3
from aws_lambda_powertools import Logger, Tracer, Metrics
from botocore.exceptions import ClientError

logger = Logger()
tracer = Tracer()
metrics = Metrics(namespace="AssetShares", service="post-share")

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

def get_user_id_from_event(event: Dict[str, Any]) -> str:
    """Extract user ID from API Gateway event"""
    request_context = event.get("requestContext", {})
    authorizer = request_context.get("authorizer", {})
    user_id = authorizer.get("sub") or authorizer.get("principalId")

    if not user_id:
        logger.warning("No user ID found in event", extra={"event": event})
        raise ValueError("User ID not found in request context")

    return user_id

class ShareAssetError(Exception):
    """Custom exception for share asset errors."""

    def __init__(self, message: str, status_code: int = HTTPStatus.NOT_FOUND):
        super().__init__(message)
        self.status_code = status_code

@tracer.capture_method
def get_asset(inventory_id: str) -> Dict[str, Any] | None:
    """
    Retrieves asset details from DynamoDB to verify it exists.

    Args:
        inventory_id: The inventory ID of the asset

    Returns:
        Dict containing the asset details. None if asset not found.
    """
    try:
        response = assets_table.get_item(
            Key={"InventoryID": inventory_id},
            ConsistentRead=True,
        )

        if "Item" not in response:
          return None 

        logger.info(
            "Asset retrieved successfully",
            extra={
                "inventory_id": inventory_id,
                "asset_type": response["Item"]
                .get("DigitalSourceAsset", {})
                .get("Type"),
            },
        )
        return response["Item"]

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        error_message = e.response["Error"]["Message"]

        logger.error(
            f"DynamoDB error: {error_message}",
            extra={"error_code": error_code, "inventory_id": inventory_id},
        )
        return None 


@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Create a share for an asset."""
    
    try:
        asset_id = event['pathParameters']['id']
        body = json.loads(event['body'])
        user_id = get_user_id_from_event(event)

        asset = get_asset(asset_id)
        if not asset:
            return create_response(404, f"Asset not found.")

        representation_type = body.get('representationType', 'proxy')
        if representation_type not in ['proxy', 'original']:
            return create_response(400, "Invalid representation type. Must be 'proxy' or 'original'")

        share_token = str(uuid.uuid4())
        current_time = int(time.time())

        expires_in = body.get('expiresIn')  # Seconds
        expires_at = current_time + expires_in if expires_in else None

        share_item = {
            'ShareToken': share_token,
            'AssetID': asset_id,
            'CreatedBy': user_id,
            'CreatedAt': current_time,
            'ExpiresAt': expires_at,
            'Status': 'active',
            'AccessCount': 0,
            'DownloadCount': 0,
            'LastAccessedAt': None,
            'ShareType': 'public',
            'ShareSettings': {
                'representationType': representation_type,
                'allowMetadata': body.get('allowMetadata', True)
            },
            'Metadata': {
                'ipAddress': event['requestContext'].get('identity', {}).get('sourceIp'),
                'userAgent': event['requestContext'].get('identity', {}).get('userAgent')
            }
        }

        # Store in DynamoDB
        shares_table.put_item(Item=share_item)

        logger.info(f"Share created for asset {asset_id} by user {user_id}")
        metrics.add_metric(name="SharesCreated", unit="Count", value=1)

        return create_response(200, "Share created successfully", {
            'shareItem': share_item,
            'shareToken': share_token,
            'representationType': representation_type,
            'expiresAt': expires_at,
            'createdAt': current_time
        })
        
    except Exception as e:
        logger.error(f"Error creating share: {str(e)}")
        return create_response(500, f"Error: {str(e)}")
