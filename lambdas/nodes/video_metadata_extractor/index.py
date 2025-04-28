import os
import json
import re
import subprocess
import datetime
from pathlib import Path
from typing import Any, Dict, List

import boto3
from boto3.dynamodb.conditions import Key
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext
from pymediainfo import MediaInfo

from lambda_middleware import lambda_middleware   # <- your own decorator

# ─── constants ──────────────────────────────────────────────────────────
SIGNED_URL_TIMEOUT = 60
FFPROBE_BIN = "/opt/bin/ffprobe"
TMP_DIR = Path("/tmp")

logger = Logger()
tracer = Tracer()

s3          = boto3.client("s3")
dynamodb    = boto3.resource("dynamodb")
asset_table = dynamodb.Table(os.environ["MEDIALAKE_ASSET_TABLE"])

# ─── helpers ────────────────────────────────────────────────────────────
def run_ffprobe(file_path: str) -> Dict[str, Any]:
    """Return ffprobe JSON for a file, raise on error."""
    result = subprocess.run(
        [FFPROBE_BIN, "-v", "error", "-show_streams", "-show_format",
         "-print_format", "json", file_path],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode:
        raise RuntimeError(f"ffprobe failed: {result.stderr.decode()}")
    return json.loads(result.stdout)

def run_mediainfo(file_path: str) -> Dict[str, Any]:
    """Return MediaInfo JSON for a file."""
    return json.loads(MediaInfo.parse(file_path, output="JSON"))

def merge_metadata(ff: Dict, mi: Dict) -> Dict[str, Any]:
    """Very light merge – identical to your original logic."""
    merged = {"general": {}, "video": [], "audio": []}

    # general
    ff_general = {k: v for k, v in ff.get("format", {}).items() if k != "streams"}
    mi_general = next(
        (t for t in mi.get("media", {}).get("track", []) if t.get("@type") == "General"),
        {},
    )
    merged["general"] = {**ff_general, **mi_general}

    # streams
    ff_video = [s for s in ff.get("streams", []) if s.get("codec_type") == "video"]
    ff_audio = [s for s in ff.get("streams", []) if s.get("codec_type") == "audio"]
    mi_video = [t for t in mi.get("media", {}).get("track", []) if t.get("@type") == "Video"]
    mi_audio = [t for t in mi.get("media", {}).get("track", []) if t.get("@type") == "Audio"]

    # ── video streams ───────────────────────────────
    for i, stream in enumerate(ff_video):
        extra = mi_video[i] if i < len(mi_video) else {}
        merged["video"].append({**stream, **extra})

    # ── audio streams ───────────────────────────────
    for i, stream in enumerate(ff_audio):
        extra = mi_audio[i] if i < len(mi_audio) else {}
        merged["audio"].append({**stream, **extra})

    return merged

def clean_asset_id(asset_id: str) -> str:
    parts = asset_id.split(":")
    uuid = parts[-2] if parts[-1] == "master" else parts[-1]
    return f"asset:uuid:{uuid}"

def sanitize_metadata(data: Dict[str, Any]) -> Dict[str, Any]:
    """Drop huge blobs & control chars so OpenSearch / DynamoDB stay happy."""
    def is_blob(s: Any) -> bool:
        return isinstance(s, str) and len(s) > 100 and re.fullmatch(r"[A-Za-z0-9+/]+={0,2}", s or "")
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

# ─── handler ────────────────────────────────────────────────────────────
@lambda_middleware(event_bus_name=os.environ.get("EVENT_BUS_NAME", "default-event-bus"))
@logger.inject_lambda_context
@tracer.capture_lambda_handler
def lambda_handler(event: Dict[str, Any], context: LambdaContext):  # noqa: D401
    """
    Ingest *AssetCreated* event, enrich metadata & write back to DynamoDB.
    Expects `event["input"]["detail"]` to match the sample provided.
    """
    steps: Dict[str, Dict[str, str]] = {}

    try:
        detail          = event["input"]["detail"]          # <- fixed
        src             = detail["DigitalSourceAsset"]["MainRepresentation"]
        bucket          = src["StorageInfo"]["PrimaryLocation"]["Bucket"]
        key             = src["StorageInfo"]["PrimaryLocation"]["ObjectKey"]["FullPath"]
        inventory_id    = clean_asset_id(detail["InventoryID"])
        local_file      = TMP_DIR / Path(key).name

        # 1. download
        s3.download_file(bucket, key, str(local_file))
        steps.setdefault(inventory_id, {})["S3_download"] = "Success"

        # 2. probe
        ff_data = run_ffprobe(str(local_file))
        mi_data = run_mediainfo(str(local_file))
        steps[inventory_id]["Metadata_probe"] = "Success"

        merged = merge_metadata(ff_data, mi_data)
        sanitized = sanitize_metadata(merged)

        # 3. update DynamoDB
        asset_table.update_item(
            Key={"InventoryID": inventory_id},
            UpdateExpression="SET #m.#e = :v",
            ExpressionAttributeNames={"#m": "Metadata", "#e": "EmbeddedMetadata"},
            ExpressionAttributeValues={":v": sanitized},
        )
        steps[inventory_id]["DDB_update"] = "Success"

        # 4. build minimal video-spec object for response payload
        v0 = merged["video"][0] if merged["video"] else {}
        video_spec = {
            "Resolution": {"Width": v0.get("width"), "Height": v0.get("height")},
            "Codec": v0.get("codec_name"),
            "BitRate": v0.get("bit_rate"),
            "FrameRate": v0.get("r_frame_rate"),
        }

        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "message": "Process completed successfully",
                    "steps": steps,
                    "video_spec": video_spec,
                }
            ),
        }

    except Exception as exc:  # pylint: disable=broad-except
        logger.exception("Processing failed")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(exc), "steps": steps}),
        }
