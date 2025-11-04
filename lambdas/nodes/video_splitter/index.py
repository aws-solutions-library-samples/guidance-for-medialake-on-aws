"""
Video Splitter Lambda – stream‑copy edition (no‑reencode, no ffprobe)
──────────────────────────────────────────────────────────────────────
• Splits a source video into MP4 chunks ≤ MAX_CHUNK_SIZE_MB **without re‑encoding**.
• Uses your original get_video_duration() (regex‑parsing ffmpeg stderr).
• Uploads each chunk to S3 and returns their metadata.

ENV
───
MAX_CHUNK_SIZE_MB           default 50.0
CHUNK_DURATION              default 7200 s
MEDIA_ASSETS_BUCKET_NAME    default source bucket
EVENT_BUS_NAME              optional (for @lambda_middleware)
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
from typing import Any, Dict, List, Tuple

import boto3
import requests
from aws_lambda_powertools import Logger, Tracer
from lambda_middleware import lambda_middleware
from nodes_utils import format_duration

# ────────────────────────────────────────────────────────── helpers ──
logger = Logger()
tracer = Tracer()
s3_client = boto3.client("s3")

MAX_CHUNK_SIZE_MB = float(os.getenv("MAX_CHUNK_SIZE_MB", "50.0"))
MAX_CHUNK_SIZE_BYTES = int(MAX_CHUNK_SIZE_MB * 1024 * 1024)
SAFE_MARGIN = 0.97  # 3 % head‑room
FFMPEG = "/opt/bin/ffmpeg"


def _run(cmd: List[str]) -> subprocess.CompletedProcess:
    """Run subprocess, raise on error, return CompletedProcess."""
    return subprocess.run(cmd, capture_output=True, text=True, check=True)


# ── reused exactly from your original script ─────────────────────────
def get_video_duration(path: str) -> float:
    """Return duration of file (seconds) via ffmpeg probe."""
    proc = subprocess.run([FFMPEG, "-i", path], capture_output=True, text=True)
    match = re.search(r"Duration:\s+(\d+):(\d+):(\d+\.\d+)", proc.stderr or "")
    if not match:
        logger.error("Could not parse duration from ffmpeg output")
        return 0.0
    h, m, s = int(match[1]), int(match[2]), float(match[3])
    return h * 3600 + m * 60 + s


# ─────────────────────────────────────────────────────────────────────


def get_media_info(path: str) -> Tuple[float, int]:
    """
    Return (duration_seconds, size_bytes) using get_video_duration + os.stat.
    """
    return get_video_duration(path), os.path.getsize(path)


def split_segment_copy(
    src: str, dst: str, start: float, target_dur: float
) -> Tuple[bool, float]:
    """
    Stream‑copy a slice of `target_dur` seconds into `dst`.
    Returns (success, actual_duration).
    """
    cmd = [
        FFMPEG,
        "-hide_banner",
        "-loglevel",
        "error",
        "-ss",
        f"{start:.3f}",
        "-t",
        f"{target_dur:.3f}",
        "-i",
        src,
        "-c",
        "copy",
        "-map",
        "0",
        "-movflags",
        "+faststart",
        "-avoid_negative_ts",
        "make_zero",
        "-y",
        dst,
    ]
    try:
        _run(cmd)
        dur, _ = get_media_info(dst)
        return True, dur
    except subprocess.CalledProcessError as e:
        logger.error(f"ffmpeg failed: {e.stderr or e}")
        return False, 0.0


def create_size_constrained_segment_copy(
    src: str, dst: str, start: float, max_dur: float
) -> Tuple[bool, float]:
    """
    Shorten duration until the segment size ≤ limit (no re‑encode).
    Returns (success, actual_duration).
    """
    total_dur, total_size = get_media_info(src)
    avg_bps = (total_size * 8) / max(total_dur, 0.1)

    dur = min(max_dur, (MAX_CHUNK_SIZE_BYTES * SAFE_MARGIN * 8) / avg_bps)
    dur = max(1.0, dur)

    while dur > 0:
        ok, real_dur = split_segment_copy(src, dst, start, dur)
        if not ok:
            return False, 0.0

        size = os.path.getsize(dst)
        if size <= MAX_CHUNK_SIZE_BYTES:
            return True, real_dur

        dur = max(1.0, real_dur * (MAX_CHUNK_SIZE_BYTES * SAFE_MARGIN / size))

    logger.error("Unable to create size‑constrained segment without re‑encoding")
    return False, 0.0


def ensure_tmp_dir(path: str = "/tmp/segments") -> str:
    os.makedirs(path, exist_ok=True)
    return path


def _bad_request(msg: str) -> Dict[str, Any]:
    logger.warning(msg)
    return {"statusCode": 400, "body": json.dumps({"error": msg})}


def _error(code: int, msg: str) -> Dict[str, Any]:
    logger.error(msg)
    return {"statusCode": code, "body": json.dumps({"error": msg})}


# ────────────────────────────────────────────────────────── handler ──
@lambda_middleware(event_bus_name=os.getenv("EVENT_BUS_NAME", "default-event-bus"))
@logger.inject_lambda_context
@tracer.capture_lambda_handler
def lambda_handler(event: Dict[str, Any], context) -> Any:
    try:
        logger.info("Incoming event", extra={"event": event})

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
                return _bad_request("Missing presignedUrl and no proxy found")

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
            return _bad_request("Could not locate InventoryID or asset ID")

        raw = os.getenv("CHUNK_DURATION") or str(data.get("chunkDuration", "7200"))
        try:
            max_chunk_dur = int(raw)
        except ValueError:
            max_chunk_dur = 7200
            logger.warning("Invalid CHUNK_DURATION – defaulting to 7200 s")

        # Download source
        # Two download paths:
        # 1. Direct S3 download: Used when accessing proxy representations stored
        #    in S3. More efficient as it uses boto3's native S3 transfer capabilities.
        # 2. Presigned URL download: Used when the source is provided via a
        #    time-limited presigned URL (e.g., from external sources or cross-account
        #    access). Uses requests with 600s timeout to handle large files.
        input_path = os.path.join(tempfile.gettempdir(), os.path.basename(source_key))
        if use_s3_direct:
            logger.info(
                "Downloading proxy from S3",
                extra={"bucket": source_bucket, "key": source_key},
            )
            s3_client.download_file(source_bucket, source_key, input_path)
        else:
            logger.info("Downloading via presigned URL")
            r = requests.get(presigned_url, timeout=600)
            r.raise_for_status()
            with open(input_path, "wb") as f:
                f.write(r.content)

        # Split
        total_duration, _ = get_media_info(input_path)
        output_dir = ensure_tmp_dir()
        base_name = os.path.splitext(os.path.basename(source_key))[0]

        segments: List[Dict[str, Any]] = []
        seg_idx = 0
        current_start = 0.0

        while current_start < total_duration:
            seg_idx += 1
            seg_name = f"{base_name}_segment_{seg_idx:03d}.mp4"
            seg_path = os.path.join(output_dir, seg_name)

            logger.info(f"Creating segment {seg_idx} @ {current_start:.2f}s")

            ok, actual_dur = create_size_constrained_segment_copy(
                input_path, seg_path, current_start, max_chunk_dur
            )
            if not ok:
                return _error(500, f"Failed to create segment {seg_idx}")

            segments.append(
                {
                    "filename": seg_name,
                    "path": seg_path,
                    "start_time": current_start,
                    "duration": actual_dur,
                    "size_mb": os.path.getsize(seg_path) / (1024 * 1024),
                }
            )
            current_start += actual_dur

        # Upload & build response
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
                    "mediaType": "Video",
                    "asset_id": asset_id,
                    "inventory_id": inventory_id,
                }
            )

        logger.info(
            f"Created {len(chunk_meta)} segments; total duration "
            f"{sum(c['duration'] for c in chunk_meta):.2f}s"
        )
        return chunk_meta

    except Exception as exc:
        logger.exception("Unhandled exception")
        return _error(500, f"Unhandled error: {exc}")
