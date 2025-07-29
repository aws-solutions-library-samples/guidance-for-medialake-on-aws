import decimal
import json
import os
import re
import subprocess
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict

import boto3
from aws_lambda_powertools import Logger, Tracer
from lambda_middleware import lambda_middleware
from pymediainfo import MediaInfo

# ── config / clients ───────────────────────────────────────────────
logger = Logger()
tracer = Tracer()

SIGNED_URL_TIMEOUT = 60
TABLE_NAME = os.environ["MEDIALAKE_ASSET_TABLE"]

s3_client = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")
asset_table = dynamodb.Table(TABLE_NAME)

TMP_DIR = Path("/tmp")


# ── helper: strip Decimal → int/float ──────────────────────────────
def _strip_decimals(obj):
    if isinstance(obj, list):
        return [_strip_decimals(v) for v in obj]
    if isinstance(obj, dict):
        return {k: _strip_decimals(v) for k, v in obj.items()}
    if isinstance(obj, decimal.Decimal):
        return int(obj) if obj % 1 == 0 else float(obj)
    return obj


# ── helper: convert all numbers to Decimal for DynamoDB ────────────
def _decimalize(obj: Any) -> Any:
    if isinstance(obj, list):
        return [_decimalize(v) for v in obj]
    if isinstance(obj, dict):
        return {k: _decimalize(v) for k, v in obj.items()}
    if isinstance(obj, float) or isinstance(obj, int):
        # Use str() to avoid binary float quirks
        return Decimal(str(obj))
    return obj


# ── helpers: field sanitization ────────────────────────────────────
def _sanitize_field_name(field_name: str) -> str:
    sanitized = field_name.replace("@", "").replace("#", "")
    sanitized = re.sub(r"(?<!^)(?=[A-Z])", "_", sanitized)
    sanitized = sanitized.lower()
    sanitized = re.sub(r"[^a-z0-9_]", "_", sanitized)
    sanitized = re.sub(r"_+", "_", sanitized).strip("_")
    if sanitized and sanitized[0].isdigit():
        sanitized = f"field_{sanitized}"
    return sanitized or "unknown_field"


def _should_be_duration_field(field_name: str) -> bool:
    field_lower = field_name.lower()
    duration_patterns = [
        "duration",
        "time",
        "length",
        "runtime",
        "play",
        "playback",
        "total",
        "media",
        "stream",
        "file",
        "track",
    ]
    if any(p in field_lower for p in duration_patterns):
        return True
    time_suffixes = ["_ts", "_time", "_duration", "_length", "_runtime"]
    return any(suffix in field_lower for suffix in time_suffixes)


def _should_be_numeric_field(field_name: str) -> bool:
    if _should_be_duration_field(field_name):
        return False
    field_lower = field_name.lower()
    numeric_patterns = [
        "rate",
        "bitrate",
        "framerate",
        "samplerate",
        "count",
        "number",
        "channels",
        "channel",
        "size",
        "width",
        "height",
        "filesize",
        "index",
        "id",
        "level",
        "profile",
        "fps",
        "delay",
        "stream_size",
    ]
    if any(p in field_lower for p in numeric_patterns):
        return True
    numeric_indicators = [
        "_rate",
        "_count",
        "_size",
        "_width",
        "_height",
        "_fps",
        "_id",
        "_index",
    ]
    return any(ind in field_lower for ind in numeric_indicators)


def _sanitize_field_value(value: Any, field_name: str = "") -> Any:
    if isinstance(value, (dict, list)):
        return str(value)
    if isinstance(value, (int, float, str, bool)) or value is None:
        if _should_be_duration_field(field_name):
            try:
                return float(value)
            except Exception:
                return value
        return value
    if isinstance(value, str) and _should_be_numeric_field(field_name):
        try:
            return float(value) if "." in value else int(value)
        except Exception:
            pass
    return str(value)


# ── helpers: analysis tools ────────────────────────────────────────
def run_ffprobe(file_path: str) -> Dict[str, Any]:
    cmd = [
        "/opt/bin/ffprobe",
        "-v",
        "error",
        "-show_streams",
        "-show_format",
        "-print_format",
        "json",
        file_path,
    ]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if res.returncode:
        raise RuntimeError("ffprobe failed: " + res.stderr.decode())
    return json.loads(res.stdout.decode())


def run_mediainfo(file_path: str) -> Dict[str, Any]:
    return json.loads(MediaInfo.parse(file_path, output="JSON"))


