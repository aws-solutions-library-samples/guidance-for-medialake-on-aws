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
dynamodb_client = boto3.client("dynamodb")
asset_table = dynamodb_client.Table(table_name)


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

    for record in event["Records"]:
        if record["eventName"] != "INSERT":
            continue

        new_image = record["dynamodb"]["NewImage"]
        movie_id = new_image["movie_id"]["N"]
        s3_source_bucket = new_image["S3_bucket"]["S"]
        s3_source_key = new_image["S3_object"]["S"]
        inventory_id = new_image.get("InventoryID", {}).get("S", "")
        clean_inventory_id = clean_asset_id(inventory_id)

        steps_messages[movie_id] = {}

        # Download file from S3 to /tmp/ for mediainfo
        local_path = f"/tmp/{os.path.basename(s3_source_key)}"
        try:
            s3_client.download_file(s3_source_bucket, s3_source_key, local_path)
            steps_messages[movie_id]["S3_download"] = "Success"
        except Exception as e:
            steps_messages[movie_id]["S3_download"] = f"Failure: {e}"
            error = True
            continue

        try:
            ff_data = run_ffprobe(local_path)
            steps_messages[movie_id]["FFProbe_analysis"] = "Success"
        except Exception as e:
            steps_messages[movie_id]["FFProbe_analysis"] = f"Failure: {e}"
            error = True
            continue

        try:
            mi_data = run_mediainfo(local_path)
            steps_messages[movie_id]["Mediainfo_analysis"] = "Success"
        except Exception as e:
            steps_messages[movie_id]["Mediainfo_analysis"] = f"Failure: {e}"
            error = True
            continue

        # Merge metadata
        merged_output = merge_metadata(ff_data, mi_data)

        # Create new representation for proxy
        output_bucket = os.environ.get("OUTPUT_BUCKET")
        output_key = f"{s3_source_bucket}/{s3_source_key.rsplit('.', 1)[0]}_proxy.mp4"
        asset_id = f"{clean_asset_id(movie_id)}:proxy"

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
            steps_messages[movie_id]["DDB_update"] = "Success"
        except Exception as e:
            logger.exception(
                "Error updating DynamoDB",
                extra={
                    "inventory_id": clean_inventory_id,
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
            )
            steps_messages[movie_id]["DDB_update"] = f"Failure: {e}"
            error = True

    if error:
        statusCode = 500
    else:
        statusCode = 200

    return {"statusCode": statusCode, "body": json.dumps(steps_messages)}


# @logger.inject_lambda_context
# @tracer.capture_lambda_handler
# def lambda_handler(event, context: LambdaContext):
#     # Get DynamoDB table name from environment variable
#     table_name = os.environ["MEDIALAKE_ASSET_TABLE"]
#     dynamodb = boto3.resource("dynamodb")
#     table = dynamodb.Table(table_name)

#     # Get the s3_uri and mode from query parameters
#     input = event.get("input", {})
#     input_data = input.get("DigitalSourceAsset", {})
#     inventory_id = input.get("InventoryID")
#     clean_inventory_id = clean_asset_id(inventory_id)
#     main_representation = input_data.get("MainRepresentation", {})
#     master_asset_id = input_data.get("ID")
#     asset_id = clean_asset_id(master_asset_id)
#     storage_info = main_representation.get("StorageInfo", {})
#     PrimaryLocation = storage_info.get("PrimaryLocation", {})
#     object_info = PrimaryLocation.get("ObjectKey", {})
#     bucket = PrimaryLocation.get("Bucket")
#     key = object_info.get("FullPath")

#     # Get the output bucket from event
#     output_bucket = event.get("output_bucket")

#     mode = event.get("mode", "proxy")  # default to proxy mode

#     if not key:
#         return {"statusCode": 400, "body": "Missing key parameter"}
#     if not bucket:
#         return {"statusCode": 400, "body": "Missing bucket parameter"}

#     if not output_bucket:
#         return {"statusCode": 400, "body": "Missing output_bucket parameter"}

#     # Initialize S3 client
#     s3 = boto3.client("s3")

#     try:
#         # Fetch the image from S3
#         s3_response = s3.get_object(Bucket=bucket, Key=key)
#         image_data = s3_response["Body"].read()
#         img = Image.open(io.BytesIO(image_data))

#         if mode == "thumbnail":
#             # Get thumbnail parameters
#             # params = event.get("thumbnail")
#             width = event.get("width")
#             height = event.get("height")
#             crop = event.get("crop", False)

#             # Check if both width and height are None
#             if width is None and height is None:
#                 return {
#                     "statusCode": 400,
#                     "body": "Both width and height cannot be None for thumbnail creation",
#                 }

#             # If one dimension is None, calculate it based on the aspect ratio
#             if width is None:
#                 width = int(height * (img.width / img.height))
#             elif height is None:
#                 height = int(width * (img.height / img.width))

#             # Ensure width and height are integers
#             width = int(width)
#             height = int(height)

#             # Process image
#             processed_img = create_thumbnail(img, width, height, crop)

#             # Generate output key
#             output_key = (
#                 f"{bucket}/{key.rsplit('.', 1)[0]}_thumbnails_{width}x{height}.webp"
#             )

#         elif mode == "proxy":
#             # Process image
#             processed_img = create_proxy(img)
#             width, height = img.size
#             # Generate output key
#             output_key = f"{bucket}/{key.rsplit('.', 1)[0]}_proxy.webp"

#         else:
#             return {"statusCode": 400, "body": "Invalid mode parameter"}

#         # Save the processed image
#         output_buffer = io.BytesIO()

#         # Save as WebP with appropriate quality
#         if mode == "thumbnail":
#             processed_img.save(output_buffer, format="WEBP", quality=85)
#             asset_id = f"{asset_id}:thumbnail"
#             output_data = output_buffer.getvalue()
#             new_representation = {
#                 "ID": asset_id,
#                 "Type": "Image",
#                 "Format": "WEBP",
#                 "Purpose": mode,
#                 "StorageInfo": {
#                     "PrimaryLocation": {
#                         "StorageType": "s3",
#                         "Provider": "aws",
#                         "Bucket": output_bucket,
#                         "ObjectKey": {
#                             "FullPath": output_key,
#                         },
#                         "Status": "active",
#                         "FileInfo": {
#                             "Size": len(output_data),
#                         },
#                     }
#                 },
#                 "ImageSpec": {
#                     "Resolution": {"Width": width, "Height": height},
#                 },
#             }
#         else:  # proxy mode
#             processed_img.save(output_buffer, format="WEBP", quality=90)
#             output_data = output_buffer.getvalue()
#             asset_id = f"{asset_id}:proxy"
#             new_representation = {
#                 "ID": asset_id,
#                 "Type": "Image",
#                 "Format": "WEBP",
#                 "Purpose": mode,
#                 "StorageInfo": {
#                     "PrimaryLocation": {
#                         "StorageType": "s3",
#                         "Provider": "aws",
#                         "Bucket": output_bucket,
#                         "ObjectKey": {
#                             "FullPath": output_key,
#                         },
#                         "Status": "active",
#                         "FileInfo": {
#                             "Size": len(output_data),
#                         },
#                     }
#                 },
#             }

#         # Upload to output bucket
#         s3.put_object(
#             Bucket=output_bucket,
#             Key=output_key,
#             Body=output_data,
#             ContentType="image/webp",
#         )

#         try:
#             # Add logging before the update
#             logger.info(
#                 "Attempting DynamoDB update",
#                 extra={
#                     "inventory_id": clean_inventory_id,
#                     "new_representation": new_representation,
#                 },
#             )

#             # Update DynamoDB
#             response = table.update_item(
#                 Key={"InventoryID": clean_inventory_id},
#                 UpdateExpression="SET #dr = list_append(if_not_exists(#dr, :empty_list), :new_rep)",
#                 ExpressionAttributeNames={"#dr": "DerivedRepresentations"},
#                 ExpressionAttributeValues={
#                     ":new_rep": [new_representation],
#                     ":empty_list": [],
#                 },
#                 ReturnValues="UPDATED_NEW",
#             )

#             # Add more detailed success logging
#             logger.info(
#                 "DynamoDB update response",
#                 extra={"response": response, "inventory_id": clean_inventory_id},
#             )

#         except Exception as e:
#             # Enhance error logging
#             logger.exception(
#                 "Error updating DynamoDB",
#                 extra={
#                     "inventory_id": clean_inventory_id,
#                     "error": str(e),
#                     "error_type": type(e).__name__,
#                 },
#             )
#             raise  # Re-raise to ensure we catch all errors

#         # Return the processed image information
#         return {
#             "statusCode": 200,
#             "body": {
#                 "ID": asset_id,
#                 "type": "image",
#                 "format": "WEBP",
#                 "Purpose": mode,
#                 "StorageInfo": {
#                     "PrimaryLocation": {
#                         "StorageType": "s3",
#                         "Bucket": output_bucket,
#                         "path": output_key,
#                         "status": "active",
#                         "ObjectKey": {
#                             "FullPath": output_key,
#                         },
#                     }
#                 },
#                 "location": {
#                     "bucket": output_bucket,
#                     "key": output_key,
#                 },
#                 "mode": mode,
#             },
#         }

#     except Exception as e:
#         return {"statusCode": 500, "body": f"Error processing image: {str(e)}"}
