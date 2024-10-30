import json
import boto3
import os
import uuid
from datetime import datetime

# Initialize AWS clients
s3 = boto3.client("s3")
eventbridge = boto3.client("events")

# Environment variables
EVENT_BUS_NAME = os.environ["NORMALIZED_EVENT_BUS"]


def handler(event, context):
    print(event)

    for record in event["Records"]:
        body = json.loads(record["body"])
        s3_events = body["Records"]

        for s3_event in s3_events:
            # Extract S3 event information
            bucket = s3_event["s3"]["bucket"]["name"]
            key = s3_event["s3"]["object"]["key"]
            event_time = s3_event["eventTime"]
            event_type = s3_event["eventName"]

            if not bucket or not key:
                print("Invalid event format: missing bucket or key information")
                continue

            asset = process_asset(bucket, key, event_time, event_type)
            if asset:
                # Create EventBridge event
                event_type = "AssetDeleted" if event_type.startswith("ObjectRemoved") else "AssetIngested"
                event_detail = {"eventType": event_type, "assets": [asset]}

                try:
                    response = eventbridge.put_events(
                        Entries=[
                            {
                                "Source": "MnEMSCAutomatedWorkflow",
                                "DetailType": event_type,
                                "Detail": json.dumps(event_detail),
                                "EventBusName": EVENT_BUS_NAME,
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
        },
        "status": "Deleted" if event_type.startswith("ObjectRemoved") else "Ingested",
        "tags": parse_tags(metadata.get("tags", "")),
        "workflow": {
            "currentStage": "Deleted" if event_type.startswith("ObjectRemoved") else "QC",
            "history": [
                {
                    "stage": "Deleted" if event_type.startswith("ObjectRemoved") else "Ingest",
                    "timestamp": event_time,
                }
            ],
        },
    }

    # Include hash if it exists
    if hash_value:
        asset["hash"] = {"algorithm": "SHA-256", "value": hash_value}

    return asset


def get_asset_type(file_extension):
    video_extensions = [".mp4", ".mov", ".avi", ".mkv"]
    audio_extensions = [".mp3", ".wav", ".aac", ".flac"]
    image_extensions = [".jpg", ".jpeg", ".png", ".tiff"]

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
    }
    return format_map.get(file_extension.lower(), "Unknown")


def parse_tags(tags_string):
    return [tag.strip() for tag in tags_string.split(",") if tag.strip()]
