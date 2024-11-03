import json
import os
import uuid
from datetime import datetime
import boto3
from io import BytesIO
from PIL import Image, ExifTags, ImageStat
from PIL.ExifTags import TAGS, GPSTAGS
import logging
import math
from typing import Dict, Any

# Initialize AWS clients
s3 = boto3.client("s3")
eventbridge = boto3.client("events")
dynamodb = boto3.resource("dynamodb")

# Environment variables
INGEST_EVENT_BUS = os.environ["INGEST_EVENT_BUS"]
MEDIALAKE_ASSET_TABLE = os.environ["MEDIALAKE_ASSET_TABLE"]


def handler(event, context):
    for record in event["Records"]:
        body = json.loads(record["body"])

        if "Event" in body and body["Event"] == "s3:TestEvent":
            # Handle test event
            print("Received S3 test event")
            continue

        if "Records" not in body:
            print("Invalid event format: missing Records")
            continue

        s3_events = body["Records"]

        for s3_event in s3_events:
            # Extract S3 event information
            try:
                bucket = s3_event["s3"]["bucket"]["name"]
                key = s3_event["s3"]["object"]["key"]
                event_time = s3_event["eventTime"]
                event_type = s3_event["eventName"]
            except KeyError as e:
                print(f"Invalid event format: missing key {str(e)}")
                continue

            if not bucket or not key:
                print("Invalid event format: missing bucket or key information")
                continue

            asset = process_asset(bucket, key, event_time, event_type)
            if asset:
                try:
                    s3.put_object_tagging(
                        Bucket=bucket,
                        Key=key,
                        Tagging={
                            "TagSet": [
                                {"Key": "medialakeUID", "Value": asset["id"]},
                            ]
                        },
                    )
                    print(f"S3 object tagged with MediaLake UID: {asset['id']}")
                except Exception as e:
                    print(f"Error tagging S3 object: {str(e)}")

                try:
                    table = dynamodb.Table(MEDIALAKE_ASSET_TABLE)
                    table.put_item(Item=asset)
                    print(f"Asset information inserted into DynamoDB: {asset['id']}")
                except Exception as e:
                    print(f"Error inserting asset information into DynamoDB: {str(e)}")

                # Create EventBridge event
                event_type = (
                    "AssetDeleted"
                    if event_type.startswith("ObjectRemoved")
                    else "AssetIngested"
                )
                event_detail = {"eventType": event_type, "assets": [asset]}
                print(asset)
                try:
                    response = eventbridge.put_events(
                        Entries=[
                            {
                                "Source": "MediaLakeIngest",
                                "DetailType": event_type,
                                "Detail": json.dumps(event_detail),
                                "EventBusName": INGEST_EVENT_BUS,
                            }
                        ]
                    )
                    print(f"EventBridge event sent: {response}")
                except Exception as e:
                    print(f"Error sending EventBridge event: {str(e)}")