def merge_metadata(ff: Dict, mi: Dict) -> Dict[str, Any]:
    merged = {"general": {}, "video": [], "audio": []}
    ff_fmt = ff.get("format", {})
    mi_gen = next(
        (
            t
            for t in mi.get("media", {}).get("track", [])
            if t.get("@type") == "General"
        ),
        {},
    )
    merged_gen = {k: v for k, v in ff_fmt.items() if k != "streams"}
    for k, v in mi_gen.items():
        if v and merged_gen.get(k) != v:
            merged_gen[k] = v
    merged["general"] = merged_gen

    ff_streams = ff.get("streams", [])
    mi_tracks = mi.get("media", {}).get("track", [])
    video_ff = [s for s in ff_streams if s.get("codec_type") == "video"]
    audio_ff = [s for s in ff_streams if s.get("codec_type") == "audio"]
    video_mi = [t for t in mi_tracks if t.get("@type") == "Video"]
    audio_mi = [t for t in mi_tracks if t.get("@type") == "Audio"]

    for i, s in enumerate(video_ff):
        merged_v = {**s}
        if i < len(video_mi):
            for k, v in video_mi[i].items():
                if v and not merged_v.get(k):
                    key = _sanitize_field_name(k)
                    merged_v[key] = _sanitize_field_value(v, key)
        merged["video"].append(merged_v)

    for i, s in enumerate(audio_ff):
        merged_a = {**s}
        if i < len(audio_mi):
            for k, v in audio_mi[i].items():
                if v and not merged_a.get(k):
                    key = _sanitize_field_name(k)
                    merged_a[key] = _sanitize_field_value(v, key)
        merged["audio"].append(merged_a)

    return merged


# ── helpers: ID sanitisation ───────────────────────────────────────
def clean_asset_id(val: str) -> str:
    parts = val.split(":")
    uuid = parts[-2] if parts[-1] == "master" else parts[-1]
    return f"asset:uuid:{uuid}"


# ── handler ────────────────────────────────────────────────────────
@lambda_middleware(event_bus_name=os.getenv("EVENT_BUS_NAME", "default-event-bus"))
@logger.inject_lambda_context
@tracer.capture_lambda_handler
def lambda_handler(event, context):
    steps, audio_specs, updated_assets = {}, {}, {}

    # remove try/except so any exception bubbles up
    assets = event.get("payload", {}).get("assets", [])
    if not assets:
        raise ValueError("No assets found in event.payload.assets")

    for asset in assets:
        inv_raw = asset.get("InventoryID")
        if not inv_raw:
            continue

        inv_id = clean_asset_id(inv_raw)

        # download
        src = asset["DigitalSourceAsset"]["MainRepresentation"]
        bucket = src["StorageInfo"]["PrimaryLocation"]["Bucket"]
        key = src["StorageInfo"]["PrimaryLocation"]["ObjectKey"]["FullPath"]
        local = TMP_DIR / Path(key).name
        s3_client.download_file(bucket, key, str(local))
        steps.setdefault(inv_id, {})["S3_download"] = "Success"

        # analyse
        ff = run_ffprobe(str(local))
        steps[inv_id]["FFProbe"] = "Success"
        mi = run_mediainfo(str(local))
        steps[inv_id]["MediaInfo"] = "Success"
        merged = merge_metadata(ff, mi)

        # extract audio spec
        first_audio = merged.get("audio", [{}])[0]
        audio_specs[inv_id] = {
            "Duration": first_audio.get("duration"),
            "Codec": first_audio.get("codec_name"),
            "SampleRate": first_audio.get("sample_rate"),
            "Channels": first_audio.get("channels"),
        }

        # fetch existing metadata, merge and decimalize
        existing_emb = (
            asset_table.get_item(Key={"InventoryID": inv_id})
            .get("Item", {})
            .get("Metadata", {})
            .get("EmbeddedMetadata", {})
        )
        merged_emb = {**existing_emb, "audio": merged.get("audio", [])}
        merged_emb_decimal = _decimalize(merged_emb)

        # store in DDB (now using only Decimals for numbers)
        asset_table.update_item(
            Key={"InventoryID": inv_id},
            UpdateExpression="SET #md.#em = :m",
            ExpressionAttributeNames={"#md": "Metadata", "#em": "EmbeddedMetadata"},
            ExpressionAttributeValues={":m": merged_emb_decimal},
        )
        steps[inv_id]["DDB_update"] = "Success"

        # verify
        updated_item = asset_table.get_item(Key={"InventoryID": inv_id}).get("Item", {})
        updated_assets[inv_id] = updated_item
        steps[inv_id]["DDB_get"] = "Success"

    # strip Decimal objects before returning
    return {
        "statusCode": 200,
        "body": json.dumps(
            {
                "message": "Process completed successfully",
                "steps": _strip_decimals(steps),
                "audio_specs": _strip_decimals(audio_specs),
                "updatedAsset": _strip_decimals(updated_assets),
            }
        ),
    }
