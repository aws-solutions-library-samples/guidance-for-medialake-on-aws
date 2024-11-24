from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.event_handler import APIGatewayRestResolver
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.metrics import MetricUnit
from boto3.session import Session
import boto3
from typing import Dict, Any, Optional
import os
import json

# Initialize PowerTools
logger = Logger()
tracer = Tracer()
metrics = Metrics(namespace="MediaLake/Users")

from aws_lambda_powertools.event_handler.api_gateway import CORSConfig

# Configure CORS
cors_config = CORSConfig(
    allow_origin="*",
    allow_headers=[
        "Content-Type",
        "X-Amz-Date",
        "Authorization",
        "X-Api-Key",
        "X-Amz-Security-Token",
    ],
)

# Initialize API Gateway resolver
app = APIGatewayRestResolver(
    serializer=lambda x: json.dumps(x, default=str),
    strip_prefixes=["/api"],
    cors=cors_config,
)

# Initialize AWS clients with X-Ray tracing
session = Session()
cognito = session.client("cognito-idp")

# Constants
USER_POOL_ID = os.environ["USER_POOL_ID"]
MAX_RESULTS = 60  # AWS Cognito limit is 60

# Input schema for validation
INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "queryStringParameters": {
            "type": "object",
            "properties": {
                "pageSize": {"type": "string", "pattern": "^[0-9]+$"},
                "paginationToken": {"type": "string"},
            },
        }
    },
}


@tracer.capture_method
def get_user_attributes(user: Dict[str, Any]) -> Dict[str, Any]:
    """Extract and format user attributes."""
    attributes = {}
    for attr in user.get("Attributes", []):
        attributes[attr["Name"]] = attr["Value"]

    return {
        "username": user.get("Username"),
        "enabled": user.get("Enabled", False),
        "status": user.get("UserStatus"),
        "created": (
            user.get("UserCreateDate").isoformat()
            if user.get("UserCreateDate")
            else None
        ),
        "modified": (
            user.get("UserLastModifiedDate").isoformat()
            if user.get("UserLastModifiedDate")
            else None
        ),
        "email": attributes.get("email"),
        "email_verified": attributes.get("email_verified"),
        "given_name": attributes.get("given_name"),
        "family_name": attributes.get("family_name"),
        "groups": user.get("Groups", []),
    }


@app.get("/settings/users")
@tracer.capture_method
def get_users():
    """Get users from Cognito user pool with pagination support."""
    try:
        # Get query parameters if they exist, otherwise use empty dict
        query_params = app.current_event.query_string_parameters or {}

        # Build Cognito parameters with default values
        params = {
            "UserPoolId": USER_POOL_ID,
        }

        # Handle pagination parameters
        current_page = int(query_params.get("page", "1"))
        page_size = MAX_RESULTS
        if "pageSize" in query_params:
            try:
                page_size = int(query_params["pageSize"])
                page_size = max(1, min(page_size, MAX_RESULTS))
            except (ValueError, TypeError):
                page_size = MAX_RESULTS

        params["Limit"] = page_size

        # Optional: Add pagination token if provided and not empty
        pagination_token = query_params.get("paginationToken")
        if pagination_token and pagination_token.strip():
            params["PaginationToken"] = pagination_token

        logger.info(
            "Request parameters",
            extra={
                "page_size": params.get("Limit"),
                "pagination_token": params.get("PaginationToken"),
                "user_pool_id": USER_POOL_ID,
                "current_page": current_page,
            },
        )

        # Start timing the Cognito API call
        with tracer.provider.in_subsegment("## cognito-list-users") as subsegment:
            response = cognito.list_users(**params)

            logger.info(
                "Cognito response received",
                extra={
                    "users_count": len(response.get("Users", [])),
                    "has_pagination_token": "PaginationToken" in response,
                },
            )

            # Add metadata to the subsegment
            subsegment.put_metadata("page_size", page_size)
            subsegment.put_metadata(
                "has_pagination_token", bool(params.get("PaginationToken"))
            )

        # Process users
        users = [get_user_attributes(user) for user in response.get("Users", [])]

        # Prepare search metadata
        search_metadata = {
            "totalResults": len(users),  # Note: Cognito doesn't provide total count
            "page": current_page,
            "pageSize": page_size,
        }

        # New response structure
        result = {
            "status": "200",
            "message": "ok",
            "data": {"users": users, "searchMetadata": search_metadata},
        }

        # Add pagination token to response if more results exist
        if "PaginationToken" in response:
            result["data"]["nextToken"] = response["PaginationToken"]

        logger.info(
            "Preparing response",
            extra={
                "result_users_count": len(users),
                "search_metadata": search_metadata,
            },
        )

        return {"statusCode": 200, "body": json.dumps(result)}

    except Exception as e:
        logger.exception(
            "Error retrieving users",
            extra={"error_type": type(e).__name__, "error_details": str(e)},
        )
        metrics.add_metric(name="UsersRetrievalError", unit=MetricUnit.Count, value=1)

        # Error response following the same structure
        error_response = {
            "status": "500",
            "message": str(e),
            "data": {
                "searchMetadata": {
                    "totalResults": 0,
                    "page": 1,
                    "pageSize": MAX_RESULTS,
                }
            },
        }

        return {"statusCode": 500, "body": json.dumps(error_response)}


@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """Lambda handler with AWS PowerTools decorators for observability."""
    logger.info(event)
    try:
        return app.resolve(event, context)
    except Exception as e:
        logger.exception("Error processing request")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Internal server error", "message": str(e)}),
        }
