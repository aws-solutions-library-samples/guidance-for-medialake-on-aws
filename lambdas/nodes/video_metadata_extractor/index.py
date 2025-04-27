import boto3
import json
import subprocess
import os
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext
from boto3.dynamodb.conditions import Key

from pymediainfo import MediaInfo


# Initialize Powertools
logger = Logger()
tracer = Tracer()


SIGNED_URL_TIMEOUT = 60

table_name = os.environ["MEDIALAKE_ASSET_TABLE"]


s3_client = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")
asset_table = dynamodb.Table(table_name)


def run_ffprobe(file_path):
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
        return json.loads(result.stdout.decode("utf-8"))
    else:
        raise RuntimeError("ffprobe failed: " + result.stderr.decode("utf-8"))


def run_mediainfo(file_path):
    media_info = MediaInfo.parse(file_path, output="JSON")
    data = json.loads(media_info)
    return data


def merge_metadata(ffprobe_data, mediainfo_data):
    merged = {"general": {}, "video": [], "audio": []}

    ff_format = ffprobe_data.get("format", {})
    mi_general = {}
    for track in mediainfo_data.get("media", {}).get("track", []):
        if track.get("@type") == "General":
            mi_general = track
            break

    # Merge general info
    merged_general = {}
    for k, v in ff_format.items():
        if k not in ["streams"]:
            merged_general[k] = v
    for k, v in mi_general.items():
        if k not in merged_general or (merged_general[k] != v and v):
            merged_general[k] = v
    merged["general"] = merged_general

    ff_streams = ffprobe_data.get("streams", [])
    mi_video_tracks = [
        t
        for t in mediainfo_data.get("media", {}).get("track", [])
        if t.get("@type") == "Video"
    ]
    mi_audio_tracks = [
        t
        for t in mediainfo_data.get("media", {}).get("track", [])
        if t.get("@type") == "Audio"
    ]
    ff_video_streams = [s for s in ff_streams if s.get("codec_type") == "video"]
    ff_audio_streams = [s for s in ff_streams if s.get("codec_type") == "audio"]

    # Merge video streams
    for i, ff_video in enumerate(ff_video_streams):
        merged_video = {}
        for k, v in ff_video.items():
            merged_video[k] = v

        if i < len(mi_video_tracks):
            for k, v in mi_video_tracks[i].items():
                if k not in merged_video or (not merged_video[k] and v):
                    merged_video[k] = v
        merged["video"].append(merged_video)

    # Merge audio streams
    for i, ff_audio in enumerate(ff_audio_streams):
        merged_audio = {}
        for k, v in ff_audio.items():
            merged_audio[k] = v

        if i < len(mi_audio_tracks):
            for k, v in mi_audio_tracks[i].items():
                if k not in merged_audio or (not merged_audio[k] and v):
                    merged_audio[k] = v
        merged["audio"].append(merged_audio)

    return merged


def clean_asset_id(input_string: str) -> str:
    """
    Ensures the asset ID has the correct format without duplicates.
    Extracts just the UUID part and adds the proper prefix.
    """
    parts = input_string.split(":")
    uuid = parts[-1]
    if uuid == "master":
        uuid = parts[-2]
    return f"asset:uuid:{uuid}"


def sanitize_metadata(metadata):
    def sanitize_value(value):
        if isinstance(value, str):
            # Skip placeholder dates
            if value.startswith("0000-00-00"):
                return None
                
            # Try to normalize date strings
            normalized_value = normalize_date_string(value)
            normalized_value = normalize_date_time_string(normalized_value)
            
            # If it's a valid date, sanitize and return it
            try:
                import datetime
                datetime.datetime.fromisoformat(normalized_value.replace('Z', '+00:00'))
                # It's a valid date, sanitize and return
                return (
                    "".join(char for char in normalized_value if ord(char) >= 32)
                    .encode("ascii", "ignore")
                    .decode("ascii")
                    .replace("\\", "\\\\")
                    .replace('"', '\\"')
                    .replace("'", "\\'")
                    .replace("\0", "\\0")
                )
            except (ValueError, TypeError):
                # Not a date, apply regular sanitization
                return (
                    "".join(char for char in value if ord(char) >= 32)
                    .encode("ascii", "ignore")
                    .decode("ascii")
                    .replace("\\", "\\\\")
                    .replace('"', '\\"')
                    .replace("'", "\\'")
                    .replace("\0", "\\0")
                )
        elif isinstance(value, (bytes, bytearray)):
            # Handle binary data similar to Uint8Array in JS
            return clip_bytes(value)
        elif isinstance(value, dict):
            # Special handling for complex objects with binary data
            if "Dt" in value and "#value" in value and value.get("Dt") == "binary.base64":
                # This is a binary object with base64 encoding, convert to string
                return f"Binary data: {value.get('#value', '')[:30]}..."
            
            # Regular dictionary processing
            sanitized_dict = sanitize_dict(value)
            # If empty after sanitization, return None
            return sanitized_dict if sanitized_dict else None
        elif isinstance(value, list):
            sanitized_list = [sanitize_value(item) for item in value if sanitize_value(item) is not None]
            # If empty after sanitization, return None
            return sanitized_list if sanitized_list else None
        else:
            # Convert all other values to strings to ensure they're indexable
            if value is not None:
                return str(value)
            return None

    def sanitize_dict(d):
        result = {}
        for k, v in d.items():
            sanitized_value = sanitize_value(v)
            if sanitized_value is not None:
                result[sanitize_key(k)] = sanitized_value
        return result

    def sanitize_key(key):
        # Remove '@' and capitalize the first letter
        key = key.replace("@", "")
        # Convert from snake_case or camel_case to CamelCase
        return "".join(word.capitalize() for word in key.split("_"))

    # First pass: sanitize the metadata
    sanitized = {k.capitalize(): sanitize_value(v) for k, v in metadata.items() if sanitize_value(v) is not None}
    
    # Second pass: remove base64 blobs
    remove_base64_fields(sanitized)
    
    # Third pass: force all leaf values to be simple types
    sanitized = force_simple_values(sanitized)
    
    return sanitized

