def translate_event_to_request(event):
    """
    Extract input parameters for creating a transcription job.

    Expected structure:
    {
        "payload": {
            "assets": [
                {
                    "InventoryID": "...",
                    "DerivedRepresentations": [
                        {
                            "Purpose": "proxy",
                            "StorageInfo": {
                                "PrimaryLocation": {
                                    "Bucket": "...",
                                    "ObjectKey": {
                                        "FullPath": "..."
                                    }
                                }
                            }
                        }
                    ]
                }
            ]
        }
    }
    """
    try:
        # Get the assets array from the payload
        assets = event.get("payload", {}).get("assets", [])

        if not assets:
            raise ValueError("No assets found in the event payload")

        # Get the first asset
        asset = assets[0]

        # Extract inventory ID
        inventory_id = asset.get("InventoryID", "")

        # Find the proxy representation
        proxy_rep = None
        for rep in asset.get("DerivedRepresentations", []):
            if rep.get("Purpose") == "proxy":
                proxy_rep = rep
                break

        if not proxy_rep:
            raise ValueError("No proxy representation found in the asset")

        # Extract storage information from the proxy representation
        storage_data = proxy_rep.get("StorageInfo", {}).get("PrimaryLocation", {})

        # Extract S3 bucket, key, and path
        s3_bucket = storage_data.get("Bucket", "")
        s3_key = storage_data.get("ObjectKey", {}).get("FullPath", "")

        # Extract path from the key (everything before the last slash)
        s3_path = ""
        if "/" in s3_key:
            s3_path = s3_key.rsplit("/", 1)[0]

        # Extract the base name from the source key (without extension)
        import os
        import re

        base_name = os.path.splitext(os.path.basename(s3_key))[0]

        # Sanitize base_name to comply with AWS Transcribe OutputKey constraints
        # Replace spaces and other problematic characters with underscores
        base_name = re.sub(r"[^a-zA-Z0-9\-_.\!\*\'\(\)\/\&\$@=;:+,?]", "_", base_name)
        # Remove multiple consecutive underscores
        base_name = re.sub(r"_+", "_", base_name)
        # Remove leading/trailing underscores
        base_name = base_name.strip("_")

        # Get the media format from the file extension or from the Format field
        media_format = ""
        if "." in s3_key:
            media_format = os.path.splitext(s3_key)[1][1:].lower()
        else:
            # Try to get format from the representation
            media_format = proxy_rep.get("Format", "").lower()

        # Validate media format
        valid_formats = ["mp3", "mp4", "wav", "flac", "ogg", "amr", "webm"]
        if media_format not in valid_formats:
            # Default to mp3 if format is not recognized
            media_format = "mp3"

        # Generate a job name with timestamp
        import time

        job_name = f"{base_name}-{int(time.time())}"

        # Get output bucket from environment variable
        import os

        output_bucket = os.environ.get("MEDIA_ASSETS_BUCKET_NAME", "")

        # Get transcribe role ARN from environment variable
        transcribe_role_arn = os.environ.get("TRANSCRIBE_SERVICE_ROLE_ROLE_ARN", "")

        # Log the extracted values for debugging
        print(
            f"Final values - s3_bucket: {s3_bucket}, s3_key: {s3_key}, s3_path: {s3_path}"
        )
        print(
            f"media_format: {media_format}, output_bucket: {output_bucket}, transcribe_role_arn: {transcribe_role_arn}"
        )

        return {
            "s3_bucket": s3_bucket,
            "s3_key": s3_key,
            "s3_path": s3_path,
            "base_name": base_name,
            "inventory_id": inventory_id,
            "job_name": job_name,
            "media_format": media_format,
            "output_bucket": output_bucket,
            "transcribe_role_arn": transcribe_role_arn,
        }
    except Exception as e:
        import traceback

        error_details = traceback.format_exc()
        print(f"Error processing event: {str(e)}")
        print(f"Error details: {error_details}")
        print(f"Event structure: {event}")
        raise ValueError(f"Error extracting parameters from event: {str(e)}")


def clean_asset_id(input_string):
    """
    Ensures the asset ID has the correct format without duplicates.
    Extracts just the UUID part and adds the proper prefix.
    """
    parts = input_string.split(":")
    uuid_part = parts[-1]
    if uuid_part == "master":
        uuid_part = parts[-2]
    return f"asset:uuid:{uuid_part}"
