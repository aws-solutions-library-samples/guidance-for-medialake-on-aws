"""
Asset Details Lambda Handler

This Lambda function retrieves detailed asset information from DynamoDB based on asset ID.
It implements AWS best practices including:
- Structured logging with AWS Lambda Powertools
- Tracing with AWS X-Ray
- Input validation and error handling
- Metrics and monitoring
- Security best practices
- Performance optimization through global clients
"""

import json
import os
from http import HTTPStatus
from typing import Any, Dict, List, Optional

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.data_classes import APIGatewayProxyEvent
from aws_lambda_powertools.utilities.typing import LambdaContext
from botocore.exceptions import ClientError
from opensearchpy import (
    NotFoundError,
    OpenSearch,
    RequestError,
    RequestsAWSV4SignerAuth,
    RequestsHttpConnection,
)
from utils import generate_presigned_url, replace_binary_data

# Initialize AWS Lambda Powertools
logger = Logger(service="asset-details-service")
tracer = Tracer(service="asset-details-service")
metrics = Metrics(namespace="AssetDetailsService", service="asset-details-service")

# Initialize AWS clients with X-Ray tracing
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["MEDIALAKE_ASSET_TABLE"])


# Initialize OpenSearch client
def get_opensearch_client() -> OpenSearch:
    """Create and return an OpenSearch client with optimized settings."""
    host = os.environ["OPENSEARCH_ENDPOINT"].replace("https://", "")
    region = os.environ["AWS_REGION"]
    service_scope = os.environ["SCOPE"]

    auth = RequestsAWSV4SignerAuth(
        boto3.Session().get_credentials(), region, service_scope
    )

    return OpenSearch(
        hosts=[{"host": host, "port": 443}],
        http_auth=auth,
        use_ssl=True,
        verify_certs=True,
        connection_class=RequestsHttpConnection,
        region=region,
        timeout=30,
        max_retries=2,
        retry_on_timeout=True,
        maxsize=10,
    )


class AssetDetailsError(Exception):
    """Custom exception for asset retrieval errors"""

    def __init__(
        self, message: str, status_code: int = HTTPStatus.INTERNAL_SERVER_ERROR
    ):
        super().__init__(message)
        self.status_code = status_code


@tracer.capture_method
def validate_asset_id(asset_id: Optional[str]) -> None:
    """
    Validates the asset ID format.

    Args:
        asset_id: The asset ID to validate

    Raises:
        AssetDetailsError: If the asset ID is invalid
    """
    if not asset_id or not isinstance(asset_id, str):
        raise AssetDetailsError("Invalid or missing asset ID", HTTPStatus.BAD_REQUEST)


@tracer.capture_method
def get_asset_details(inventory_id: str) -> Dict[str, Any]:
    """
    Retrieves asset details from DynamoDB.

    Args:
        inventory_id: The inventory ID of the asset

    Returns:
        Dict containing the asset details

    Raises:
        AssetDetailsError: If the retrieval fails or asset not found
    """
    try:
        response = table.get_item(
            Key={"InventoryID": inventory_id},
            ConsistentRead=True,  # Ensure we get the latest data
        )
        print(response)

        if "Item" not in response:
            raise AssetDetailsError(
                f"Asset with ID {inventory_id} not found", HTTPStatus.NOT_FOUND
            )

        asset_data = response["Item"]

        # Log successful retrieval (excluding sensitive data)
        logger.info(
            "Asset details retrieved successfully",
            extra={
                "inventory_id": inventory_id,
                "asset_type": asset_data.get("assetType"),
                # "retrieval_timestamp": tracer.get_timestamp(),
            },
        )

        # Record successful retrieval metric
        metrics.add_metric(name="AssetRetrievals", unit=MetricUnit.Count, value=1)

        return asset_data

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        error_message = e.response["Error"]["Message"]

        logger.error(
            f"DynamoDB error: {error_message}",
            extra={"error_code": error_code, "inventory_id": inventory_id},
        )

        metrics.add_metric(name="AssetRetrievalErrors", unit=MetricUnit.Count, value=1)

        raise AssetDetailsError(f"Failed to retrieve asset details: {error_message}")


