import json, os, re, subprocess, decimal
from datetime import datetime
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

s3_client   = boto3.client("s3")
dynamodb    = boto3.resource("dynamodb")
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

# ── helpers: field sanitization ────────────────────────────────────
def _sanitize_field_name(field_name: str) -> str:
    """Sanitize all field names to avoid conflicts with object mapping."""
    # Remove problematic characters and prefixes
    sanitized = field_name.replace("@", "").replace("#", "")
    
    # Convert to lowercase with underscores (snake_case)
    # This ensures consistent naming and avoids case-sensitive conflicts
    import re
    
    # Insert underscores before uppercase letters (CamelCase to snake_case)
    sanitized = re.sub(r'(?<!^)(?=[A-Z])', '_', sanitized)
    
    # Convert to lowercase
    sanitized = sanitized.lower()
    
    # Replace any remaining problematic characters with underscores
    sanitized = re.sub(r'[^a-z0-9_]', '_', sanitized)
    
    # Remove multiple consecutive underscores
    sanitized = re.sub(r'_+', '_', sanitized)
    
    # Remove leading/trailing underscores
    sanitized = sanitized.strip('_')
    
    # Ensure field name doesn't start with a number
    if sanitized and sanitized[0].isdigit():
        sanitized = f"field_{sanitized}"
    
    # Ensure we have a valid field name
    if not sanitized:
        sanitized = "unknown_field"
    
    return sanitized

def _sanitize_field_value(value: Any, field_name: str = "") -> Any:
    """Ensure field values are simple types, not complex objects."""
    if isinstance(value, (dict, list)):
        # Convert complex objects to string representation to avoid mapping conflicts
        return str(value)
    elif isinstance(value, (int, float, str, bool)) or value is None:
        return value
    else:
        # For numeric-looking strings, try to preserve as numbers if the field should be numeric
        if isinstance(value, str) and _should_be_numeric_field(field_name):
            try:
                # Try to convert to int first, then float
                if '.' in value:
                    return float(value)
                else:
                    return int(value)
            except (ValueError, TypeError):
                pass
        
        # Convert any other type to string
        return str(value)

def _should_be_numeric_field(field_name: str) -> bool:
    """Check if a field should remain numeric based on its name."""
    numeric_fields = {
        'channels', 'channel_count', 'sample_rate', 'bit_rate', 'bitrate',
        'duration', 'width', 'height', 'frame_rate', 'framerate', 'fps',
        'size', 'filesize', 'file_size', 'length', 'count', 'number',
        'index', 'id', 'level', 'profile', 'delay', 'stream_size'
    }
    
    # Convert field name to lowercase for comparison
    field_lower = field_name.lower()
    
    # Check exact matches
    if field_lower in numeric_fields:
        return True
    
    # Check if field name contains numeric indicators
    numeric_indicators = ['_rate', '_count', '_size', '_duration', '_width', '_height', '_fps']
    return any(indicator in field_lower for indicator in numeric_indicators)

# ── helpers: analysis tools ────────────────────────────────────────
def run_ffprobe(file_path: str) -> Dict[str, Any]:
    cmd = ["/opt/bin/ffprobe", "-v", "error",
           "-show_streams", "-show_format", "-print_format", "json", file_path]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if res.returncode:
        raise RuntimeError("ffprobe failed: " + res.stderr.decode())
    return json.loads(res.stdout.decode())

def run_mediainfo(file_path: str) -> Dict[str, Any]:
    return json.loads(MediaInfo.parse(file_path, output="JSON"))

