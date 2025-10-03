import base64
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
API_KEYS_TABLE = os.environ.get("API_KEYS_TABLE")
if not API_KEYS_TABLE:
    raise ValueError("API_KEYS_TABLE environment variable is required")
api_keys_table = dynamodb.Table(API_KEYS_TABLE)

# Initialize API Gateway resolver
app = APIGatewayRestResolver()


@app.get("/settings/api-keys")
@tracer.capture_method
def list_api_keys():
    """
    List API keys with pagination support
    Query parameters:
    - limit: Number of items to return (default: 20, max: 100)
    - nextToken: Pagination token for next page
    """
    try:
        # Parse query parameters
        query_params = app.current_event.query_string_parameters or {}
        limit = int(query_params.get("limit", 20))
        next_token = query_params.get("nextToken")

        # Validate limit parameter
        if limit < 1:
            limit = 20
        elif limit > 100:
            limit = 100

        # Prepare scan parameters
        scan_params = {"Limit": limit}

        # Handle pagination token
        if next_token:
            try:
                # Decode the pagination token
                decoded_token = base64.b64decode(next_token).decode("utf-8")
                exclusive_start_key = json.loads(decoded_token)
                scan_params["ExclusiveStartKey"] = exclusive_start_key
            except (ValueError, json.JSONDecodeError, Exception) as e:
                logger.warning(f"Invalid pagination token: {e}")
                return {
                    "status": "error",
                    "message": "Invalid pagination token",
                    "data": {},
                }

        # Scan the API keys table with pagination
        response = api_keys_table.scan(**scan_params)

        # Extract items from response
        items = response.get("Items", [])

        # Filter out sensitive data (secret ARNs) from the response
        api_keys = []
        for item in items:
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
            api_keys.append(api_key)

        # Sort by createdAt date (newest first)
        api_keys.sort(key=lambda x: x.get("createdAt", ""), reverse=True)

        # Prepare response data
        response_data = {
            "apiKeys": api_keys,
            "count": len(api_keys),
            "pagination": {"limit": limit, "hasMore": "LastEvaluatedKey" in response},
        }

        # Add next token if there are more items
        if "LastEvaluatedKey" in response:
            # Encode the LastEvaluatedKey as a pagination token
            token_data = json.dumps(response["LastEvaluatedKey"], default=str)
            next_token = base64.b64encode(token_data.encode("utf-8")).decode("utf-8")
            response_data["pagination"]["nextToken"] = next_token

        return {
            "status": "success",
            "message": "API keys retrieved successfully",
            "data": response_data,
        }

    except Exception as e:
        logger.exception("Error listing API keys")
        return {
            "status": "error",
            "message": f"Error listing API keys: {str(e)}",
            "data": {},
        }


@logger.inject_lambda_context(correlation_id_path="requestContext.requestId")
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: dict, context: LambdaContext) -> dict:
    """
    Lambda handler for API keys list endpoint
    """
    return app.resolve(event, context)
