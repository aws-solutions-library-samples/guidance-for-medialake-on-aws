"""
Video Orientation Correction Node

Detects video orientation via FFprobe side_data (displaymatrix / rotation)
and submits a MediaConvert job to rotate the video if needed.

Rotation detection logic:
- FFprobe reports rotation in stream side_data or tags
- Common values: 0 (landscape), 90 (portrait CW), 180 (upside-down), 270 (portrait CCW)
- If rotation != 0, a MediaConvert transcode job is submitted with the
  appropriate VideoPreprocessors.ImageInserter or Rotate setting
- If rotation == 0, the asset passes through unchanged

The node follows the same middleware pattern as video_proxy_and_thumbnail,
using Jinja2 templates for MediaConvert job settings.
"""

import json
import os
import subprocess
from pathlib import Path
from typing import Any, Dict

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext
from botocore.config import Config
from lambda_middleware import lambda_middleware

# ─── constants ──────────────────────────────────────────────────────────
FFPROBE_BIN = "/opt/bin/ffprobe"
TMP_DIR = Path("/tmp")
SIGNED_URL_TIMEOUT = int(os.getenv("SIGNED_URL_TIMEOUT", "300"))

logger = Logger(service="video-orientation-correction")
tracer = Tracer()
metrics = Metrics(namespace="MediaLake", service="video-orientation-correction")

_SIGV4_CFG = Config(signature_version="s3v4", s3={"addressing_style": "virtual"})
_S3_CLIENT_CACHE: dict[str, boto3.client] = {}

dynamodb = boto3.resource("dynamodb")
asset_table = dynamodb.Table(os.environ["MEDIALAKE_ASSET_TABLE"])


# ─── S3 helpers ─────────────────────────────────────────────────────────


def _get_s3_client(bucket: str) -> boto3.client:
    """Region-aware S3 client, cached per region."""
    generic = _S3_CLIENT_CACHE.setdefault(
        "us-east-1",
        boto3.client("s3", region_name="us-east-1", config=_SIGV4_CFG),
    )
    try:
        region = (
            generic.get_bucket_location(Bucket=bucket).get("LocationConstraint")
            or "us-east-1"
        )
    except Exception:
        region = os.getenv("AWS_REGION", "us-east-1")

    if region not in _S3_CLIENT_CACHE:
        _S3_CLIENT_CACHE[region] = boto3.client(
            "s3",
            region_name=region,
            endpoint_url=f"https://s3.{region}.amazonaws.com",
            config=_SIGV4_CFG,
        )
    return _S3_CLIENT_CACHE[region]


def _presigned_url(bucket: str, key: str) -> str:
    client = _get_s3_client(bucket)
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=SIGNED_URL_TIMEOUT,
    )


# ─── rotation detection ────────────────────────────────────────────────


def detect_rotation(input_path: str) -> int:
    """
    Detect video rotation angle using FFprobe.

    Checks two sources:
    1. Stream side_data (displaymatrix) — modern containers (MP4/MOV)
    2. Stream tags.rotate — legacy metadata tag

    Returns: rotation in degrees (0, 90, 180, 270). Defaults to 0.
    """
    cmd = [
        FFPROBE_BIN,
        "-v",
        "error",
        "-analyzeduration",
        "5M",
        "-probesize",
        "5M",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=width,height",
        "-show_entries",
        "stream_side_data=rotation",
        "-show_entries",
        "stream_tags=rotate",
        "-print_format",
        "json",
        input_path,
    ]
    try:
        result = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10
        )
    except subprocess.TimeoutExpired:
        logger.warning(
            "FFprobe timed out during rotation detection",
            extra={"input_path": input_path},
        )
        return 0
    if result.returncode:
        logger.warning(
            "FFprobe failed for rotation detection",
            extra={"stderr": result.stderr.decode()[:500]},
        )
        return 0

    try:
        data = json.loads(result.stdout)
    except (json.JSONDecodeError, ValueError):
        logger.warning(
            "FFprobe returned malformed JSON for rotation detection",
            extra={"stdout": result.stdout.decode(errors="replace")[:500]},
        )
        return 0
    streams = data.get("streams", [])
    if not streams:
        return 0

    stream = streams[0]

    # Check side_data first (modern containers)
    for sd in stream.get("side_data_list", []):
        if "rotation" in sd:
            rotation = int(float(sd["rotation"]))
            # Normalize negative rotations (e.g., -90 → 270)
            return rotation % 360

    # Fallback: legacy rotate tag
    rotate_tag = stream.get("tags", {}).get("rotate")
    if rotate_tag:
        return int(float(rotate_tag)) % 360

    return 0


# ─── audio detection ────────────────────────────────────────────────────


