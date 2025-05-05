import os
import json
import re
import subprocess
import tempfile
from typing import Dict, Any, List, Optional

import boto3
import requests
from aws_lambda_powertools import Logger, Tracer
from lambda_middleware import lambda_middleware
from nodes_utils import format_duration   # your existing utility

# ── Powertools & AWS clients ────────────────────────────────────────────────
logger = Logger()
tracer = Tracer()
s3_client = boto3.client("s3")


# ── Helpers ─────────────────────────────────────────────────────────────────
def get_audio_duration(path: str) -> float:
    """
    Run ffmpeg to parse 'Duration: hh:mm:ss.ss' from stderr → seconds (float).
    """
    cmd = ["/opt/bin/ffmpeg", "-i", path]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    match = re.search(r"Duration:\s+(\d+):(\d+):(\d+\.\d+)", proc.stderr or "")
    if not match:
        logger.error("Could not parse duration from ffmpeg output")
        return 0.0
    h, m, s = int(match[1]), int(match[2]), float(match[3])
    return h * 3600 + m * 60 + s


def ensure_tmp_dir(dir_name: str = "/tmp/segments") -> str:
    os.makedirs(dir_name, exist_ok=True)
    return dir_name


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
def lambda_handler(event: Dict[str, Any], context) -> Any:
    try:
        logger.info("Incoming event", extra={"event": event})

        # ── Extract payload ──────────────────────────────────────────────
        payload = event.get("payload", {})
        data    = payload.get("data", {})
        assets  = payload.get("assets", [])

        # ── Try direct presignedUrl first ─────────────────────────────────
        presigned_url = data.get("presignedUrl")
        source_bucket = data.get("bucket")
        source_key    = data.get("key")
        use_s3_direct = False

        if not (presigned_url and source_bucket and source_key):
            logger.info("No presignedUrl in data; falling back to proxy asset")
            proxy = next(
                (r for r in assets[0].get("DerivedRepresentations", [])
                 if r.get("Purpose") == "proxy"),
                None
            )
            if not proxy:
                return _bad_request("Missing presignedUrl and no proxy DerivedRepresentation found")

            loc = proxy["StorageInfo"]["PrimaryLocation"]
            source_bucket = loc["Bucket"]
            source_key = loc.get("ObjectKey", {}).get("FullPath") or loc.get("path")
            if not source_key:
                return _bad_request("Proxy representation missing S3 key")

            # mark to download directly from S3
            use_s3_direct = True

        # ── Extract IDs ──────────────────────────────────────────────────────
        try:
            inventory_id = assets[0]["InventoryID"]
            asset_id     = assets[0]["DigitalSourceAsset"]["ID"]
        except Exception:
            return _bad_request("Could not locate InventoryID or DigitalSourceAsset ID")

        # ── Determine chunk duration ─────────────────────────────────────────
        raw = os.getenv("CHUNK_DURATION") or str(data.get("chunkDuration", "10"))
        try:
            chunk_duration = int(raw)
        except ValueError:
            chunk_duration = 10
            logger.warning("Invalid CHUNK_DURATION – defaulting to 10 s")

        # ── Download source file into /tmp ──────────────────────────────────
        input_path = os.path.join(tempfile.gettempdir(), os.path.basename(source_key))
        if use_s3_direct:
            logger.info("Downloading proxy asset directly from S3",
                        extra={"bucket": source_bucket, "key": source_key})
            try:
                s3_client.download_file(source_bucket, source_key, input_path)
            except Exception as e:
                return _error(500, f"Failed to download from S3 directly: {e}")
        else:
            logger.info("Downloading via presigned URL", extra={"url": presigned_url})
            try:
                r = requests.get(presigned_url)
                r.raise_for_status()
                with open(input_path, "wb") as f:
                    f.write(r.content)
            except Exception as e:
                return _error(500, f"Failed to download presigned URL: {e}")

        # ── Segment with ffmpeg ─────────────────────────────────────────────
        total_duration = get_audio_duration(input_path)
        output_dir     = ensure_tmp_dir()
        base_name      = os.path.splitext(os.path.basename(source_key))[0]
        output_pattern = os.path.join(output_dir, f"{base_name}_segment_%03d.mp3")

        ffmpeg_cmd = [
            "/opt/bin/ffmpeg", "-hide_banner", "-loglevel", "error",
            "-i", input_path,
            "-f", "segment",
            "-segment_time", str(chunk_duration),
            "-c:a", "libmp3lame", "-q:a", "2",
            output_pattern,
        ]
        logger.info("Running ffmpeg", extra={"cmd": " ".join(ffmpeg_cmd)})
        try:
            subprocess.check_call(ffmpeg_cmd)
        except subprocess.CalledProcessError as e:
            return _error(500, f"ffmpeg failed: {e}")

        # ── Upload chunks & build response ─────────────────────────────────
        upload_bucket   = os.getenv("MEDIA_ASSETS_BUCKET_NAME", source_bucket)
        chunk_locations: List[Dict[str, Any]] = []

        for idx, fname in enumerate(sorted(os.listdir(output_dir)), start=1):
            if not fname.startswith(f"{base_name}_segment_"):
                continue

            path    = os.path.join(output_dir, fname)
            seg_key = f"chunks/{asset_id}/{fname}"
            try:
                s3_client.upload_file(path, upload_bucket, seg_key)
            except Exception as e:
                return _error(500, f"Error uploading segment {idx}: {e}")

            start   = (idx - 1) * chunk_duration
            seg_dur = min(chunk_duration, max(total_duration - start, 0))
            end     = start + seg_dur

            chunk_locations.append({
                "bucket": upload_bucket,
                "key": seg_key,
                "url": f"s3://{upload_bucket}/{seg_key}",
                "index": idx,
                "start_time": start,
                "end_time": end,
                "start_time_formatted": format_duration(start),
                "end_time_formatted":   format_duration(end),
                "duration": seg_dur,
                "duration_formatted": format_duration(seg_dur),
                "size_bytes": os.path.getsize(path),
                "mediaType": "Audio",
                "asset_id": asset_id,
                "inventory_id": inventory_id
            })

        return chunk_locations

    except Exception as e:
        logger.exception("Unhandled exception")
        return _error(500, f"Unhandled error: {e}")
