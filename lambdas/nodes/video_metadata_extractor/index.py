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
    data = json.loads(media_info.to_json())
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


@logger.inject_lambda_context
@tracer.capture_lambda_handler
def lambda_handler(event, context):
    error = False
    steps_messages = {}
    print(event)

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
        error = True
        return {"statusCode": 500, "body": json.dumps(steps_messages)}

    ff_data = None
    mi_data = None

    try:
        ff_data = run_ffprobe(local_path)
        steps_messages[clean_inventory_id]["FFProbe_analysis"] = "Success"
        logger.info("FFProbe analysis completed successfully")
    except Exception as e:
        error_msg = f"FFProbe analysis failed: {str(e)}"
        logger.error(error_msg, extra={"local_path": local_path})
        steps_messages[clean_inventory_id]["FFProbe_analysis"] = f"Failure: {e}"
        error = True

    try:
        mi_data = run_mediainfo(local_path)
        steps_messages[clean_inventory_id]["Mediainfo_analysis"] = "Success"
        logger.info("MediaInfo analysis completed successfully")
    except Exception as e:
        error_msg = f"MediaInfo analysis failed: {str(e)}"
        logger.error(error_msg, extra={"local_path": local_path})
        steps_messages[clean_inventory_id]["Mediainfo_analysis"] = f"Failure: {e}"
        error = True

    if error or ff_data is None or mi_data is None:
        logger.error(
            "One or more analysis steps failed",
            extra={"ff_data": bool(ff_data), "mi_data": bool(mi_data)},
        )
        return {"statusCode": 500, "body": json.dumps(steps_messages)}

    # Merge metadata
    merged_output = merge_metadata(ff_data, mi_data)

    # Create new representation for proxy
    output_bucket = os.environ.get("OUTPUT_BUCKET")
    output_key = f"{s3_source_bucket}/{s3_source_key.rsplit('.', 1)[0]}_proxy.mp4"
    asset_id = f"{clean_inventory_id}:proxy"

    new_representation = {
        "ID": asset_id,
        "Type": "Video",
        "Format": "MP4",
        "Purpose": "proxy",
        "StorageInfo": {
            "PrimaryLocation": {
                "StorageType": "s3",
                "Provider": "aws",
                "Bucket": output_bucket,
                "ObjectKey": {
                    "FullPath": output_key,
                },
                "Status": "active",
                "FileInfo": {
                    "Size": os.path.getsize(
                        local_path
                    ),  # Approximate size, as proxy might be smaller
                },
            }
        },
        "VideoSpec": {
            "Resolution": {
                "Width": merged_output["video"][0].get("width"),
                "Height": merged_output["video"][0].get("height"),
            },
            "Codec": merged_output["video"][0].get("codec_name"),
            "BitRate": merged_output["video"][0].get("bit_rate"),
            "FrameRate": merged_output["video"][0].get("r_frame_rate"),
        },
    }

    # Update DynamoDB
    # Update DynamoDB
    try:
        logger.info(
            "Attempting DynamoDB update",
            extra={
                "inventory_id": clean_inventory_id,
                "new_representation": new_representation,
            },
        )

        response = asset_table.update_item(
            Key={"InventoryID": clean_inventory_id},
            UpdateExpression="SET #dr = list_append(if_not_exists(#dr, :empty_list), :new_rep), ffprobe_mediainfo_merged = :merged",
            ExpressionAttributeNames={"#dr": "DerivedRepresentations"},
            ExpressionAttributeValues={
                ":new_rep": [new_representation],
                ":empty_list": [],
                ":merged": json.dumps(merged_output),
            },
            ReturnValues="UPDATED_NEW",
        )

        logger.info(
            "DynamoDB update response",
            extra={"response": response, "inventory_id": clean_inventory_id},
        )
        steps_messages[clean_inventory_id]["DDB_update"] = "Success"
    except Exception as e:
        logger.exception(
            "Error updating DynamoDB",
            extra={
                "inventory_id": clean_inventory_id,
                "error": str(e),
                "error_type": type(e).__name__,
            },
        )
        steps_messages[clean_inventory_id]["DDB_update"] = f"Failure: {e}"
        error = True

    if error:
        statusCode = 500
    else:
        statusCode = 200

    return {"statusCode": statusCode, "body": json.dumps(steps_messages)}
