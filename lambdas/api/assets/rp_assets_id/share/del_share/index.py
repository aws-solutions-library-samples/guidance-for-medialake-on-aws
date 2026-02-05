
from decimal import Decimal
import json
import os
from typing import Dict, Any
from aws_lambda_powertools.logging import correlation_paths
import boto3
from aws_lambda_powertools import Logger, Tracer, Metrics
from utils import is_admin, extract_user_context

logger = Logger()
tracer = Tracer()
metrics = Metrics(namespace="AssetShares", service="delete-share")

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
        share_token = event['pathParameters']['shareToken']
        user_context = extract_user_context(event)
        user_id = user_context['user_id']
        
        share_response = shares_table.get_item(Key={'ShareToken': share_token})

        if 'Item' not in share_response:
            return create_response(404, "Share not found")
        
        share = share_response['Item']

        if share['AssetID'] != asset_id:
            return create_response(400, "Share does not belong to the specified asset")
        
        if share['CreatedBy'] != user_id and not is_admin(user_context):
            return create_response(403, "User not authorized to delete this share")
        
        shares_table.update_item(
            Key={'ShareToken': share_token},
            UpdateExpression='SET #status = :revoked',
            ExpressionAttributeNames={'#status': 'Status'},
            ExpressionAttributeValues={':revoked': 'revoked'}
        )

        logger.info(f"Share {share_token} revoked by user {user_id}")
        metrics.add_metric(name="SharesRevoked", unit="Count", value=1)

        return create_response(200, "Share revoked successfully")
        
    except Exception as e:
        logger.error(f"Error deleting share: {str(e)}")
        return create_response(500, f"Error: {str(e)}")

