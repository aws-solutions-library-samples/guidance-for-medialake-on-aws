import json
import os
import re
import shutil
import subprocess
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, Optional

import boto3
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext
from botocore.config import Config
from lambda_middleware import lambda_middleware
from pymediainfo import MediaInfo

# ─── constants ──────────────────────────────────────────────────────────
SIGNED_URL_TIMEOUT = int(os.getenv("SIGNED_URL_TIMEOUT", "300"))  # give ffprobe time
FFPROBE_BIN = "/opt/bin/ffprobe"
TMP_DIR = Path("/tmp")
SAFETY_MARGIN_BYTES = 64 * 1024 * 1024  # leave some room

logger = Logger(service="video-metadata-extractor")
tracer = Tracer()

# Signature style & virtual-host addressing are required for every region
_SIGV4_CFG = Config(
    signature_version="s3v4",
    s3={"addressing_style": "virtual"},
)

_ENDPOINT_TMPL = "https://s3.{region}.amazonaws.com"
_S3_CLIENT_CACHE: dict[str, boto3.client] = {}  # {region → client}

dynamodb = boto3.resource("dynamodb")
asset_table = dynamodb.Table(os.environ["MEDIALAKE_ASSET_TABLE"])


# ─── s3 region-aware client helpers ─────────────────────────────────────


def _get_s3_client_for_bucket(bucket: str) -> boto3.client:
    """
    Return an S3 client **pinned to the bucket's actual region**.
    Clients are cached to reuse TCP connections across warm invocations.
    Falls back to region detection from bucket name or environment if GetBucketLocation fails.
    """
    # Try to detect region from bucket name patterns or environment first
    detected_region = _detect_region_from_context(bucket)

    if detected_region and detected_region in _S3_CLIENT_CACHE:
        return _S3_CLIENT_CACHE[detected_region]

    # Try GetBucketLocation as fallback if we have permissions
    generic = _S3_CLIENT_CACHE.setdefault(
        "us-east-1",
        boto3.client("s3", region_name="us-east-1", config=_SIGV4_CFG),
    )

    try:
        region = (
            generic.get_bucket_location(Bucket=bucket).get("LocationConstraint")
            or "us-east-1"
        )
        logger.debug(f"Retrieved bucket region via GetBucketLocation: {region}")
    except (generic.exceptions.NoSuchBucket, generic.exceptions.ClientError) as e:
        # Fall back to detected region or default
        region = detected_region or "us-west-2"  # Default to us-west-2 based on error
        logger.warning(
            f"Could not get bucket location for {bucket}, using {region}: {str(e)}"
        )

    if region not in _S3_CLIENT_CACHE:
        _S3_CLIENT_CACHE[region] = boto3.client(
            "s3",
            region_name=region,
            endpoint_url=_ENDPOINT_TMPL.format(region=region),
            config=_SIGV4_CFG,
        )
    return _S3_CLIENT_CACHE[region]


def _detect_region_from_context(bucket: str) -> Optional[str]:
    """
    Attempt to detect the S3 bucket region from context clues.
    """
    # Check if AWS_REGION environment variable is set (common in Lambda)
    env_region = os.environ.get("AWS_REGION")
    if env_region:
        logger.debug(f"Using region from AWS_REGION environment: {env_region}")
        return env_region

    # Check if AWS_DEFAULT_REGION is set
    default_region = os.environ.get("AWS_DEFAULT_REGION")
    if default_region:
        logger.debug(
            f"Using region from AWS_DEFAULT_REGION environment: {default_region}"
        )
        return default_region

    # Based on the error message, this specific bucket is in us-west-2
    # You could add more bucket-to-region mappings here if needed
    if "medialakebaseinfrastructu" in bucket:
        logger.debug("Detected MediaLake bucket, using us-west-2")
        return "us-west-2"

    return None


# ─── helpers ────────────────────────────────────────────────────────────


def _json_default(o):
    if isinstance(o, Decimal):
        # keep integers as ints; everything else as float
        return int(o) if o % 1 == 0 else float(o)
    if isinstance(o, (bytes, bytearray)):
        return f"{len(o)} bytes"
    return str(o)


