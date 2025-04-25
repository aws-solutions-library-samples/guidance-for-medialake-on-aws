def translate_event_to_request(event):
    """
    Extract input parameters for creating a video thumbnail MediaConvert job.
    
    Expected structure:
    {
        "input": {
            "InventoryID": "...",
            "DigitalSourceAsset": {
                "ID": "...",
                "MainRepresentation": {
                    "StorageInfo": {
                        "PrimaryLocation": {
                            "Bucket": "...",
                            "ObjectKey": {
                                "FullPath": "..."
                            }
                        }
                    },
                    "Duration": {
                        "Frames": 1000
                    }
                }
            }
        },
        "output_bucket": "...",
        "thumbnail_width": 300,
        "thumbnail_height": 400
    }
    """
    try:
        # Extract input data
        input_data = event.get("input", {}).get("DigitalSourceAsset", {})
        inventory_id = event.get("input", {}).get("InventoryID", "")
        
        # Clean asset ID
        master_asset_id = input_data.get("ID", "")
        asset_id = clean_asset_id(master_asset_id)
        
        # Extract storage information
        main_representation = input_data.get("MainRepresentation", {})
        storage_info = main_representation.get("StorageInfo", {})
        primary_location = storage_info.get("PrimaryLocation", {})
        
        input_bucket = primary_location.get("Bucket", "")
        input_key = primary_location.get("ObjectKey", {}).get("FullPath", "")
        
        # Extract output bucket and thumbnail dimensions
        output_bucket = event.get("output_bucket", "")
        thumbnail_width = event.get("thumbnail_width", 300)
        thumbnail_height = event.get("thumbnail_height", 400)
        
        # Extract duration frames if available
        duration_frames = main_representation.get("Duration", {}).get("Frames")
        
        # Generate output key
        output_key = f"{input_bucket}/{input_key.rsplit('.', 1)[0]}_thumbnail"
        
        # Get MediaConvert role ARN and queue from environment variables
        # These would typically be passed in the event or retrieved from environment variables
        mediaconvert_role_arn = event.get("mediaconvert_role_arn", "${MEDIACONVERT_ROLE_ARN}")
        mediaconvert_queue = event.get("mediaconvert_queue", "${MEDIACONVERT_QUEUE}")
        
        return {
            "input_bucket": input_bucket,
            "input_key": input_key,
            "output_bucket": output_bucket,
            "output_key": output_key,
            "mediaconvert_role_arn": mediaconvert_role_arn,
            "mediaconvert_queue": mediaconvert_queue,
            "thumbnail_width": thumbnail_width,
            "thumbnail_height": thumbnail_height,
            "duration_frames": duration_frames,
            "inventory_id": inventory_id,
            "asset_id": asset_id
        }
    except Exception as e:
        raise ValueError(f"Error extracting parameters from event: {str(e)}")


def clean_asset_id(input_string):
    """
    Clean the asset ID to a standard format.
    
    Args:
        input_string: The input asset ID string
        
    Returns:
        Cleaned asset ID in the format "asset:uuid:{uuid}"
    """
    parts = input_string.split(":")
    uuid = parts[-1]
    if uuid == "master":
        uuid = parts[-2]
    return f"asset:uuid:{uuid}"