def force_simple_values(obj):
    """Ensure all complex objects are converted to simple types that OpenSearch can index"""
    if obj is None:
        return None
    
    if isinstance(obj, (str, int, float, bool)):
        return obj
    
    if isinstance(obj, (bytes, bytearray)):
        return clip_bytes(obj)
    
    if isinstance(obj, list):
        return [force_simple_values(item) for item in obj if item is not None]
    
    if isinstance(obj, dict):
        # Check for special binary object format
        if "Dt" in obj and "#value" in obj:
            return f"Binary data: {str(obj.get('#value', ''))[:30]}..."
        
        # Process regular dictionaries
        result = {}
        for k, v in obj.items():
            processed_value = force_simple_values(v)
            if processed_value is not None:
                result[k] = processed_value
        return result
    
    # Default: convert to string
    return str(obj)

def normalize_date_string(s):
    """Normalize date strings in format YYYY-M-D to YYYY-MM-DD"""
    import re
    m = re.match(r'^(\d{4})-(\d{1,2})-(\d{1,2})$', s)
    if m:
        y, mn, d = m.groups()
        return f"{y}-{mn.zfill(2)}-{d.zfill(2)}"
    return s

def normalize_date_time_string(s):
    """Normalize datetime strings"""
    import re
    m = re.match(r'^(\d{4}-\d{2}-\d{2})T(\d{2}):(\d{2}):(\d{3})Z$', s)
    if m:
        date, hh, mm, ms = m.groups()
        return f"{date}T{hh}:{mm}:00.{ms}Z"
    return s

def clip_bytes(byte_data, limit=60):
    """Format byte arrays similar to clipBytes in JS"""
    if not byte_data:
        return ""
    
    # Convert to hex representation
    hex_values = [f"{b:02x}" for b in byte_data[:limit]]
    result = " ".join(hex_values)
    
    # Add indication of remaining bytes
    if len(byte_data) > limit:
        result += f"\n... and {len(byte_data) - limit} more"
    
    return result

def is_likely_base64(s):
    """Check if a string is likely a base64 encoded blob"""
    import re
    return (
        isinstance(s, str) and
        len(s) > 100 and
        bool(re.match(r'^[A-Za-z0-9+/]+={0,2}$', s))
    )

def remove_base64_fields(obj):
    """Recursively remove base64 blobs from the metadata"""
    if isinstance(obj, list):
        # Filter out base64 string items
        filtered = []
        for item in obj:
            if is_likely_base64(item):
                continue
            elif item and isinstance(item, (dict, list)):
                remove_base64_fields(item)
                filtered.append(item)
            else:
                filtered.append(item)
        
        # Clear and repopulate the list
        obj.clear()
        obj.extend(filtered)
    
    elif isinstance(obj, dict):
        # Process dictionary items
        keys_to_delete = []
        for key, val in obj.items():
            if is_likely_base64(val):
                keys_to_delete.append(key)
            elif isinstance(val, list) and all(is_likely_base64(el) for el in val):
                keys_to_delete.append(key)
            else:
                remove_base64_fields(val)
        
        # Delete identified keys
        for key in keys_to_delete:
            del obj[key]