def detect_audio(input_path: str) -> bool:
    """
    Detect whether the input file contains at least one audio stream.

    Uses FFprobe to query audio stream count. Returns False when no audio
    is found or when probing fails (safe default — MediaConvert would
    error on a missing audio selector).
    """
    cmd = [
        FFPROBE_BIN,
        "-v",
        "error",
        "-select_streams",
        "a",
        "-show_entries",
        "stream=index",
        "-print_format",
        "json",
        input_path,
    ]
    try:
        result = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10
        )
    except subprocess.TimeoutExpired:
        logger.warning(
            "FFprobe timed out during audio detection",
            extra={"input_path": input_path},
        )
        return False
    if result.returncode:
        logger.warning(
            "FFprobe failed for audio detection",
            extra={"stderr": result.stderr.decode()[:500]},
        )
        return False

    try:
        data = json.loads(result.stdout)
    except (json.JSONDecodeError, ValueError):
        logger.warning(
            "FFprobe returned malformed JSON for audio detection",
            extra={"stdout": result.stdout.decode(errors="replace")[:500]},
        )
        return False
    return len(data.get("streams", [])) > 0


# ─── rotation → MediaConvert mapping ───────────────────────────────────

# MediaConvert uses DEGREES_* enum values for rotation
ROTATION_MAP = {
    0: None,  # No rotation needed
    90: "DEGREES_90",
    180: "DEGREES_180",
    270: "DEGREES_270",
}


def clean_asset_id(asset_id: str) -> str:
    parts = asset_id.split(":")
    uuid = parts[-2] if parts[-1] == "master" else parts[-1]
    return f"asset:uuid:{uuid}"


def _json_default(o):
    """JSON serializer for Decimal and other non-standard types."""
    import decimal

    if isinstance(o, decimal.Decimal):
        return int(o) if o % 1 == 0 else float(o)
    raise TypeError(f"Object of type {type(o)} is not JSON serializable")


# ─── MediaConvert helpers ───────────────────────────────────────────────


def _get_mediaconvert_client() -> boto3.client:
    """Get MediaConvert client with cached endpoint."""
    mc_generic = boto3.client("mediaconvert", region_name=os.getenv("AWS_REGION"))
    endpoints = mc_generic.describe_endpoints(MaxResults=1)
    endpoint_url = endpoints["Endpoints"][0]["Url"]
    return boto3.client(
        "mediaconvert",
        region_name=os.getenv("AWS_REGION"),
        endpoint_url=endpoint_url,
    )


def submit_rotation_job(
    input_bucket: str,
    input_key: str,
    output_bucket: str,
    output_prefix: str,
    rotation_degrees: str,
    queue_arn: str,
    role_arn: str,
    has_audio: bool = True,
) -> Dict[str, Any]:
    """
    Submit a MediaConvert job that rotates the video and writes the
    corrected file back to S3.

    When *has_audio* is False the AudioDescriptions / AudioSelectors keys
    are omitted so MediaConvert does not fail on inputs without an audio
    track.
    """
    mc_client = _get_mediaconvert_client()

    output_settings: Dict[str, Any] = {
        "ContainerSettings": {
            "Container": "MP4",
            "Mp4Settings": {"MoovPlacement": "PROGRESSIVE_DOWNLOAD"},
        },
        "VideoDescription": {
            "CodecSettings": {
                "Codec": "H_264",
                "H264Settings": {
                    "RateControlMode": "QVBR",
                    "SceneChangeDetect": "TRANSITION_DETECTION",
                    "QualityTuningLevel": "SINGLE_PASS_HQ",
                    "QvbrSettings": {"QvbrQualityLevel": 9},
                },
            },
        },
        "NameModifier": "_rotated",
    }

    input_settings: Dict[str, Any] = {
        "VideoSelector": {
            "Rotate": rotation_degrees,
        },
        "FileInput": f"s3://{input_bucket}/{input_key}",
    }

    if has_audio:
        output_settings["AudioDescriptions"] = [
            {
                "CodecSettings": {
                    "Codec": "AAC",
                    "AacSettings": {
                        "Bitrate": 128000,
                        "CodingMode": "CODING_MODE_2_0",
                        "SampleRate": 44100,
                    },
                },
                "AudioSourceName": "Audio Selector 1",
            }
        ]
        input_settings["AudioSelectors"] = {
            "Audio Selector 1": {"DefaultSelection": "DEFAULT"}
        }

    job_settings = {
        "Queue": queue_arn,
        "Role": role_arn,
        "Settings": {
            "OutputGroups": [
                {
                    "Name": "Orientation Corrected",
                    "Outputs": [output_settings],
                    "OutputGroupSettings": {
                        "Type": "FILE_GROUP_SETTINGS",
                        "FileGroupSettings": {
                            "Destination": f"s3://{output_bucket}/{output_prefix}",
                        },
                    },
                }
            ],
            "Inputs": [input_settings],
        },
        "StatusUpdateInterval": "SECONDS_60",
        "Priority": 0,
    }

    response = mc_client.create_job(**job_settings)
    return {
        "jobId": response["Job"]["Id"],
        "status": response["Job"]["Status"],
    }


# ─── handler ────────────────────────────────────────────────────────────


