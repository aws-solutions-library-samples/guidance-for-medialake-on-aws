def translate_event_to_request(event):
    """
    Extract input parameters for creating an audio proxy MediaConvert job.
    
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
                    }
                }
            }
        },
        "output_bucket": "..."
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
        
        # Extract output bucket
        output_bucket = event.get("output_bucket", "")
        
        # Generate output key
        output_key = f"{input_bucket}/{input_key.rsplit('.', 1)[0]}_audio"
        
        # Get MediaConvert role ARN and queue from environment variables
        # These would typically be passed in the event or retrieved from environment variables
        mediaconvert_role_arn = event.get("mediaconvert_role_arn", "${MEDIACONVERT_ROLE_ARN}")
        mediaconvert_queue_arn = event.get("mediaconvert_queue_arn", "${MEDIACONVERT_QUEUE_ARN}")
        
        return {
            "input_bucket": input_bucket,
            "input_key": input_key,
            "output_bucket": output_bucket,
            "output_key": output_key,
            "mediaconvert_role_arn": mediaconvert_role_arn,
            "mediaconvert_queue_arn": mediaconvert_queue_arn,
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