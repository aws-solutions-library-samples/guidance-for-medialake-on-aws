import base64
import json
import os
from typing import Any, Dict, Optional

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.utilities.data_classes import APIGatewayProxyEvent
from aws_lambda_powertools.utilities.parser import parse_qs
from aws_lambda_powertools.utilities.typing import LambdaContext
from boto3.dynamodb.conditions import Key
from pydantic import BaseModel, Field, validator

from config import global_prefix

# Initialize AWS X-Ray, metrics, and logger
tracer = Tracer(service="asset-service")
metrics = Metrics(namespace=f"{global_prefix}-asset-service", service="asset-api")
logger = Logger(service="asset-api", level=os.getenv("LOG_LEVEL", "WARNING"))

# Initialize DynamoDB
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.getenv("ASSET_TABLE_NAME"))

MAX_ITEMS = 250


class QueryParams(BaseModel):
    limit: Optional[int] = Field(default=10, ge=1, le=50)
    page: Optional[int] = Field(default=1, ge=1)
    sort: Optional[str] = Field(default="timestamp:desc")
    filter: Optional[str] = None
    pagination_token: Optional[str] = None

    @validator("sort")
    def validate_sort(cls, v):
        if v and v not in ["timestamp:desc", "timestamp:asc"]:
            raise ValueError("Invalid sort parameter")
        return v


class APIError(Exception):
    def __init__(self, message: str, status_code: int):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


@tracer.capture_method
def encode_pagination_token(last_evaluated_key: Dict) -> str:
    """Encode the LastEvaluatedKey for safe transmission."""
    return base64.b64encode(json.dumps(last_evaluated_key).encode()).decode()


@tracer.capture_method
def decode_pagination_token(token: str) -> Dict:
    """Decode the pagination token back into LastEvaluatedKey."""
    try:
        return json.loads(base64.b64decode(token.encode()).decode())
    except Exception as e:
        logger.error(f"Invalid pagination token: {str(e)}")
        raise APIError("Invalid pagination token provided", 400)


@tracer.capture_method
def build_query_params(params: QueryParams) -> Dict[str, Any]:
    """Build DynamoDB query parameters based on request parameters."""
    key_condition = Key("DigitalSourceAsset.ID").begins_with("asset:img:")

    query_params = {
        "IndexName": os.getenv("AssetIDIndex"),
        "KeyConditionExpression": key_condition,
        "Limit": min(params.limit, MAX_ITEMS),
        "ScanIndexForward": params.sort != "timestamp:desc",
    }

    if params.pagination_token:
        try:
            query_params["ExclusiveStartKey"] = decode_pagination_token(
                params.pagination_token
            )
        except APIError as e:
            raise e

    if params.filter:
        logger.debug(f"Applying filter: {params.filter}")
        # Implement your filter logic here based on your requirements
        # query_params['FilterExpression'] = ...

    return query_params


@tracer.capture_method
def build_error_response(error: Exception, status_code: int) -> Dict[str, Any]:
    """Build standardized error response."""
    runtime_id = (
        context.aws_request_id if hasattr(context, "aws_request_id") else "UNKNOWN"
    )

    if isinstance(error, APIError):
        message = f"{error.message} (Runtime ID: {runtime_id})"
    else:
        message = f"An unexpected error occurred. Please try again later. (Runtime ID: {runtime_id})"

    return {"statusCode": status_code, "body": {"status": "error", "message": message}}


@metrics.log_metrics(capture_cold_start_metric=True)
@tracer.capture_lambda_handler
@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
def lambda_handler(
    event: APIGatewayProxyEvent, context: LambdaContext
) -> Dict[str, Any]:
    try:
        # Parse and validate query parameters
        raw_params = parse_qs(event.get("queryStringParameters") or {})
        query_params = QueryParams(**raw_params)

        logger.debug(f"Processed query parameters: {query_params.dict()}")

        # Build and execute query
        dynamo_query_params = build_query_params(query_params)

        logger.info(f"Executing DynamoDB query with params: {dynamo_query_params}")
        response = table.query(**dynamo_query_params)

        # Process results
        items = response.get("Items", [])
        last_evaluated_key = response.get("LastEvaluatedKey")

        # Generate pagination token if there are more results
        next_token = (
            encode_pagination_token(last_evaluated_key) if last_evaluated_key else None
        )

        metrics.add_metric(name="AssetsRetrieved", value=len(items), unit="Count")

        return {
            "statusCode": 200,
            "body": {
                "status": "success",
                "message": "Assets retrieved successfully",
                "data": {
                    "assets": items,
                    "pagination": {
                        "total": len(items),
                        "has_more": last_evaluated_key is not None,
                        "next_token": next_token,
                    },
                },
            },
        }

    except APIError as e:
        logger.warning(f"API Error: {str(e)}", exc_info=True)
        metrics.add_metric(name="AssetRetrievalClientErrors", value=1, unit="Count")
        return build_error_response(e, e.status_code)

    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        metrics.add_metric(name="AssetRetrievalServerErrors", value=1, unit="Count")
        return build_error_response(e, 500)
