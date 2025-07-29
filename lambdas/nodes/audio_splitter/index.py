"""
Audio Chunker Lambda
────────────────────
• Splits an input MP3 (or any ffmpeg-readable source) into 10-second chunks
  that are **always** ≤ MAX_CHUNK_SIZE_MB.
• Uploads each chunk to S3 and returns their metadata.

ENV
───
MAX_CHUNK_SIZE_MB           default 10.5
CHUNK_DURATION              default 10   (seconds)
MEDIA_ASSETS_BUCKET_NAME    default source bucket
EVENT_BUS_NAME              optional (for @lambda_middleware)
"""

from __future__ import annotations

import json
import math
import os
import re
import subprocess
import tempfile
from typing import Any, Dict, List, Tuple

import boto3
import requests
from aws_lambda_powertools import Logger, Tracer
from lambda_middleware import lambda_middleware
from nodes_utils import format_duration  # your existing helper

# ── Powertools & AWS clients ────────────────────────────────────────────────
logger = Logger()
tracer = Tracer()
s3_client = boto3.client("s3")

# ── Configuration ───────────────────────────────────────────────────────────
MAX_CHUNK_SIZE_MB = float(os.getenv("MAX_CHUNK_SIZE_MB", "10.5"))
MAX_CHUNK_SIZE_BYTES = int(MAX_CHUNK_SIZE_MB * 1024 * 1024)

# Bit-rates LAME supports for constant-bit-rate (CBR) MP3
ALLOWED_CBR = [320, 256, 224, 192, 160, 128, 96, 64, 48, 32, 24]  # kbps
SAFE_MARGIN = 0.97  # 3 % head-room for ID3/container overhead


# ── Helpers ─────────────────────────────────────────────────────────────────
def get_audio_duration(path: str) -> float:
    """Return duration of file (seconds) via ffmpeg probe."""
    cmd = ["/opt/bin/ffmpeg", "-i", path]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    match = re.search(r"Duration:\s+(\d+):(\d+):(\d+\.\d+)", proc.stderr or "")
    if not match:
        logger.error("Could not parse duration from ffmpeg output")
        return 0.0
    h, m, s = int(match[1]), int(match[2]), float(match[3])
    return h * 3600 + m * 60 + s


def get_file_size_mb(path: str) -> float:
    return os.path.getsize(path) / (1024 * 1024)


def encode_audio_segment(
    input_path: str,
    output_path: str,
    start_time: float,
    duration: float,
    extra_args: List[str],
) -> Tuple[bool, float]:
    """
    Encode one segment with the given ffmpeg args (bit-rate, mono, etc.)
    Returns (success, actual_duration).
    """
    cmd = (
        [
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
            "-f",
            "mp3",
            "-c:a",
            "libmp3lame",
        ]
        + extra_args
        + ["-y", output_path]
    )

    try:
        subprocess.check_call(cmd)
        return True, get_audio_duration(output_path)
    except subprocess.CalledProcessError as e:
        logger.error(f"FFmpeg encoding failed: {e}")
        return False, 0.0


def compute_target_bitrate(duration_s: float) -> Tuple[int, List[str]]:
    """
    Pick the highest CBR (and down-sampling if needed) so that:
          size ≤ MAX_CHUNK_SIZE_BYTES
    Returns (bitrate_kbps, ffmpeg_args).
    """
    ceiling_kbps = int((MAX_CHUNK_SIZE_BYTES * 8) / (duration_s * 1000) * SAFE_MARGIN)

    # First try stereo, 44.1 kHz
    for kbps in reversed(ALLOWED_CBR):
        if kbps <= ceiling_kbps:
            return kbps, ["-b:a", f"{kbps}k"]

    # Try mono + 22.05 kHz
    downsample = ["-ac", "1", "-ar", "22050"]
    ceiling_kbps = int((MAX_CHUNK_SIZE_BYTES * 8) / (duration_s * 1000) * SAFE_MARGIN)
    for kbps in reversed(ALLOWED_CBR):
        if kbps <= ceiling_kbps:
            return kbps, downsample + ["-b:a", f"{kbps}k"]

    raise RuntimeError(
        "Impossible size constraint: even 22 kHz/mono/24 kbps exceeds the limit."
    )


def create_size_constrained_segment(
    input_path: str,
    output_path: str,
    start_time: float,
    target_duration: float,
) -> Tuple[bool, float, str]:
    """
    Encode once with the mathematically derived bit-rate. Guaranteed or fail.
    """
    try:
        kbps, ffmpeg_args = compute_target_bitrate(target_duration)
    except RuntimeError as e:
        logger.error(str(e))
        return False, 0.0, "failed"

    success, actual_dur = encode_audio_segment(
        input_path, output_path, start_time, target_duration, ffmpeg_args
    )
    if not success:
        return False, 0.0, "ffmpeg_error"

    if os.path.getsize(output_path) > MAX_CHUNK_SIZE_BYTES:
        logger.error(
            f"File still too large at {kbps} kbps "
            f"({get_file_size_mb(output_path):.2f} MB)."
        )
        return False, actual_dur, "failed"

    return True, actual_dur, f"{kbps}kbps"


def ensure_tmp_dir(path: str = "/tmp/segments") -> str:
    os.makedirs(path, exist_ok=True)
    return path


def _bad_request(msg: str) -> Dict[str, Any]:
    logger.warning(msg)
    return {"statusCode": 400, "body": json.dumps({"error": msg})}


def _error(code: int, msg: str) -> Dict[str, Any]:
    logger.error(msg)
    return {"statusCode": code, "body": json.dumps({"error": msg})}


# ── Lambda Handler ──────────────────────────────────────────────────────────
@lambda_middleware(event_bus_name=os.getenv("EVENT_BUS_NAME", "default-event-bus"))
@logger.inject_lambda_context
@tracer.capture_lambda_handler
def lambda_handler(event: Dict[str, Any], context) -> Any:  # noqa: C901 (long fn)
    try:
        logger.info("Incoming event", extra={"event": event})

        # ── Extract payload ──────────────────────────────────────────────
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

        raw = os.getenv("CHUNK_DURATION") or str(data.get("chunkDuration", "10"))
        try:
            chunk_duration = int(raw)
        except ValueError:
            chunk_duration = 10
            logger.warning("Invalid CHUNK_DURATION – defaulting to 10 s")

        # ── Download ─────────────────────────────────────────────────────
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

        # ── Segment ──────────────────────────────────────────────────────
        total_duration = get_audio_duration(input_path)
        output_dir = ensure_tmp_dir()
        base_name = os.path.splitext(os.path.basename(source_key))[0]

        num_segments = math.ceil(total_duration / chunk_duration)
        segments: List[Dict[str, Any]] = []

        for i in range(num_segments):
            start = i * chunk_duration
            dur = min(chunk_duration, total_duration - start)
            if dur <= 0:
                break

            seg_name = f"{base_name}_segment_{i+1:03d}.mp3"
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

        # ── Upload & Build Response ──────────────────────────────────────
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
                    "mediaType": "Audio",
                    "asset_id": asset_id,
                    "inventory_id": inventory_id,
                }
            )

        logger.info(
            f"Created {len(chunk_meta)} segments, total duration "
            f"{sum(c['duration'] for c in chunk_meta):.2f}s"
        )
        return chunk_meta

    except Exception as exc:  # catch-all so Lambda never ends uncleanly
        logger.exception("Unhandled exception")
        return _error(500, f"Unhandled error: {exc}")