@logger.inject_lambda_context
@tracer.capture_lambda_handler
def lambda_handler(event, context):
    error = False
    steps_messages = {}
    error_message = ""
    print(event)

    try:
        input_data = event["input"]
        s3_source_bucket = input_data["DigitalSourceAsset"]["MainRepresentation"][
            "StorageInfo"
        ]["PrimaryLocation"]["Bucket"]
        s3_source_key = input_data["DigitalSourceAsset"]["MainRepresentation"][
            "StorageInfo"
        ]["PrimaryLocation"]["ObjectKey"]["FullPath"]
        inventory_id = input_data.get("InventoryID", "")
        clean_inventory_id = clean_asset_id(inventory_id)

        # Download file from S3 to /tmp/ for mediainfo
        local_path = f"/tmp/{os.path.basename(s3_source_key)}"
        try:
            s3_client.download_file(s3_source_bucket, s3_source_key, local_path)
            steps_messages[clean_inventory_id] = {"S3_download": "Success"}
            logger.info(
                "File downloaded successfully",
                extra={"bucket": s3_source_bucket, "key": s3_source_key},
            )
        except Exception as e:
            error_msg = f"Failed to download file: {str(e)}"
            logger.error(
                error_msg, extra={"bucket": s3_source_bucket, "key": s3_source_key}
            )
            steps_messages[clean_inventory_id] = {"S3_download": f"Failure: {e}"}
            raise Exception(error_msg)

        ff_data = run_ffprobe(local_path)
        steps_messages[clean_inventory_id]["FFProbe_analysis"] = "Success"
        logger.info("FFProbe analysis completed successfully")

        mi_data = run_mediainfo(local_path)
        steps_messages[clean_inventory_id]["Mediainfo_analysis"] = "Success"
        logger.info("MediaInfo analysis completed successfully")

        # Merge metadata
        merged_output = merge_metadata(ff_data, mi_data)

        # Create new representation for proxy
        output_bucket = os.environ.get("OUTPUT_BUCKET")
        output_key = f"{s3_source_bucket}/{s3_source_key.rsplit('.', 1)[0]}_proxy.mp4"
        asset_id = f"{clean_inventory_id}:proxy"

        # new_representation = {
        #     "ID": asset_id,
        #     "Type": "Video",
        #     "Format": "MP4",
        #     "Purpose": "proxy",
        #     "StorageInfo": {
        #         "PrimaryLocation": {
        #             "StorageType": "s3",
        #             "Provider": "aws",
        #             "Bucket": output_bucket,
        #             "ObjectKey": {
        #                 "FullPath": output_key,
        #             },
        #             "Status": "active",
        #             "FileInfo": {
        #                 "Size": os.path.getsize(
        #                     local_path
        #                 ),  # Approximate size, as proxy might be smaller
        #             },
        #         }
        #     },
        #     "VideoSpec": {
        #         "Resolution": {
        #             "Width": merged_output["video"][0].get("width"),
        #             "Height": merged_output["video"][0].get("height"),
        #         },
        #         "Codec": merged_output["video"][0].get("codec_name"),
        #         "BitRate": merged_output["video"][0].get("bit_rate"),
        #         "FrameRate": merged_output["video"][0].get("r_frame_rate"),
        #     },
        # }
        VideoSpec= {
            "Resolution": {
                "Width": merged_output["video"][0].get("width"),
                "Height": merged_output["video"][0].get("height"),
            },
            "Codec": merged_output["video"][0].get("codec_name"),
            "BitRate": merged_output["video"][0].get("bit_rate"),
            "FrameRate": merged_output["video"][0].get("r_frame_rate"),
        },

        existing_item = asset_table.get_item(
            Key={"InventoryID": clean_inventory_id}
        ).get("Item", {})
        existing_metadata = existing_item.get("Metadata", {}).get("EmbeddedMetadata", {})
        sanitized_merged_output = sanitize_metadata(merged_output)

        # Merge existing metadata with new metadata
        merged_metadata = {**existing_metadata, **sanitized_merged_output}

        # Update DynamoDB
        response = asset_table.update_item(
            Key={"InventoryID": clean_inventory_id},
            UpdateExpression="SET #md.#cm = :metadata",
            ExpressionAttributeNames={"#md": "Metadata", "#cm": "EmbeddedMetadata"},
            ExpressionAttributeValues={
                ":metadata": merged_metadata,
            },
            ReturnValues="UPDATED_NEW",
        )

        logger.info(
            "DynamoDB update response",
            extra={"response": response, "inventory_id": clean_inventory_id},
        )
        steps_messages[clean_inventory_id]["DDB_update"] = "Success"

        return {
            "statusCode": 200,
            "body": json.dumps(
                {"message": "Process completed successfully", "steps": steps_messages, "video_spec":VideoSpec}
            ),
        }

    except Exception as e:
        error_message = f"An error occurred: {str(e)}"
        logger.exception(error_message)
        return {
            "statusCode": 500,
            "body": json.dumps({"error": error_message, "steps": steps_messages}),
        }