def merge_metadata(ff: Dict, mi: Dict) -> Dict[str, Any]:
    merged = {"general": {}, "video": [], "audio": []}
    ff_fmt  = ff.get("format", {})
    mi_gen  = next((t for t in mi.get("media", {}).get("track", [])
                    if t.get("@type") == "General"), {})
    merged_gen = {k: v for k, v in ff_fmt.items() if k != "streams"}
    for k, v in mi_gen.items():
        if v and (k not in merged_gen or merged_gen[k] != v):
            merged_gen[k] = v
    merged["general"] = merged_gen

    ff_streams = ff.get("streams", [])
    mi_tracks  = mi.get("media", {}).get("track", [])
    video_ff = [s for s in ff_streams if s.get("codec_type") == "video"]
    audio_ff = [s for s in ff_streams if s.get("codec_type") == "audio"]
    video_mi = [t for t in mi_tracks if t.get("@type") == "Video"]
    audio_mi = [t for t in mi_tracks if t.get("@type") == "Audio"]

    for i, s in enumerate(video_ff):
        merged_v = {**s}
        if i < len(video_mi):
            for k, v in video_mi[i].items():
                if v and not merged_v.get(k):
                    # Sanitize field name and ensure it's a simple value
                    sanitized_key = _sanitize_field_name(k)
                    sanitized_value = _sanitize_field_value(v, sanitized_key)
                    merged_v[sanitized_key] = sanitized_value
        merged["video"].append(merged_v)

    for i, s in enumerate(audio_ff):
        merged_a = {**s}
        if i < len(audio_mi):
            for k, v in audio_mi[i].items():
                if v and not merged_a.get(k):
                    # Sanitize field name and ensure it's a simple value
                    sanitized_key = _sanitize_field_name(k)
                    sanitized_value = _sanitize_field_value(v, sanitized_key)
                    merged_a[sanitized_key] = sanitized_value
        merged["audio"].append(merged_a)

    return merged

# ── helpers: ID sanitisation ───────────────────────────────────────
def clean_asset_id(val: str) -> str:
    parts = val.split(":")
    uuid  = parts[-2] if parts[-1] == "master" else parts[-1]
    return f"asset:uuid:{uuid}"

# ── handler ────────────────────────────────────────────────────────
@lambda_middleware(event_bus_name=os.getenv("EVENT_BUS_NAME", "default-event-bus"))
@logger.inject_lambda_context
@tracer.capture_lambda_handler
def lambda_handler(event, context):
    steps, audio_specs, updated_assets = {}, {}, {}

    try:
        assets = event.get("payload", {}).get("assets", [])
        if not assets:
            raise ValueError("No assets found in event.payload.assets")

        for asset in assets:
            inv_raw = asset.get("InventoryID")
            if not inv_raw:
                continue
            inv_id = clean_asset_id(inv_raw)

            # download
            src      = asset["DigitalSourceAsset"]["MainRepresentation"]
            bucket   = src["StorageInfo"]["PrimaryLocation"]["Bucket"]
            key      = src["StorageInfo"]["PrimaryLocation"]["ObjectKey"]["FullPath"]
            local    = TMP_DIR / Path(key).name
            s3_client.download_file(bucket, key, str(local))
            steps.setdefault(inv_id, {})["S3_download"] = "Success"

            # analyse
            ff = run_ffprobe(str(local));                 steps[inv_id]["FFProbe"]  = "Success"
            mi = run_mediainfo(str(local));              steps[inv_id]["MediaInfo"] = "Success"
            merged = merge_metadata(ff, mi)

            # extract audio spec
            first_audio = merged.get("audio", [{}])[0]
            audio_specs[inv_id] = {
                "Duration":   first_audio.get("duration"),
                "Codec":      first_audio.get("codec_name"),
                "SampleRate": first_audio.get("sample_rate"),
                "Channels":   first_audio.get("channels"),
            }

            # merge & store in DDB
            existing_emb = (asset_table.get_item(Key={"InventoryID": inv_id})
                                          .get("Item", {})
                                          .get("Metadata", {})
                                          .get("EmbeddedMetadata", {}))
            merged_emb   = {**existing_emb, "audio": merged.get("audio", [])}
            asset_table.update_item(
                Key={"InventoryID": inv_id},
                UpdateExpression="SET #md.#em = :m",
                ExpressionAttributeNames={"#md": "Metadata", "#em": "EmbeddedMetadata"},
                ExpressionAttributeValues={":m": merged_emb},
            )
            steps[inv_id]["DDB_update"] = "Success"

            updated_item = asset_table.get_item(Key={"InventoryID": inv_id}).get("Item", {})
            updated_assets[inv_id] = updated_item
            steps[inv_id]["DDB_get"] = "Success"

        # strip Decimal objects before serialising
        safe_steps        = _strip_decimals(steps)
        safe_audio_specs  = _strip_decimals(audio_specs)
        safe_updated_assets = _strip_decimals(updated_assets)

        return {
            "statusCode": 200,
            "body": json.dumps({
                "message":      "Process completed successfully",
                "steps":        safe_steps,
                "audio_specs":  safe_audio_specs,
                "updatedAsset": safe_updated_assets,
            }),
        }

    except Exception as exc:
        logger.exception("Processing failed")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(exc), "steps": _strip_decimals(steps)}),
        }