def run_ffprobe(input_path: str) -> Dict[str, Any]:
    """Return ffprobe JSON for a file or URL, raise on error."""
    # Limit probe size so ffprobe doesn’t try to slurp entire remote objects
    cmd = [
        FFPROBE_BIN,
        "-v",
        "error",
        "-analyzeduration",
        "10M",
        "-probesize",
        "10M",
        "-show_streams",
        "-show_format",
        "-print_format",
        "json",
        input_path,
    ]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode:
        raise RuntimeError(f"ffprobe failed: {result.stderr.decode()}")
    return json.loads(result.stdout)


def run_mediainfo(input_path: str) -> Dict[str, Any]:
    """Return MediaInfo JSON for a file path or (if supported) HTTP URL."""
    try:
        return json.loads(MediaInfo.parse(input_path, output="JSON"))
    except Exception as e:
        # Some layers don’t have libcurl-enabled MediaInfo; fall back to empty
        logger.warning(
            "MediaInfo failed; continuing with ffprobe only", extra={"error": str(e)}
        )
        return {"media": {"track": []}}


def merge_metadata(ff: Dict, mi: Dict) -> Dict[str, Any]:
    merged = {"general": {}, "video": [], "audio": []}

    ff_general = {k: v for k, v in ff.get("format", {}).items() if k != "streams"}
    mi_general = next(
        (
            t
            for t in mi.get("media", {}).get("track", [])
            if t.get("@type") == "General"
        ),
        {},
    )
    merged["general"] = {**ff_general, **mi_general}

    ff_video = [s for s in ff.get("streams", []) if s.get("codec_type") == "video"]
    ff_audio = [s for s in ff.get("streams", []) if s.get("codec_type") == "audio"]
    tracks = mi.get("media", {}).get("track", [])
    mi_video = [t for t in tracks if t.get("@type") == "Video"]
    mi_audio = [t for t in tracks if t.get("@type") == "Audio"]

    for i, stream in enumerate(ff_video):
        extra = mi_video[i] if i < len(mi_video) else {}
        merged["video"].append({**stream, **extra})

    for i, stream in enumerate(ff_audio):
        extra = mi_audio[i] if i < len(mi_audio) else {}
        merged["audio"].append({**stream, **extra})

    return merged


def clean_asset_id(asset_id: str) -> str:
    parts = asset_id.split(":")
    uuid = parts[-2] if parts[-1] == "master" else parts[-1]
    return f"asset:uuid:{uuid}"


def sanitize_metadata(data: Dict[str, Any]) -> Dict[str, Any]:
    def is_blob(s: Any) -> bool:
        return (
            isinstance(s, str)
            and len(s) > 100
            and re.fullmatch(r"[A-Za-z0-9+/]+={0,2}", s or "")
        )

    def walk(o: Any):
        if isinstance(o, dict):
            return {k: walk(v) for k, v in o.items() if not is_blob(v)}
        if isinstance(o, list):
            return [walk(i) for i in o if not is_blob(i)]
        if isinstance(o, (bytes, bytearray)):
            return f"{len(o)} bytes"
        if isinstance(o, str) and o.startswith("0000-00-00"):
            return None
        return o

    return walk(data)


def tmp_free_bytes() -> int:
    return shutil.disk_usage(TMP_DIR).free


def presigned_url(bucket: str, key: str, expires: Optional[int] = None) -> str:
    """
    Generate a presigned URL for an S3 object with region-aware client.
    The URL is signed in the bucket's own region, preventing
    SignatureDoesNotMatch errors outside us-east-1.
    """
    try:
        # Use region-aware S3 client
        s3_client = _get_s3_client_for_bucket(bucket)
        url = s3_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=expires or SIGNED_URL_TIMEOUT,
            HttpMethod="GET",
        )

        logger.debug(
            "Generated presigned URL for s3://%s/%s (region %s)",
            bucket,
            key,
            s3_client.meta.region_name,
        )

        return url
    except Exception as e:
        logger.error(f"Error generating presigned URL: {str(e)}")
        raise