def process_asset(bucket, key, event_time, event_type):
    # Generate a unique ID for the asset
    asset_id = str(uuid.uuid4())

    # Get object metadata
    try:
        response = s3.head_object(Bucket=bucket, Key=key)
        metadata = response.get("Metadata", {})
        content_type = response.get("ContentType", "application/octet-stream")
        size = response.get("ContentLength", 0)
    except Exception as e:
        print(f"Error getting object metadata: {str(e)}")
        metadata = {}
        content_type = "application/octet-stream"
        size = 0

    # Determine asset type based on file extension
    file_extension = os.path.splitext(key)[1].lower()
    asset_type = get_asset_type(file_extension)

    # Check for hash in metadata
    hash_value = metadata.get("checksum-sha256", None)

    technical_metadata = {}
    if asset_type == "Image":
        try:
            # Download image to memory
            response = s3.get_object(Bucket=bucket, Key=key)
            image_data = response["Body"].read()

            with Image.open(BytesIO(image_data)) as img:
                # Get comprehensive technical metadata
                technical_metadata = get_image_technical_metadata(img)

                # Get EXIF data
                exif_data = get_exif_data(img)
                if exif_data:
                    technical_metadata["exif"] = exif_data

                # Add file format details
                technical_metadata["format_details"] = {
                    "format_description": (
                        img.format_description
                        if hasattr(img, "format_description")
                        else None
                    ),
                    "mime_type": Image.MIME.get(img.format),
                    "extension": img.format.lower() if img.format else None,
                }

                # Calculate file efficiency
                if (
                    technical_metadata["basic"]["width"]
                    and technical_metadata["basic"]["height"]
                ):
                    pixels = (
                        technical_metadata["basic"]["width"]
                        * technical_metadata["basic"]["height"]
                    )
                    bytes_per_pixel = size / pixels if pixels > 0 else 0
                    technical_metadata["efficiency"] = {
                        "total_pixels": pixels,
                        "bytes_per_pixel": round(bytes_per_pixel, 3),
                        "bits_per_pixel": technical_metadata["basic"]["bits_per_pixel"],
                    }

        except Exception as e:
            logging.error(f"Error extracting image metadata: {str(e)}")

    # Create the standardized asset object
    asset = {
        "id": asset_id,
        "sourceLocation": {"path": key, "bucket": bucket, "type": "S3"},
        "type": asset_type,
        "name": os.path.basename(key),
        "dateCreated": datetime.utcnow().isoformat() + "Z",
        "dateModified": event_time,
        "size": size,
        "format": {
            "container": get_container_format(file_extension),
            "codec": metadata.get("codec", "Unknown"),
        },
        "metadata": {
            "contentType": content_type,
            "customMetadata": metadata,
            "technical": technical_metadata if technical_metadata else None,
        },
        "status": "Deleted" if event_type.startswith("ObjectRemoved") else "Ingested",
        "tags": parse_tags(metadata.get("tags", "")),
    }

    # Include hash if it exists
    if hash_value:
        asset["hash"] = {"algorithm": "SHA-256", "value": hash_value}

    return asset


def get_asset_type(file_extension):
    video_extensions = [".mp4", ".mov", ".avi", ".mkv"]
    audio_extensions = [".mp3", ".wav", ".aac", ".flac"]
    image_extensions = [
        ".jpg",
        ".jpeg",
        ".png",
        ".tiff",
        ".webp",
        ".heic",
        ".heif",
        ".svg",
        ".gif",
        ".bmp",
    ]

    if file_extension in video_extensions:
        return "Video"
    elif file_extension in audio_extensions:
        return "Audio"
    elif file_extension in image_extensions:
        return "Image"
    else:
        return "Other"


def get_container_format(file_extension):
    format_map = {
        ".mp4": "MPEG-4",
        ".mov": "QuickTime",
        ".avi": "AVI",
        ".mkv": "Matroska",
        ".mp3": "MPEG Audio Layer III",
        ".wav": "Waveform Audio",
        ".aac": "Advanced Audio Coding",
        ".flac": "Free Lossless Audio Codec",
        ".jpg": "JPEG",
        ".jpeg": "JPEG",
        ".png": "PNG",
        ".tiff": "TIFF",
        ".webp": "WebP",
        ".heic": "High-Efficiency Image Format",
        ".heif": "High-Efficiency Image Format",
        ".gif": "GIF",
        ".bmp": "Bitmap",
        ".svg": "Scalable Vector Graphics",
    }
    return format_map.get(file_extension.lower(), "Unknown")


def parse_tags(tags_string):
    return [tag.strip() for tag in tags_string.split(",") if tag.strip()]


