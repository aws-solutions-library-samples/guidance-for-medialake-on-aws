"""
Video Splitter Lambda
────────────────────
• Splits an input video file into MP4 chunks of configurable duration
  that are **always** ≤ MAX_CHUNK_SIZE_MB.
• Uploads each chunk to S3 and returns their metadata.

ENV
───
MAX_CHUNK_SIZE_MB           default 50.0
CHUNK_DURATION              default 7200 (2 hours in seconds)
MEDIA_ASSETS_BUCKET_NAME    default source bucket
EVENT_BUS_NAME              optional (for @lambda_middleware)
"""

from __future__ import annotations

import json
import math
import os
import subprocess
import tempfile
from typing import Any, Dict, List, Tuple

import boto3
import requests
from aws_lambda_powertools import Logger, Tracer
from lambda_middleware import lambda_middleware
from nodes_utils import format_duration

# Powertools & AWS clients
logger = Logger()
tracer = Tracer()
s3_client = boto3.client("s3")

# Configuration
MAX_CHUNK_SIZE_MB = float(os.getenv("MAX_CHUNK_SIZE_MB", "50.0"))
MAX_CHUNK_SIZE_BYTES = int(MAX_CHUNK_SIZE_MB * 1024 * 1024)

# Video encoding presets for size optimization
VIDEO_PRESETS = [
    # High quality
    {"crf": 23, "scale": None, "fps": None, "description": "high_quality"},
    # Medium quality with resolution scaling
    {"crf": 28, "scale": "1280:720", "fps": None, "description": "medium_720p"},
    # Lower quality with resolution scaling
    {"crf": 32, "scale": "854:480", "fps": None, "description": "low_480p"},
    # Very low quality with frame rate reduction
    {"crf": 35, "scale": "640:360", "fps": 15, "description": "very_low_360p_15fps"},
]

SAFE_MARGIN = 0.95  # 5% headroom for container overhead


