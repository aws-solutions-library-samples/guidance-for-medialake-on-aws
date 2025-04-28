import json
import os
import re
import subprocess
from datetime import datetime

import boto3
from aws_lambda_powertools import Logger, Tracer
from lambda_middleware import lambda_middleware
from pymediainfo import MediaInfo


# ── config / clients ───────────────────────────────────────────────
logger = Logger()
tracer = Tracer()

SIGNED_URL_TIMEOUT = 60
table_name = os.environ["MEDIALAKE_ASSET_TABLE"]

s3_client = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")
asset_table = dynamodb.Table(table_name)


# ── helpers: analysis tools ────────────────────────────────────────
def run_ffprobe(file_path: str) -> dict:
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
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode == 0:
        return json.loads(result.stdout.decode())
    raise RuntimeError("ffprobe failed: " + result.stderr.decode())


def run_mediainfo(file_path: str) -> dict:
    media_info = MediaInfo.parse(file_path, output="JSON")
    return json.loads(media_info)


def merge_metadata(ffprobe_data: dict, mediainfo_data: dict) -> dict:
    merged = {"general": {}, "video": [], "audio": []}

    ff_format = ffprobe_data.get("format", {})
    mi_general = next(
        (t for t in mediainfo_data.get("media", {}).get("track", []) if t.get("@type") == "General"),
        {},
    )

    # general
    merged_general = {k: v for k, v in ff_format.items() if k != "streams"}
    for k, v in mi_general.items():
        if k not in merged_general or (merged_general[k] != v and v):
            merged_general[k] = v
    merged["general"] = merged_general

    # stream lists
    ff_streams = ffprobe_data.get("streams", [])
    ff_video_streams = [s for s in ff_streams if s.get("codec_type") == "video"]
    ff_audio_streams = [s for s in ff_streams if s.get("codec_type") == "audio"]

    mi_tracks = mediainfo_data.get("media", {}).get("track", [])
    mi_video_tracks = [t for t in mi_tracks if t.get("@type") == "Video"]
    mi_audio_tracks = [t for t in mi_tracks if t.get("@type") == "Audio"]

    # video
    for i, ff_video in enumerate(ff_video_streams):
        merged_video = {k: v for k, v in ff_video.items()}
        if i < len(mi_video_tracks):
            for k, v in mi_video_tracks[i].items():
                if k not in merged_video or (not merged_video[k] and v):
                    merged_video[k] = v
        merged["video"].append(merged_video)

    # audio
    for i, ff_audio in enumerate(ff_audio_streams):
        merged_audio = {k: v for k, v in ff_audio.items()}
        if i < len(mi_audio_tracks):
            for k, v in mi_audio_tracks[i].items():
                if k not in merged_audio or (not merged_audio[k] and v):
                    merged_audio[k] = v
        merged["audio"].append(merged_audio)

    return merged


# ── helpers: sanitisation / misc ───────────────────────────────────
def clean_asset_id(value: str) -> str:
    parts = value.split(":")
    uuid_part = parts[-2] if parts[-1] == "master" else parts[-1]
    return f"asset:uuid:{uuid_part}"


def normalize_date_string(s: str) -> str:
    m = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})$", s)
    if m:
        y, mn, d = m.groups()
        return f"{y}-{mn.zfill(2)}-{d.zfill(2)}"
    return s


def normalize_date_time_string(s: str) -> str:
    m = re.match(r"^(\d{4}-\d{2}-\d{2})T(\d{2}):(\d{2}):(\d{3})Z$", s)
    if m:
        date, hh, mm, ms = m.groups()
        return f"{date}T{hh}:{mm}:00.{ms}Z"
    return s


def is_likely_base64(s: str) -> bool:
    return isinstance(s, str) and len(s) > 100 and bool(re.match(r"^[A-Za-z0-9+/]+={0,2}$", s))


def clip_bytes(byte_data: bytes | bytearray, limit: int = 60) -> str:
    if not byte_data:
        return ""
    hex_vals = " ".join(f"{b:02x}" for b in byte_data[:limit])
    return f"{hex_vals}\n... and {len(byte_data) - limit} more" if len(byte_data) > limit else hex_vals


def remove_base64_fields(obj):
    if isinstance(obj, list):
        filtered = []
        for item in obj:
            if is_likely_base64(item):
                continue
            if isinstance(item, (dict, list)):
                remove_base64_fields(item)
            filtered.append(item)
        obj.clear()
        obj.extend(filtered)

    elif isinstance(obj, dict):
        keys_to_delete = []
        for k, v in obj.items():
            if is_likely_base64(v) or (
                isinstance(v, list) and v and all(is_likely_base64(el) for el in v)
            ):
                keys_to_delete.append(k)
            else:
                remove_base64_fields(v)
        for k in keys_to_delete:
            del obj[k]


def force_simple_values(obj):
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj

    if isinstance(obj, (bytes, bytearray)):
        return clip_bytes(obj)

    if isinstance(obj, list):
        return [force_simple_values(v) for v in obj if v is not None]

    if isinstance(obj, dict):
        if {"Dt", "#value"} <= obj.keys():
            return f"Binary data: {obj['#value'][:30]}..."
        return {k: force_simple_values(v) for k, v in obj.items() if v is not None}

    return str(obj)