def get_image_technical_metadata(img: Image.Image) -> Dict[str, Any]:
    """Extract comprehensive technical metadata from an image."""
    metadata = {
        "basic": {
            "width": img.width,
            "height": img.height,
            "aspect_ratio": round(img.width / img.height, 3),
            "mode": img.mode,
            "format": img.format,
            "is_animated": getattr(img, "is_animated", False),
            "n_frames": getattr(img, "n_frames", 1),
            "bits_per_pixel": len(img.getbands()) * 8,
            "color_channels": len(img.getbands()),
            "color_space": img.mode,
            "compression": getattr(img, "info", {}).get("compression", None),
            "resolution": {
                "x": img.info.get("dpi", (0, 0))[0],
                "y": img.info.get("dpi", (0, 0))[1],
            },
        },
        "color_stats": {},
        "histogram": {},
    }

    # Calculate color statistics
    try:
        stat = ImageStat.Stat(img)
        metadata["color_stats"] = {
            "mean": stat.mean,
            "median": stat.median,
            "stddev": stat.stddev,
            "rms": stat.rms,
        }

        # Calculate perceived brightness
        if img.mode == "RGB":
            r, g, b = stat.mean[:3]
            perceived_brightness = math.sqrt(0.299 * r**2 + 0.587 * g**2 + 0.114 * b**2)
            metadata["color_stats"]["perceived_brightness"] = round(
                perceived_brightness, 2
            )

        # Get histogram data
        hist = img.histogram()
        metadata["histogram"] = {
            "values": hist,
            "total_pixels": img.width * img.height,
        }
    except Exception as e:
        logging.warning(f"Error calculating color statistics: {str(e)}")

    return metadata


def get_exif_data(img: Image.Image) -> Dict[str, Any]:
    """Extract and process all EXIF data from image."""
    exif_data = {}

    try:
        if hasattr(img, "_getexif") and img._getexif():
            exif = img._getexif()

            # Standard EXIF data
            for tag_id, value in exif.items():
                tag = TAGS.get(tag_id, tag_id)

                # Skip binary data
                if isinstance(value, bytes):
                    try:
                        value = value.decode(errors="ignore")
                    except:
                        continue

                # Process GPS Info separately
                if tag == "GPSInfo":
                    gps_data = {}
                    for gps_tag_id, gps_value in value.items():
                        gps_tag = GPSTAGS.get(gps_tag_id, gps_tag_id)
                        gps_data[gps_tag] = gps_value

                    # Convert GPS coordinates to decimal degrees if available
                    if all(
                        k in gps_data
                        for k in [
                            "GPSLatitude",
                            "GPSLatitudeRef",
                            "GPSLongitude",
                            "GPSLongitudeRef",
                        ]
                    ):
                        try:
                            lat = gps_data["GPSLatitude"]
                            lat_ref = gps_data["GPSLatitudeRef"]
                            lon = gps_data["GPSLongitude"]
                            lon_ref = gps_data["GPSLongitudeRef"]

                            lat_decimal = (
                                float(lat[0])
                                + float(lat[1]) / 60
                                + float(lat[2]) / 3600
                            ) * (-1 if lat_ref == "S" else 1)
                            lon_decimal = (
                                float(lon[0])
                                + float(lon[1]) / 60
                                + float(lon[2]) / 3600
                            ) * (-1 if lon_ref == "W" else 1)

                            gps_data["decimal_coordinates"] = {
                                "latitude": round(lat_decimal, 6),
                                "longitude": round(lon_decimal, 6),
                            }
                        except Exception as e:
                            logging.warning(
                                f"Error converting GPS coordinates: {str(e)}"
                            )

                    exif_data["gps"] = gps_data
                else:
                    exif_data[tag] = str(value)

            # Organize camera settings
            camera_settings = {}
            important_settings = {
                "Make": "camera_make",
                "Model": "camera_model",
                "ExposureTime": "exposure_time",
                "FNumber": "f_number",
                "ISOSpeedRatings": "iso_speed",
                "FocalLength": "focal_length",
                "ExposureProgram": "exposure_program",
                "ExposureMode": "exposure_mode",
                "WhiteBalance": "white_balance",
                "MeteringMode": "metering_mode",
                "Flash": "flash",
                "LensModel": "lens_model",
                "LensMake": "lens_make",
            }

            for exif_tag, setting_name in important_settings.items():
                if exif_tag in exif_data:
                    camera_settings[setting_name] = exif_data[exif_tag]

            if camera_settings:
                exif_data["camera_settings"] = camera_settings

    except Exception as e:
        logging.warning(f"Error processing EXIF data: {str(e)}")

    return exif_data
