import boto3
import json
import os
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.middleware_factory import lambda_handler_decorator
from botocore.config import Config 
from lambda_middleware import lambda_middleware

# Initialize Powertools
logger = Logger()
tracer = Tracer()

# Initialize AWS S3 client with Signature Version 4
s3_client = boto3.client("s3", config=Config(signature_version="s3v4"))


@lambda_middleware(
    event_bus_name=os.environ.get("EVENT_BUS_NAME", "default-event-bus"),

)
@logger.inject_lambda_context
@tracer.capture_lambda_handler
def lambda_handler(event, context):
    try:
        # Retrieve configuration from the input section if needed
        input_data = event.get("detail", {}).get("outputs", {}).get("input", {})

        # Initialize variables for S3 bucket, key, and media type
        s3_bucket = None
        s3_key = None
        media_type = None
        
        # Try to extract media type from input data
        digital_source_asset = input_data.get("DigitalSourceAsset", {})
        if digital_source_asset:
            media_type = digital_source_asset.get("Type")
            logger.info(f"Found media type in DigitalSourceAsset: {media_type}")
        if media_type == None:
            media_type = event.get("item", {}).get("mediaType", None)
        if media_type == None:
            media_type = event.get("payload", {}).get("mediaType", None)
            
        
        # Extract S3 object information from CheckMediaConvertStatusResult (for video)
        check_media_convert = (
            event.get("detail", {})
            .get("outputs", {})
            .get("CheckMediaConvertStatusResult", {})
        )
        
        if check_media_convert:
            payload = check_media_convert.get("Payload", {})
            proxy_file = payload.get("proxy", {})
            
            s3_bucket = (
                proxy_file.get("StorageInfo", {}).get("PrimaryLocation", {}).get("Bucket")
            )
            s3_key = (
                proxy_file.get("StorageInfo", {})
                .get("PrimaryLocation", {})
                .get("ObjectKey", {})
                .get("FullPath")
            )
            
            logger.info("Found video proxy information in CheckMediaConvertStatusResult")
        
        # If not found, try to extract from ImageThumbnailResult (for image)
        
        if not s3_bucket or not s3_key:
            image_proxy_result = (
                event.get("detail", {})
                .get("outputs", {})
                .get("ImageThumbnailResult", {})
            )

            if image_proxy_result:
                payload = image_proxy_result.get("Payload", {})
                body = payload.get("body", {})

                # s3_bucket = (
                #     body.get("StorageInfo", {}).get("PrimaryLocation", {}).get("Bucket")
                # )
                # s3_key = (
                #     body.get("StorageInfo", {})
                #     .get("PrimaryLocation", {})
                #     .get("ObjectKey", {})
                #     .get("FullPath")
                # )

                s3_bucket = (
                    body.get("bucket")
                )
                s3_key = (
                    body.get("key")
                )

                logger.info("Found image proxy information in ImageProxyResult")

        # ✅ If still not found, check for 'item' key (for audio chunks, etc.)
        if not s3_bucket or not s3_key:
            item = event.get("item", {})
            s3_bucket = item.get("bucket")
            s3_key = item.get("key")
        
        if s3_bucket and s3_key:
            logger.info("Found S3 info in event['item']")

        if not s3_bucket or not s3_key:
            payload = event.get("payload", {})
            s3_bucket = payload.get("bucket")
            s3_key = payload.get("key")
            if s3_bucket and s3_key:
                logger.info("Found S3 info in event['payload']")

        # Validate required parameters
        if not s3_bucket or not s3_key:
            error_message = "Missing required S3 bucket or key information in event"
            logger.error(error_message)
            return {"statusCode": 400, "body": json.dumps({"error": error_message})}

        # Get URL validity duration from configuration (default to 3600 seconds / 1 hour)
        url_validity_duration = int(
            input_data.get("configuration", {}).get("urlValidityDuration", 3600)
        )

        # Validate URL validity duration
        if (
            url_validity_duration <= 0 or url_validity_duration > 604800
        ):  # Max 7 days (AWS limit)
            error_message = "URL validity duration must be between 1 second and 604800 seconds (7 days)"
            logger.error(error_message)
            return {"statusCode": 400, "body": json.dumps({"error": error_message})}

        # Generate pre-signed URL for the file
        presigned_url = s3_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": s3_bucket, "Key": s3_key},
            ExpiresIn=url_validity_duration,
        )

        logger.info(
            f"Generated pre-signed URL for {s3_bucket}/{s3_key} valid for {url_validity_duration} seconds"
        )

        # Return success response with pre-signed URL and media type
        return {
            "presignedUrl": presigned_url,
            "expiresIn": url_validity_duration,
            "bucket": s3_bucket,
            "key": s3_key,
            "mediaType": media_type,
        }

    except Exception as e:
        error_message = f"Error generating pre-signed URL: {str(e)}"
        logger.exception(error_message)
        return {"statusCode": 500, "body": json.dumps({"error": error_message})}
