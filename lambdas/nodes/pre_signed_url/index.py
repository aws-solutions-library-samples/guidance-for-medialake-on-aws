# lambda_handler.py
import json
import os
from typing import Any, Dict, Tuple

import boto3
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext
from botocore.config import Config
from lambda_middleware import lambda_middleware  # keep if still used

# ── Powertools / AWS clients ────────────────────────────────────────────────
logger    = Logger()
tracer    = Tracer()
s3_client = boto3.client("s3", config=Config(signature_version="s3v4"))

URL_VALIDITY_DEFAULT = 3_600        # 1 h
URL_VALIDITY_MAX     = 604_800      # 7 d


def _pick_representation(assets: list[Dict[str, Any]]
                          ) -> Tuple[str, str, str]:
    """
    Apply selection rules on the FIRST asset only.

    Returns (bucket, key, media_type)
    """
    if not assets:
        raise ValueError("payload.assets is empty")

    reps = assets[0].get("DerivedRepresentations") or []
    if not reps:
        raise ValueError("payload.assets[0].DerivedRepresentations is empty")

    # 1️⃣ search for Video/Audio proxy
    for rep in reps:
        if rep.get("Purpose") == "proxy" and rep.get("Type") in ("Video", "Audio"):
            loc = rep["StorageInfo"]["PrimaryLocation"]
            bucket = loc["Bucket"]
            key    = loc["ObjectKey"]["FullPath"]
            media  = rep.get("Format") or rep.get("Type")
            return bucket, key, media

    # 2️⃣ search for Image thumbnail
    for rep in reps:
        if rep.get("Purpose") == "thumbnail" and rep.get("Type") == "Image":
            loc = rep["StorageInfo"]["PrimaryLocation"]
            bucket = loc["Bucket"]
            key    = loc["ObjectKey"]["FullPath"]
            media  = rep.get("Format") or rep.get("Type")
            return bucket, key, media

    raise ValueError("No representation matched the selection rules")


@lambda_middleware(  # remove if not needed
    event_bus_name=os.getenv("EVENT_BUS_NAME", "default-event-bus"),
)
@logger.inject_lambda_context
@tracer.capture_lambda_handler
def lambda_handler(event: Dict[str, Any], context: LambdaContext):
    """
    Generate a pre-signed S3 URL for the *selected* representation in the event.
    """
    logger.debug("Incoming event: %s", json.dumps(event))

    try:
        # ── 1. Extract bucket/key/mediaType from the new shape ────────────
        bucket, key, media_type = _pick_representation(
            event.get("payload", {}).get("assets", [])
        )

        # ── 2. Determine URL validity (env-driven, capped) ───────────────
        url_validity = int(os.getenv("URL_VALIDITY", URL_VALIDITY_DEFAULT))
        if not 0 < url_validity <= URL_VALIDITY_MAX:
            raise ValueError(
                f"URL_VALIDITY must be between 1 s and {URL_VALIDITY_MAX} s"
            )

        # ── 3. Generate the URL ──────────────────────────────────────────
        presigned_url = s3_client.generate_presigned_url(
            ClientMethod="get_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=url_validity,
        )
        logger.info("Generated URL for s3://%s/%s valid %ss", bucket, key, url_validity)

        return {
            "statusCode": 200,
            "presignedUrl": presigned_url,
            "expiresIn": url_validity,
            "bucket": bucket,
            "key": key,
            "mediaType": media_type,
        }

    except Exception as exc:
        logger.exception("Failed to create pre-signed URL")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(exc)}),
        }
