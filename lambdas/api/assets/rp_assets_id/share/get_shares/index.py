
from decimal import Decimal
import json
import os
from typing import Dict, Any
from aws_lambda_powertools.logging import correlation_paths
import boto3
from aws_lambda_powertools import Logger, Tracer, Metrics
from utils import extract_user_context, is_admin

logger = Logger()
tracer = Tracer()
metrics = Metrics(namespace="AssetShares", service="get-shares")

shares_table = boto3.resource('dynamodb').Table(os.environ['SHARES_TABLE_NAME'])

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


@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Get all shares for an asset"""
    
    try:
        asset_id = event['pathParameters']['id']
        user_context = extract_user_context(event)
        user_id = user_context['user_id']
        
        logger.info(f"Querying shares for asset {asset_id}")
        
        # Query all shares for this asset using AssetID-CreatedAt-index GSI
        response = shares_table.query(
            IndexName='AssetID-CreatedAt-index',
            KeyConditionExpression='AssetID = :asset_id',
            ExpressionAttributeValues={
                ':asset_id': asset_id
            },
            ScanIndexForward=False  # Sort by CreatedAt descending (newest first)
        )
        
        shares = response.get('Items', [])
        for share in shares:
            share['IsOwner'] = is_admin(user_context) or (share['CreatedBy'] == user_id)
        
        logger.info(f"Found {len(shares)} active shares for asset {asset_id}")
        
        return create_response(
            200, 
            f"Successfully retrieved shares for asset {asset_id}",
            {
                "shares": shares,
                "count": len(shares)
            }
        )
        
    except Exception as e:
        logger.error(f"Error retrieving shares for asset: {str(e)}")
        return create_response(500, f"Error: {str(e)}")