def create_response(
    status_code: int, message: str, data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Creates a standardized API response.

    Args:
        status_code: HTTP status code
        message: Response message
        data: Optional response data

    Returns:
        Dict containing the API Gateway response
    """
    body = {
        "status": "success" if status_code < 400 else "error",
        "message": message,
        "data": data or {},
    }

    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",  # Configure as needed
            "Access-Control-Allow-Credentials": True,
            "Cache-Control": "no-cache, no-store, must-revalidate",
        },
        "body": json.dumps(body, default=str),
    }


@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(
    event: APIGatewayProxyEvent, context: LambdaContext
) -> Dict[str, Any]:
    """Lambda handler for getting asset details."""
    try:
        # Extract and validate asset ID
        asset_id = event.get("pathParameters", {}).get("id")
        if not asset_id:
            raise AssetDetailsError("Missing asset ID", HTTPStatus.BAD_REQUEST)

        # Get asset details
        asset_data = get_asset_details(asset_id)

        # Add any additional metadata or computed fields
        enriched_asset = enrich_asset_data(asset_data)
        print(enriched_asset)

        return create_response(
            HTTPStatus.OK,
            "Asset details retrieved successfully",
            {"asset": enriched_asset},
        )

    except Exception as e:
        error_message = (
            str(e)
            if isinstance(str(e), str)
            else e.args[0] if e.args else "Unknown error"
        )
        logger.error(
            f"Unexpected error during asset retrieval: {error_message}",
            extra={"asset_id": asset_id},
        )
        metrics.add_metric(name="UnexpectedErrors", unit=MetricUnit.Count, value=1)
        return create_response(
            HTTPStatus.INTERNAL_SERVER_ERROR, "Internal server error"
        )


def get_url_for_purpose(asset, purpose):
    for rep in asset.get("DerivedRepresentations", []):
        if rep.get("Purpose") == purpose:
            storage = rep.get("StorageInfo", {}).get("PrimaryLocation", {})
            if storage.get("StorageType") == "s3":
                return generate_presigned_url(
                    bucket=storage["Bucket"], key=storage["ObjectKey"]["FullPath"]
                )
    return None


@tracer.capture_method
def get_asset_clips(asset_id: str) -> List[Dict[str, Any]]:
    """
    Retrieve clips for a specific asset from OpenSearch.

    Args:
        asset_id: The ID of the asset to retrieve clips for

    Returns:
        List of clip objects
    """
    try:
        client = get_opensearch_client()
        index_name = os.environ["OPENSEARCH_INDEX"]

        # Query for clips associated with this asset
        query = {
            "query": {
                "bool": {
                    "must": [
                        {"term": {"DigitalSourceAsset.ID": asset_id}},
                        {"term": {"embedding_scope": "clip"}},
                    ]
                }
            },
            "size": 100,  # Limit to 100 clips per asset
            "_source": {"excludes": ["embedding"]},
            "sort": [{"start_timecode": {"order": "asc"}}],  # Sort by start time
        }

        response = client.search(body=query, index=index_name)

        clips = []
        for hit in response["hits"]["hits"]:
            source = hit["_source"]
            clip = {
                "score": hit["_score"],
                "start_timecode": source.get("start_timecode"),
                "end_timecode": source.get("end_timecode"),
                "timestamp": source.get("timestamp"),
                "type": source.get("type"),
            }

            # Add any additional fields that might be useful
            for key, value in source.items():
                if key not in ["DigitalSourceAsset"] and key not in clip:
                    clip[key] = value

            clips.append(clip)

        logger.info(f"Retrieved {len(clips)} clips for asset {asset_id}")
        return clips

    except (RequestError, NotFoundError) as e:
        logger.warning(f"OpenSearch error retrieving clips: {str(e)}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error retrieving clips: {str(e)}")
        return []


@tracer.capture_method
def enrich_asset_data(asset: Dict[str, Any]) -> Dict[str, Any]:
    """Enrich asset data with additional computed fields and handle binary data."""
    try:
        thumbnail_url = get_url_for_purpose(asset, "thumbnail")
        proxy_url = get_url_for_purpose(asset, "proxy")

        # Add URLs to their respective DerivedRepresentations
        for rep in asset.get("DerivedRepresentations", []):
            if rep.get("Purpose") == "thumbnail" and thumbnail_url:
                rep["URL"] = thumbnail_url
            elif rep.get("Purpose") == "proxy" and proxy_url:
                rep["URL"] = proxy_url

        # Add computed fields
        asset["DigitalSourceAsset"]["ComputedFields"] = {
            "TotalSize": sum(
                rep["StorageInfo"]["PrimaryLocation"]["FileInfo"].get("Size", 0)
                for rep in asset.get("DerivedRepresentations", [])
            )
            + asset["DigitalSourceAsset"]["MainRepresentation"]["StorageInfo"][
                "PrimaryLocation"
            ]["FileInfo"].get("Size", 0),
            "LastModified": asset["DigitalSourceAsset"].get(
                "UpdateDate", asset["DigitalSourceAsset"]["CreateDate"]
            ),
            # Add other computed fields as needed
        }

        # Replace binary data with "BINARY DATA" text
        asset = replace_binary_data(asset)

        # Get clips for this asset if it's a video or audio type
        asset_type = asset.get("DigitalSourceAsset", {}).get("Type", "").lower()
        if asset_type in ["video", "audio"]:
            try:
                asset_id = asset.get("DigitalSourceAsset", {}).get("ID")
                if asset_id:
                    clips = get_asset_clips(asset_id)
                    if clips:
                        asset["clips"] = clips
                        logger.info(f"Added {len(clips)} clips to asset response")
            except Exception as e:
                logger.error(f"Error adding clips to asset: {str(e)}")

        return asset
    except Exception as e:
        logger.error(f"Error enriching asset data: {str(e)}")
        return asset
