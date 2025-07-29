import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any, Dict

import boto3
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext
from lambda_middleware import lambda_middleware  # your decorator
from pymediainfo import MediaInfo

# ─── constants ──────────────────────────────────────────────────────────
SIGNED_URL_TIMEOUT = 60
FFPROBE_BIN = "/opt/bin/ffprobe"
TMP_DIR = Path("/tmp")

logger = Logger()
tracer = Tracer()

s3 = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")
asset_table = dynamodb.Table(os.environ["MEDIALAKE_ASSET_TABLE"])


# ─── helpers ────────────────────────────────────────────────────────────
def run_ffprobe(file_path: str) -> Dict[str, Any]:
    """Return ffprobe JSON for a file, raise on error."""
    result = subprocess.run(
        [
            FFPROBE_BIN,
            "-v",
            "error",
            "-show_streams",
            "-show_format",
            "-print_format",
            "json",
            file_path,
        ],
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
    merged = {"general": {}, "video": [], "audio": []}

    # general
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

    # streams
    ff_video = [s for s in ff.get("streams", []) if s.get("codec_type") == "video"]
    ff_audio = [s for s in ff.get("streams", []) if s.get("codec_type") == "audio"]
    mi_video = [
        t for t in mi.get("media", {}).get("track", []) if t.get("@type") == "Video"
    ]
    mi_audio = [
        t for t in mi.get("media", {}).get("track", []) if t.get("@type") == "Audio"
    ]

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


# ─── handler ────────────────────────────────────────────────────────────
@lambda_middleware(event_bus_name=os.environ.get("EVENT_BUS_NAME", "default-event-bus"))
@logger.inject_lambda_context
@tracer.capture_lambda_handler
def lambda_handler(event: Dict[str, Any], context: LambdaContext):
    """
    Ingest AssetCreated events with this shape:
      {
        "metadata": { … },
        "payload": {
          "data": { … },
          "assets": [ { … asset1 … }, { … asset2 … }, … ]
        }
      }
    Enrich each asset’s metadata, upsert into DynamoDB,
    fetch it back immediately, and include in the response.
    """
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

            # 1. Download from S3
            s3.download_file(bucket, key, str(local_file))
            steps.setdefault(inv_id, {})["S3_download"] = "Success"

            # 2. Probe with ffprobe + MediaInfo
            ff = run_ffprobe(str(local_file))
            mi = run_mediainfo(str(local_file))
            steps[inv_id]["Metadata_probe"] = "Success"

            merged = merge_metadata(ff, mi)
            sanitized = sanitize_metadata(merged)

            # 3. Update DynamoDB
            asset_table.update_item(
                Key={"InventoryID": inv_id},
                UpdateExpression="SET #m.#e = :v",
                ExpressionAttributeNames={"#m": "Metadata", "#e": "EmbeddedMetadata"},
                ExpressionAttributeValues={":v": sanitized},
            )
            steps[inv_id]["DDB_update"] = "Success"

            # 4. Fetch the updated record back
            get_resp = asset_table.get_item(Key={"InventoryID": inv_id})
            updated_item = get_resp.get("Item", {})
            updated_assets[inv_id] = updated_item
            steps[inv_id]["DDB_get"] = "Success"

            # 5. Build minimal video spec
            v0 = merged.get("video", [{}])[0]
            video_specs[inv_id] = {
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
                    "video_specs": video_specs,
                    "updatedAsset": updated_assets,
                }
            ),
        }

    except Exception as exc:
        logger.exception("Processing failed")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(exc), "steps": steps}),
        }
