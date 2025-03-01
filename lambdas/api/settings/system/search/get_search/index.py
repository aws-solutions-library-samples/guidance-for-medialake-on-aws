import json
import os
import boto3
from aws_lambda_powertools import Logger, Tracer, Metrics
from aws_lambda_powertools.event_handler import APIGatewayRestResolver
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.utilities.data_classes import APIGatewayProxyEvent
from aws_lambda_powertools.utilities.parameters import get_secret

# Initialize powertools
logger = Logger()
tracer = Tracer()
metrics = Metrics(namespace=os.environ.get("METRICS_NAMESPACE", "MediaLake"))

# Initialize AWS services
dynamodb = boto3.resource("dynamodb")
system_settings_table = dynamodb.Table(os.environ.get("SYSTEM_SETTINGS_TABLE"))

# Initialize API Gateway resolver
app = APIGatewayRestResolver()

@app.get("/settings/system/search")
@tracer.capture_method
def get_search_provider():
    """
    Get search provider configuration
    """
    try:
        # Get search provider settings
        response = system_settings_table.get_item(
            Key={
                "PK": "SYSTEM_SETTINGS",
                "SK": "SEARCH_PROVIDER"
            }
        )
        
        search_provider = response.get("Item", {})
        
        # Remove DynamoDB specific attributes
        if search_provider:
            search_provider.pop("PK", None)
            search_provider.pop("SK", None)
            
            # Don't expose the secret ARN in the response
            search_provider.pop("secretArn", None)
            
            # Add isConfigured flag if secretArn exists in the original item
            search_provider["isConfigured"] = "secretArn" in response.get("Item", {})
        
        # Prepare response
        return {
            "status": "success",
            "message": "Search provider retrieved successfully",
            "data": {
                "searchProvider": search_provider if search_provider else {
                    "name": "Twelve Labs",
                    "type": "twelvelabs",
                    "isConfigured": False,
                    "isEnabled": False
                }
            }
        }
    except Exception as e:
        logger.exception("Error retrieving search provider")
        return {
            "status": "error",
            "message": f"Error retrieving search provider: {str(e)}",
            "data": {}
        }

@logger.inject_lambda_context(correlation_id_path="requestContext.requestId")
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: dict, context: LambdaContext) -> dict:
    """
    Lambda handler for search provider API
    """
    # Verify origin if needed
    # secret_value = get_secret(os.environ.get("X_ORIGIN_VERIFY_SECRET_ARN"))
    
    return app.resolve(event, context) 