def get_video_duration(path: str) -> float:
    """Return duration of video file (seconds) via ffprobe."""
    cmd = [
        "/opt/bin/ffprobe",
        "-v",
        "quiet",
        "-show_entries",
        "format=duration",
        "-of",
        "csv=p=0",
        path,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return float(result.stdout.strip())
    except (subprocess.CalledProcessError, ValueError) as e:
        logger.error(f"Could not get video duration: {e}")
        return 0.0


def get_file_size_mb(path: str) -> float:
    return os.path.getsize(path) / (1024 * 1024)


def encode_video_segment(
    input_path: str,
    output_path: str,
    start_time: float,
    duration: float,
    preset: Dict[str, Any],
) -> Tuple[bool, float]:
    """
    Encode one video segment with the given preset.
    Returns (success, actual_duration).
    """
    cmd = [
        "/opt/bin/ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-ss",
        str(start_time),
        "-i",
        input_path,
        "-t",
        str(duration),
        "-c:v",
        "libx264",
        "-crf",
        str(preset["crf"]),
        "-c:a",
        "aac",
        "-b:a",
        "128k",
    ]

    # Add video filters if specified
    filters = []
    if preset["scale"]:
        filters.append(f"scale={preset['scale']}")
    if preset["fps"]:
        filters.append(f"fps={preset['fps']}")

    if filters:
        cmd.extend(["-vf", ",".join(filters)])

    cmd.extend(["-movflags", "+faststart", "-y", output_path])

    try:
        subprocess.check_call(cmd)
        return True, get_video_duration(output_path)
    except subprocess.CalledProcessError as e:
        logger.error(f"FFmpeg encoding failed: {e}")
        return False, 0.0


def create_size_constrained_segment(
    input_path: str,
    output_path: str,
    start_time: float,
    target_duration: float,
) -> Tuple[bool, float, str]:
    """
    Try different encoding presets until we get a file ≤ MAX_CHUNK_SIZE_BYTES.
    Returns (success, actual_duration, quality_description).
    """
    for preset in VIDEO_PRESETS:
        success, actual_dur = encode_video_segment(
            input_path, output_path, start_time, target_duration, preset
        )

        if not success:
            continue

        file_size = os.path.getsize(output_path)
        if file_size <= MAX_CHUNK_SIZE_BYTES:
            logger.info(
                f"Successfully encoded segment with {preset['description']} "
                f"({get_file_size_mb(output_path):.2f} MB)"
            )
            return True, actual_dur, preset["description"]
        else:
            logger.warning(
                f"Segment too large with {preset['description']} "
                f"({get_file_size_mb(output_path):.2f} MB), trying next preset"
            )

    logger.error(
        f"Could not create segment within size limit of {MAX_CHUNK_SIZE_MB} MB "
        f"even with lowest quality preset"
    )
    return False, 0.0, "failed"


def ensure_tmp_dir(path: str = "/tmp/segments") -> str:
    os.makedirs(path, exist_ok=True)
    return path


def _bad_request(msg: str) -> Dict[str, Any]:
    logger.warning(msg)
    return {"statusCode": 400, "body": json.dumps({"error": msg})}


def _error(code: int, msg: str) -> Dict[str, Any]:
    logger.error(msg)
    return {"statusCode": code, "body": json.dumps({"error": msg})}


@lambda_middleware(event_bus_name=os.getenv("EVENT_BUS_NAME", "default-event-bus"))
@logger.inject_lambda_context
@tracer.capture_lambda_handler
def lambda_handler(event: Dict[str, Any], context) -> Any:
    try:
        logger.info("Incoming event", extra={"event": event})

        # Extract payload
        payload = event.get("payload", {})
        data = payload.get("data", {})
        assets = payload.get("assets", [])

        presigned_url = data.get("presignedUrl")
        source_bucket = data.get("bucket")
        source_key = data.get("key")
        use_s3_direct = False

        if not (presigned_url and source_bucket and source_key):
            proxy = next(
                (
                    r
                    for r in assets[0].get("DerivedRepresentations", [])
                    if r.get("Purpose") == "proxy"
                ),
                None,
            )
            if not proxy:
                return _bad_request(
                    "Missing presignedUrl and no proxy DerivedRepresentation found"
                )

            loc = proxy["StorageInfo"]["PrimaryLocation"]
            source_bucket = loc["Bucket"]
            source_key = loc.get("ObjectKey", {}).get("FullPath") or loc.get("path")
            if not source_key:
                return _bad_request("Proxy representation missing S3 key")
            use_s3_direct = True

        try:
            inventory_id = assets[0]["InventoryID"]
            asset_id = assets[0]["DigitalSourceAsset"]["ID"]
        except Exception:
            return _bad_request("Could not locate InventoryID or DigitalSourceAsset ID")

        raw = os.getenv("CHUNK_DURATION") or str(data.get("chunkDuration", "7200"))
        try:
            chunk_duration = int(raw)
        except ValueError:
            chunk_duration = 7200
            logger.warning("Invalid CHUNK_DURATION – defaulting to 7200 s (2 hours)")

        # Download
        input_path = os.path.join(tempfile.gettempdir(), os.path.basename(source_key))
        if use_s3_direct:
            logger.info(
                "Downloading proxy asset from S3",
                extra={"bucket": source_bucket, "key": source_key},
            )
            s3_client.download_file(source_bucket, source_key, input_path)
        else:
            logger.info("Downloading via presigned URL")
            r = requests.get(presigned_url)
            r.raise_for_status()
            with open(input_path, "wb") as f:
                f.write(r.content)

        # Segment
        total_duration = get_video_duration(input_path)
        output_dir = ensure_tmp_dir()
        base_name = os.path.splitext(os.path.basename(source_key))[0]

        num_segments = math.ceil(total_duration / chunk_duration)
        segments: List[Dict[str, Any]] = []

        for i in range(num_segments):
            start = i * chunk_duration
            dur = min(chunk_duration, total_duration - start)
            if dur <= 0:
                break

            seg_name = f"{base_name}_segment_{i+1:03d}.mp4"
            seg_path = os.path.join(output_dir, seg_name)

            logger.info(
                f"Creating seg {i+1}/{num_segments} (start={start:.2f}s, "
                f"duration={dur:.2f}s)"
            )

            ok, real_dur, qual = create_size_constrained_segment(
                input_path, seg_path, start, dur
            )
            if not ok:
                return _error(500, f"Failed to create segment {i+1}")

            segments.append(
                {
                    "filename": seg_name,
                    "path": seg_path,
                    "start_time": start,
                    "duration": real_dur,
                    "quality": qual,
                    "size_mb": get_file_size_mb(seg_path),
                }
            )

        # Upload & Build Response
        upload_bucket = os.getenv("MEDIA_ASSETS_BUCKET_NAME", source_bucket)
        chunk_meta: List[Dict[str, Any]] = []

        for idx, seg in enumerate(segments, 1):
            seg_key = f"chunks/{asset_id}/{seg['filename']}"
            s3_client.upload_file(seg["path"], upload_bucket, seg_key)

            start = seg["start_time"]
            end = start + seg["duration"]

            chunk_meta.append(
                {
                    "bucket": upload_bucket,
                    "key": seg_key,
                    "url": f"s3://{upload_bucket}/{seg_key}",
                    "index": idx,
                    "start_time": start,
                    "end_time": end,
                    "start_time_formatted": format_duration(start),
                    "end_time_formatted": format_duration(end),
                    "duration": seg["duration"],
                    "duration_formatted": format_duration(seg["duration"]),
                    "size_bytes": os.path.getsize(seg["path"]),
                    "size_mb": seg["size_mb"],
                    "quality_used": seg["quality"],
                    "mediaType": "Video",
                    "asset_id": asset_id,
                    "inventory_id": inventory_id,
                }
            )

        logger.info(
            f"Created {len(chunk_meta)} segments, total duration "
            f"{sum(c['duration'] for c in chunk_meta):.2f}s"
        )
        return chunk_meta

    except Exception as exc:
        logger.exception("Unhandled exception")
        return _error(500, f"Unhandled error: {exc}")
