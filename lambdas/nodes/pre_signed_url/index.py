import boto3
import json
import os
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext
from botocore.config import Config  # Import Config to set signature version

# Initialize Powertools
logger = Logger()
tracer = Tracer()

# Initialize AWS S3 client with Signature Version 4
s3_client = boto3.client("s3", config=Config(signature_version="s3v4"))


@logger.inject_lambda_context
@tracer.capture_lambda_handler
def lambda_handler(event, context):
    try:
        # Retrieve configuration from the input section if needed
        input_data = event.get("detail", {}).get("outputs", {}).get("input", {})

        # Extract S3 object information from CheckMediaConvertStatusResult
        check_media_convert = (
            event.get("detail", {})
            .get("outputs", {})
            .get("CheckMediaConvertStatusResult", {})
        )
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

        # Validate required parameters
        if not s3_bucket or not s3_key:
            error_message = "Missing required S3 bucket or key information in CheckMediaConvertStatusResult"
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

        # Generate pre-signed URL for the file from CheckMediaConvertStatusResult
        presigned_url = s3_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": s3_bucket, "Key": s3_key},
            ExpiresIn=url_validity_duration,
        )

        logger.info(
            f"Generated pre-signed URL for {s3_bucket}/{s3_key} valid for {url_validity_duration} seconds"
        )

        # Return success response with pre-signed URL
        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "message": "Pre-signed URL generated successfully",
                    "presignedUrl": presigned_url,
                    "expiresIn": url_validity_duration,
                    "bucket": s3_bucket,
                    "key": s3_key,
                }
            ),
        }

    except Exception as e:
        error_message = f"Error generating pre-signed URL: {str(e)}"
        logger.exception(error_message)
        return {"statusCode": 500, "body": json.dumps({"error": error_message})}
