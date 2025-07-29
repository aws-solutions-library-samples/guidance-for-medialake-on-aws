# lambda_handler.py
import json
import os
from typing import Any, Dict, Tuple

import boto3
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext
from botocore.config import Config
from lambda_middleware import lambda_middleware  # keep if still used

# ── Powertools / logging ────────────────────────────────────────────────────
logger = Logger()
tracer = Tracer()

# ── Constants ──────────────────────────────────────────────────────────────
URL_VALIDITY_DEFAULT = 3_600  # 1 h
URL_VALIDITY_MAX = 604_800  # 7 d

# Signature style & virtual-host addressing are required for every region
_SIGV4_CFG = Config(
    signature_version="s3v4",
    s3={"addressing_style": "virtual"},
)

_ENDPOINT_TMPL = "https://s3.{region}.amazonaws.com"
_S3_CLIENT_CACHE: dict[str, boto3.client] = {}  # {region → client}


# ─────────────────────────────────────────────────────────────────────────────
def _get_s3_client_for_bucket(bucket: str) -> boto3.client:
    """
    Return an S3 client **pinned to the bucket’s actual region**.
    Clients are cached to reuse TCP connections across warm invocations.
    """
    generic = _S3_CLIENT_CACHE.setdefault(
        "us-east-1",
        boto3.client("s3", region_name="us-east-1", config=_SIGV4_CFG),
    )

    try:
        region = (
            generic.get_bucket_location(Bucket=bucket).get("LocationConstraint")
            or "us-east-1"
        )
    except generic.exceptions.NoSuchBucket:
        raise ValueError(f"S3 bucket {bucket!r} does not exist")

    if region not in _S3_CLIENT_CACHE:
        _S3_CLIENT_CACHE[region] = boto3.client(
            "s3",
            region_name=region,
            endpoint_url=_ENDPOINT_TMPL.format(region=region),
            config=_SIGV4_CFG,
        )
    return _S3_CLIENT_CACHE[region]


# ─────────────────────────────────────────────────────────────────────────────
def _pick_representation(assets: list[Dict[str, Any]]) -> Tuple[str, str, str]:
    """
    Apply selection rules on the **first** asset only and return:
    (bucket, key, media_type)
    """
    if not assets:
        raise ValueError("payload.assets is empty")

    reps = assets[0].get("DerivedRepresentations") or []
    if not reps:
        raise ValueError("payload.assets[0].DerivedRepresentations is empty")

    # 1️⃣ Video / Audio proxy
    for rep in reps:
        if rep.get("Purpose") == "proxy" and rep.get("Type") in ("Video", "Audio"):
            loc = rep["StorageInfo"]["PrimaryLocation"]
            return (
                loc["Bucket"],
                loc["ObjectKey"]["FullPath"].lstrip("/"),
                rep.get("Format") or rep.get("Type"),
            )

    # 2️⃣ Image thumbnail
    for rep in reps:
        if rep.get("Purpose") == "thumbnail" and rep.get("Type") == "Image":
            loc = rep["StorageInfo"]["PrimaryLocation"]
            return (
                loc["Bucket"],
                loc["ObjectKey"]["FullPath"].lstrip("/"),
                rep.get("Format") or rep.get("Type"),
            )

    raise ValueError("No representation matched the selection rules")


# ─────────────────────────────────────────────────────────────────────────────
def _extract_location(payload: Dict[str, Any]) -> Tuple[str, str, str]:
    """
    Determine (bucket, key, media_type) using *priority* order:

    1. payload.data.{bucket,key,mediaType}
    2. payload.map.item.{bucket,key,mediaType}
    3. First asset’s DerivedRepresentations (legacy rule set)
    """
    # 1️⃣  Direct “data” structure
    data = payload.get("data") or {}
    if data.get("bucket") and data.get("key"):
        return data["bucket"], data["key"].lstrip("/"), data.get("mediaType", "")

    # 2️⃣  Mapper output
    mapper_item = (payload.get("map") or {}).get("item", {})
    if mapper_item.get("bucket") and mapper_item.get("key"):
        return (
            mapper_item["bucket"],
            mapper_item["key"].lstrip("/"),
            mapper_item.get("mediaType", ""),
        )

    # 3️⃣  Legacy representation-selection
    return _pick_representation(payload.get("assets", []))


# ─────────────────────────────────────────────────────────────────────────────
@lambda_middleware(  # remove if not needed
    event_bus_name=os.getenv("EVENT_BUS_NAME", "default-event-bus"),
)
@logger.inject_lambda_context
@tracer.capture_lambda_handler
def lambda_handler(event: Dict[str, Any], context: LambdaContext):
    """
    Lambda entry – generate a pre-signed URL for the selected object.
    The URL is signed in the bucket’s own region, preventing
    SignatureDoesNotMatch errors outside us-east-1.
    """
    logger.info("Incoming event", extra={"event": event})

    try:
        # ── 1. Extract bucket / key / mediaType ────────────────────────────
        bucket, key, media_type = _extract_location(event.get("payload", {}))

        # ── 2. URL validity (env-driven, capped) ──────────────────────────
        url_validity = int(os.getenv("URL_VALIDITY", URL_VALIDITY_DEFAULT))
        if not 0 < url_validity <= URL_VALIDITY_MAX:
            raise ValueError(
                f"URL_VALIDITY must be between 1 s and {URL_VALIDITY_MAX} s"
            )

        # ── 3. Region-aware S3 client & pre-signed URL ────────────────────
        s3_client = _get_s3_client_for_bucket(bucket)
        presigned_url = s3_client.generate_presigned_url(
            ClientMethod="get_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=url_validity,
        )

        logger.info(
            "Generated URL for s3://%s/%s (region %s) valid %ss",
            bucket,
            key,
            s3_client.meta.region_name,
            url_validity,
        )

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
