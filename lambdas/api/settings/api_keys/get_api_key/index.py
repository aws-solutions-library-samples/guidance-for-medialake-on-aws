import json
import os

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.event_handler import APIGatewayRestResolver
from aws_lambda_powertools.utilities.typing import LambdaContext

# Initialize powertools
logger = Logger()
tracer = Tracer()
metrics = Metrics(namespace=os.environ.get("METRICS_NAMESPACE", "MediaLake"))

# Initialize AWS services
dynamodb = boto3.resource("dynamodb")
api_keys_table = dynamodb.Table(os.environ.get("API_KEYS_TABLE"))

# Initialize API Gateway resolver
app = APIGatewayRestResolver()


@app.get("/settings/api-keys/{id}")
@tracer.capture_method
def get_api_key(id: str):
    """
    Get a single API key by ID
    """
    try:
        # Get API key from DynamoDB
        response = api_keys_table.get_item(Key={"id": id})

        if "Item" not in response:
            return {
                "status": "error",
                "message": f"API key with ID {id} not found",
                "data": {},
            }

        item = response["Item"]

        # Filter out sensitive data (secret ARN)
        api_key = {
            "id": item.get("id"),
            "name": item.get("name"),
            "description": item.get("description"),
            "isEnabled": item.get("isEnabled", True),
            "createdAt": item.get("createdAt"),
            "updatedAt": item.get("updatedAt"),
        }

        # Include permissions if present
        if "permissions" in item:
            api_key["permissions"] = json.loads(item["permissions"])

        return {
            "status": "success",
            "message": "API key retrieved successfully",
            "data": api_key,
        }

    except Exception as e:
        logger.exception(f"Error getting API key {id}")
        return {
            "status": "error",
            "message": f"Error getting API key: {str(e)}",
            "data": {},
        }


@logger.inject_lambda_context(correlation_id_path="requestContext.requestId")
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: dict, context: LambdaContext) -> dict:
    """
    Lambda handler for single API key retrieval endpoint
    """
    return app.resolve(event, context)
