def translate_event_to_request(event):
    """
    Extract input parameters for creating a transcription job.
    
    Expected structure:
    {
        "detail": {
            "outputs": {
                "input": {
                    "DigitalSourceAsset": {
                        "MainRepresentation": {
                            "StorageInfo": {
                                "PrimaryLocation": {
                                    "Bucket": "...",
                                    "ObjectKey": {
                                        "FullPath": "...",
                                        "Path": "..."
                                    }
                                }
                            }
                        }
                    },
                    "InventoryID": "..."
                }
            }
        }
    }
    """
    try:
        # Retrieve storage from the input section
        input_data = event.get("detail", {}).get("outputs", {}).get("input", {})
        storage_data = input_data.get("DigitalSourceAsset", {}).get("MainRepresentation", {}).get("StorageInfo", {}).get("PrimaryLocation", {})
        
        # Extract S3 bucket, key, and path
        s3_bucket = storage_data.get("Bucket", "")
        s3_key = storage_data.get("ObjectKey", {}).get("FullPath", "")
        s3_path = storage_data.get("ObjectKey", {}).get("Path", "")
        
        # Extract inventory ID
        inventory_id = input_data.get("InventoryID", "")
        
        # Extract the base name from the source key (without extension)
        import os
        base_name = os.path.splitext(os.path.basename(s3_key))[0]
        
        # Get the media format from the file extension
        media_format = os.path.splitext(s3_key)[1][1:]
        
        # Generate a job name with timestamp
        import time
        job_name = f"{base_name}-{int(time.time())}"
        
        # Get output bucket from environment variable
        output_bucket = "${MEDIA_ASSETS_BUCKET_NAME}"
        
        # Get transcribe role ARN from environment variable
        transcribe_role_arn = "${TRANSCRIBE_ROLE_ARN}"
        
        return {
            "s3_bucket": s3_bucket,
            "s3_key": s3_key,
            "s3_path": s3_path,
            "inventory_id": inventory_id,
            "job_name": job_name,
            "media_format": media_format,
            "output_bucket": output_bucket,
            "transcribe_role_arn": transcribe_role_arn
        }
    except Exception as e:
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