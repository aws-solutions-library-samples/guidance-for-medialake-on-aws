from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.utilities.data_classes import APIGatewayProxyEvent
from typing import Dict, Any, Optional
import os
import boto3
import json
from botocore.config import Config
from pydantic import BaseModel, Field

# Initialize AWS X-Ray, metrics, and logger
tracer = Tracer(service="asset-service")
metrics = Metrics(namespace="presigned_url-service")
logger = Logger(service="asset-api", level=os.getenv("LOG_LEVEL", "WARNING"))

# Initialize DynamoDB and S3
dynamodb = boto3.resource("dynamodb")
# Configure S3 client with Signature Version 4 for KMS compatibility
s3_config = Config(signature_version='s3v4')
s3_client = boto3.client("s3", config=s3_config)
table = dynamodb.Table(os.getenv("MEDIALAKE_ASSET_TABLE"))

DEFAULT_EXPIRATION = 3600  # 1 hour in seconds


class RequestBody(BaseModel):
    inventory_id: str
    expiration_time: Optional[int] = Field(
        default=DEFAULT_EXPIRATION, ge=60, le=604800
    )  # Between 1 minute and 7 days
    purpose: Optional[str] = None  # Optional purpose to specify which representation to use


class APIError(Exception):
    def __init__(self, message: str, status_code: int):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


@tracer.capture_method
def get_asset_details(inventory_id: str) -> Dict[str, Any]:
    """Retrieve asset details from DynamoDB."""
    try:
        response = table.get_item(Key={"InventoryID": inventory_id})
        if "Item" not in response:
            raise APIError(f"Asset not found with ID: {inventory_id}", 404)
        return response["Item"]
    except Exception as e:
        logger.error(f"Error retrieving asset details: {str(e)}")
        raise APIError("Error retrieving asset details", 500)


@tracer.capture_method
def generate_presigned_url(bucket: str, key: str, expiration: int) -> str:
    """Generate a presigned URL for the S3 object."""
    try:
        url = s3_client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": bucket,
                "Key": key,
                "ResponseContentDisposition": f'attachment; filename="{key.split("/")[-1]}"',
            },
            ExpiresIn=expiration,
        )
        return url
    except Exception as e:
        logger.error(f"Error generating presigned URL: {str(e)}")
        raise APIError("Error generating presigned URL", 500)


@metrics.log_metrics(capture_cold_start_metric=True)
@tracer.capture_lambda_handler
@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
def lambda_handler(
    event: APIGatewayProxyEvent, context: LambdaContext
) -> Dict[str, Any]:
    try:
        # print(json.dumps(event))
        # Parse and validate request body
        body = json.loads(event.get("body", "{}"))
        request = RequestBody(**body)

        # Get asset details
        asset = get_asset_details(request.inventory_id)

        # Determine which representation to use based on purpose
        purpose = request.purpose
        
        if purpose and purpose.lower() != "original" and purpose.lower() != "master":
            # Look for a derived representation matching the purpose
            derived_representations = asset.get("DerivedRepresentations", [])
            matching_representation = None
            
            for rep in derived_representations:
                if rep.get("Purpose", "").lower() == purpose.lower():
                    matching_representation = rep
                    break
            
            if matching_representation:
                logger.info(f"Using derived representation with purpose: {purpose}")
                storage_info = matching_representation.get("StorageInfo", {})
            else:
                logger.info(f"No derived representation found for purpose: {purpose}, falling back to main representation")
                storage_info = (
                    asset.get("DigitalSourceAsset", {})
                    .get("MainRepresentation", {})
                    .get("StorageInfo", {})
                )
        else:
            # Use main representation
            logger.info("Using main representation")
            storage_info = (
                asset.get("DigitalSourceAsset", {})
                .get("MainRepresentation", {})
                .get("StorageInfo", {})
            )
            
        location = storage_info.get("PrimaryLocation", {})

        bucket = location.get("Bucket")
        key = location.get("ObjectKey", {}).get("FullPath")

        if not bucket or not key:
            raise APIError("Invalid asset storage information", 400)

        # Generate presigned URL
        presigned_url = generate_presigned_url(bucket, key, request.expiration_time)

        metrics.add_metric(name="PresignedUrlGenerated", value=1, unit="Count")

        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "status": "success",
                    "message": "Presigned URL generated successfully",
                    "data": {
                        "presigned_url": presigned_url,
                        "expires_in": request.expiration_time,
                        "asset_id": request.inventory_id,
                    },
                }
            ),
        }

    except APIError as e:
        logger.warning(f"API Error: {str(e)}", exc_info=True)
        metrics.add_metric(
            name="PresignedUrlGenerationClientErrors", value=1, unit="Count"
        )
        return {
            "statusCode": e.status_code,
            "body": json.dumps({"status": "error", "message": str(e)}),
        }

    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        metrics.add_metric(
            name="PresignedUrlGenerationServerErrors", value=1, unit="Count"
        )
        return {
            "statusCode": 500,
            "body": json.dumps(
                {"status": "error", "message": "An unexpected error occurred"}
            ),
        }
