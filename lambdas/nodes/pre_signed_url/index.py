import json
import os

import boto3
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext
from botocore.config import Config
from lambda_middleware import lambda_middleware   # keep if you still use it

# ── Powertools / AWS clients ────────────────────────────────────────────────
logger      = Logger()
tracer      = Tracer()
s3_client   = boto3.client("s3", config=Config(signature_version="s3v4"))

#   • URL validity set in env (seconds). Default = 1 hour, max = 7 days.
URL_VALIDITY_DEFAULT = 3_600
URL_VALIDITY_MAX     = 604_800  # 7 days

@lambda_middleware(  # ← remove this decorator if you’re not using the middleware
    event_bus_name=os.environ.get("EVENT_BUS_NAME", "default-event-bus"),
)
@logger.inject_lambda_context
@tracer.capture_lambda_handler
def lambda_handler(event: dict, context: LambdaContext):
    """
    Generate a pre-signed S3 URL for an object described by the *new* event shape:

    event.payload.assets[*].payload.data.body  # JSON str → {"bucket": "...", "key": "...", ...}
    """
    try:
        # ── 1. Validate & extract the first asset’s body ────────────────────
        assets = event.get("payload", {}).get("assets", [])
        if not assets:
            raise ValueError("event.payload.assets is missing or empty")

        body_str = (
            assets[0]                       # first (and only) pipeline asset
                .get("payload", {})
                .get("data", {})
                .get("body")
        )
        if not body_str:
            raise ValueError("payload.data.body is missing")

        try:
            body = json.loads(body_str)     # {"bucket": "...", "key": "...", "mode": "...", "format": "..."}
        except json.JSONDecodeError as e:
            raise ValueError(f"payload.data.body is not valid JSON: {e}")

        bucket = body.get("bucket")
        key    = body.get("key")
        if not bucket or not key:
            raise ValueError("bucket or key missing in payload.data.body")

        media_type = body.get("format") or body.get("mode")  # PNG / thumbnail / proxy …

        # ── 2. URL validity (env-driven) ───────────────────────────────────
        url_validity = int(os.getenv("URL_VALIDITY", URL_VALIDITY_DEFAULT))
        if url_validity <= 0 or url_validity > URL_VALIDITY_MAX:
            raise ValueError("URL_VALIDITY must be between 1 s and 604 800 s (7 days)")

        # ── 3. Generate pre-signed URL ─────────────────────────────────────
        presigned_url = s3_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=url_validity,
        )
        logger.info(f"Generated URL for s3://{bucket}/{key} valid {url_validity}s")

        return {
            "statusCode"   : 200,
            "presignedUrl" : presigned_url,
            "expiresIn"    : url_validity,
            "bucket"       : bucket,
            "key"          : key,
            "mediaType"    : media_type,
        }

    except Exception as exc:
        logger.exception("Failed to create pre-signed URL")
        return {
            "statusCode": 500,
            "body"      : json.dumps({"error": str(exc)}),
        }