# ─── handler ────────────────────────────────────────────────────────────
@lambda_middleware(event_bus_name=os.environ.get("EVENT_BUS_NAME", "default-event-bus"))
@logger.inject_lambda_context
@tracer.capture_lambda_handler
def lambda_handler(event: Dict[str, Any], context: LambdaContext):
    steps: Dict[str, Dict[str, str]] = {}
    video_specs: Dict[str, Dict[str, Any]] = {}
    updated_assets: Dict[str, Dict[str, Any]] = {}

    try:
        assets = event.get("payload", {}).get("assets", [])
        if not assets:
            raise ValueError("Event payload missing assets")

        for asset in assets:
            inv_id = clean_asset_id(asset["InventoryID"])
            src = asset["DigitalSourceAsset"]["MainRepresentation"]
            bucket = src["StorageInfo"]["PrimaryLocation"]["Bucket"]
            key = src["StorageInfo"]["PrimaryLocation"]["ObjectKey"]["FullPath"]
            local_file = TMP_DIR / Path(key).name

            # Object size & strategy
            s3_client = _get_s3_client_for_bucket(bucket)
            head = s3_client.head_object(Bucket=bucket, Key=key)
            size = head.get("ContentLength", 0)
            free = tmp_free_bytes()
            can_download = size and (size + SAFETY_MARGIN_BYTES) < free

            strategy = "download" if can_download else "stream"
            steps.setdefault(inv_id, {})["Strategy"] = strategy
            logger.append_keys(
                inventory_id=inv_id, s3_size=size, tmp_free=free, strategy=strategy
            )

            input_path = ""
            downloaded = False

            if strategy == "download":
                s3_client.download_file(bucket, key, str(local_file))
                downloaded = True
                input_path = str(local_file)
                steps[inv_id]["S3_download"] = "Success"
            else:
                input_path = presigned_url(bucket, key)
                steps[inv_id]["S3_presigned_url"] = "Success"

            # Probe
            ff = run_ffprobe(input_path)
            mi = run_mediainfo(
                input_path if downloaded else input_path
            )  # try URL; will fall back
            steps[inv_id]["Metadata_probe"] = "Success"

            merged = merge_metadata(ff, mi)
            sanitized = sanitize_metadata(merged)

            # Upsert in DynamoDB
            asset_table.update_item(
                Key={"InventoryID": inv_id},
                UpdateExpression="SET #m.#e = :v",
                ExpressionAttributeNames={"#m": "Metadata", "#e": "EmbeddedMetadata"},
                ExpressionAttributeValues={":v": sanitized},
            )
            steps[inv_id]["DDB_update"] = "Success"

            # Fetch back
            get_resp = asset_table.get_item(Key={"InventoryID": inv_id})
            updated_item = get_resp.get("Item", {})
            updated_assets[inv_id] = updated_item
            steps[inv_id]["DDB_get"] = "Success"

            # Minimal video spec
            v0 = merged.get("video", [{}])[0]
            video_specs[inv_id] = {
                "Resolution": {"Width": v0.get("width"), "Height": v0.get("height")},
                "Codec": v0.get("codec_name"),
                "BitRate": v0.get("bit_rate"),
                "FrameRate": v0.get("r_frame_rate"),
            }

            # Cleanup local file if used
            if downloaded:
                try:
                    local_file.unlink(missing_ok=True)
                    steps[inv_id]["Tmp_cleanup"] = "Success"
                except Exception as e:
                    logger.warning(
                        "Failed to cleanup tmp file", extra={"error": str(e)}
                    )

        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "message": "Process completed successfully",
                    "steps": steps,
                    "video_specs": video_specs,
                    "updatedAsset": updated_assets,
                },
                default=_json_default,
            ),
        }
    except Exception as exc:
        logger.exception("Processing failed", extra={"steps": steps})
        return {
            "statusCode": 500,
            "body": json.dumps(
                {"error": str(exc), "steps": steps}, default=_json_default
            ),
        }