@lambda_middleware(event_bus_name=os.environ.get("EVENT_BUS_NAME", "default-event-bus"))
@logger.inject_lambda_context
@tracer.capture_lambda_handler
def lambda_handler(event: Dict[str, Any], context: LambdaContext):
    """
    Detect video orientation and submit a MediaConvert rotation job if needed.

    Flow:
    1. Extract S3 location from the asset payload
    2. Generate a presigned URL for FFprobe streaming
    3. Detect rotation angle via FFprobe
    4. If rotation != 0, submit a MediaConvert job to correct it
    5. Update the asset record in DynamoDB with orientation info
    6. Return job details (or pass-through if no rotation needed)
    """
    steps: Dict[str, Dict[str, str]] = {}
    orientation_results: Dict[str, Dict[str, Any]] = {}

    try:
        assets = event.get("payload", {}).get("assets", [])
        if not assets:
            raise ValueError("Event payload missing assets")

        queue_arn = (
            event.get("payload", {})
            .get("data", {})
            .get(
                "MediaConvert Queue Arn",
                os.getenv("MEDIACONVERT_QUEUE_ARN", ""),
            )
        )
        role_arn = (
            event.get("payload", {})
            .get("data", {})
            .get(
                "MediaConvert Role Arn",
                os.getenv("MEDIACONVERT_ROLE_ARN", ""),
            )
        )
        if not queue_arn or not role_arn:
            raise ValueError(
                "MediaConvert Queue Arn and Role Arn are required. "
                "Provide them in payload.data or set environment variables."
            )

        for asset in assets:
            inv_id = clean_asset_id(asset["InventoryID"])
            src = asset["DigitalSourceAsset"]["MainRepresentation"]
            bucket = src["StorageInfo"]["PrimaryLocation"]["Bucket"]
            key = src["StorageInfo"]["PrimaryLocation"]["ObjectKey"]["FullPath"]

            steps.setdefault(inv_id, {})
            logger.append_keys(inventory_id=inv_id)

            # Generate presigned URL for FFprobe (streaming, no download needed)
            url = _presigned_url(bucket, key)
            steps[inv_id]["presigned_url"] = "Success"

            # Detect rotation
            rotation = detect_rotation(url)
            steps[inv_id]["rotation_detection"] = "Success"
            steps[inv_id]["detected_rotation"] = str(rotation)

            mc_rotation = ROTATION_MAP.get(rotation)

            if rotation == 0:
                # No rotation needed — pass through
                logger.info("No rotation needed", extra={"rotation": rotation})
                orientation_results[inv_id] = {
                    "rotation_detected": rotation,
                    "correction_applied": False,
                    "status": "PASS_THROUGH",
                }
                steps[inv_id]["action"] = "pass_through"
            elif mc_rotation is None:
                # Unsupported rotation angle
                logger.warning(
                    "Unsupported rotation angle", extra={"rotation": rotation}
                )
                orientation_results[inv_id] = {
                    "rotation_detected": rotation,
                    "correction_applied": False,
                    "status": "UNSUPPORTED_ANGLE",
                }
                steps[inv_id]["action"] = "unsupported_angle"
            else:
                # Submit MediaConvert rotation job
                logger.info(
                    "Submitting rotation job",
                    extra={
                        "rotation": rotation,
                        "mc_rotation": mc_rotation,
                    },
                )

                # Output goes to a /corrected/ prefix alongside the original
                key_parent = str(Path(key).parent)
                output_prefix = f"{key_parent}/corrected/"

                job_result = submit_rotation_job(
                    input_bucket=bucket,
                    input_key=key,
                    output_bucket=bucket,
                    output_prefix=output_prefix,
                    rotation_degrees=mc_rotation,
                    queue_arn=queue_arn,
                    role_arn=role_arn,
                    has_audio=detect_audio(url),
                )

                orientation_results[inv_id] = {
                    "rotation_detected": rotation,
                    "correction_applied": True,
                    "mc_rotation": mc_rotation,
                    "mediaconvert_job_id": job_result["jobId"],
                    "mediaconvert_status": job_result["status"],
                    "output_prefix": output_prefix,
                    "status": "SUBMITTED",
                }
                steps[inv_id]["action"] = "rotation_job_submitted"
                steps[inv_id]["mediaconvert_job_id"] = job_result["jobId"]

            # Update DynamoDB with orientation metadata
            asset_table.update_item(
                Key={"InventoryID": inv_id},
                UpdateExpression="SET #m = if_not_exists(#m, :empty), #m.#o = :v",
                ExpressionAttributeNames={
                    "#m": "Metadata",
                    "#o": "OrientationCorrection",
                },
                ExpressionAttributeValues={
                    ":empty": {},
                    ":v": orientation_results[inv_id],
                },
            )
        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "message": "Orientation check completed",
                    "steps": steps,
                    "orientation_results": orientation_results,
                },
                default=_json_default,
            ),
        }
    except Exception as exc:
        logger.exception("Orientation correction failed", extra={"steps": steps})
        return {
            "statusCode": 500,
            "body": json.dumps(
                {"error": str(exc), "steps": steps},
                default=_json_default,
            ),
        }