def sanitize_metadata(md: dict) -> dict:
    def sanitize_value(v):
        if isinstance(v, str):
            if v.startswith("0000-00-00"):
                return None
            v = normalize_date_time_string(normalize_date_string(v))
            try:
                datetime.fromisoformat(v.replace("Z", "+00:00"))
            except ValueError:
                pass
            v = (
                "".join(c for c in v if ord(c) >= 32)
                .encode("ascii", "ignore")
                .decode("ascii")
                .replace("\\", "\\\\")
                .replace('"', '\\"')
                .replace("'", "\\'")
                .replace("\0", "\\0")
            )
            return v

        if isinstance(v, (bytes, bytearray)):
            return clip_bytes(v)

        if isinstance(v, dict):
            cleaned = {sanitize_key(k): sanitize_value(val) for k, val in v.items()}
            return cleaned or None

        if isinstance(v, list):
            lst = [sanitize_value(item) for item in v if sanitize_value(item) is not None]
            return lst or None

        return str(v) if v is not None else None

    def sanitize_key(k: str) -> str:
        return "".join(part.capitalize() for part in k.replace("@", "").split("_"))

    sanitized = {sanitize_key(k): sanitize_value(v) for k, v in md.items()}
    remove_base64_fields(sanitized)
    return force_simple_values(sanitized)


# ── lambda handler ────────────────────────────────────────────────
@lambda_middleware(event_bus_name=os.environ.get("EVENT_BUS_NAME", "default-event-bus"))
@logger.inject_lambda_context
@tracer.capture_lambda_handler
def lambda_handler(event, context):
    steps = {}
    try:
        # ---------------------------------------------------------------------
        # 1. unwrap event shape (supports with/without extra “detail” layer)
        # ---------------------------------------------------------------------
        input_data = event.get("input", {})
        if "detail" in input_data:  # state-machine / EventBridge wrapper
            input_data = input_data["detail"]

        digital_src = input_data["DigitalSourceAsset"]
        inventory_id = input_data.get("InventoryID", "")
        clean_inventory_id = clean_asset_id(inventory_id)

        s3_bucket = (
            digital_src["MainRepresentation"]["StorageInfo"]["PrimaryLocation"]["Bucket"]
        )
        s3_key = (
            digital_src["MainRepresentation"]["StorageInfo"]["PrimaryLocation"]["ObjectKey"][
                "FullPath"
            ]
        )

        # ---------------------------------------------------------------------
        # 2. download master      /tmp/<filename>
        # ---------------------------------------------------------------------
        local_path = f"/tmp/{os.path.basename(s3_key)}"
        s3_client.download_file(s3_bucket, s3_key, local_path)
        steps[clean_inventory_id] = {"S3_download": "Success"}
        logger.info("Downloaded", extra={"bucket": s3_bucket, "key": s3_key})

        # ---------------------------------------------------------------------
        # 3. analyse (FFprobe + MediaInfo)
        # ---------------------------------------------------------------------
        ff_data = run_ffprobe(local_path)
        steps[clean_inventory_id]["FFProbe_analysis"] = "Success"

        mi_data = run_mediainfo(local_path)
        steps[clean_inventory_id]["Mediainfo_analysis"] = "Success"

        merged = merge_metadata(ff_data, mi_data)

        # keep just audio info (for the spec the pipeline needs)
        AudioSpec = {
            "Duration": merged["audio"][0].get("duration"),
            "Codec": merged["audio"][0].get("codec_name"),
            "SampleRate": merged["audio"][0].get("sample_rate"),
            "Channels": merged["audio"][0].get("channels"),
        }
        merged.pop("video", None)

        # ---------------------------------------------------------------------
        # 4. DynamoDB upsert (merge embedded metadata)
        # ---------------------------------------------------------------------
        existing_item = asset_table.get_item(Key={"InventoryID": clean_inventory_id}).get(
            "Item", {}
        )
        existing_emd = existing_item.get("Metadata", {}).get("EmbeddedMetadata", {})

        sanitized = sanitize_metadata(merged)
        remove_base64_fields(sanitized)

        merged_metadata = {**existing_emd, **sanitized}

        response = asset_table.update_item(
            Key={"InventoryID": clean_inventory_id},
            UpdateExpression="SET #md.#em = :m",
            ExpressionAttributeNames={"#md": "Metadata", "#em": "EmbeddedMetadata"},
            ExpressionAttributeValues={":m": merged_metadata},
            ReturnValues="UPDATED_NEW",
        )

        logger.info("DynamoDB updated", extra={"resp": response})
        steps[clean_inventory_id]["DDB_update"] = "Success"

        # ---------------------------------------------------------------------
        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "message": "Process completed successfully",
                    "steps": steps,
                    "audio_spec": AudioSpec,
                }
            ),
        }

    except Exception as exc:
        logger.exception("Unhandled error", exc_info=exc)
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(exc), "steps": steps}),
        }
