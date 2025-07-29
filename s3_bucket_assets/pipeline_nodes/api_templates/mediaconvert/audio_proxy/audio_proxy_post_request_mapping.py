def translate_event_to_request(event):
    """
    Extract input parameters for creating an audio proxy MediaConvert job.
    """
    try:
        # Input event shimming
        inp = event["input"]
        inventory_id = inp.get("InventoryID", "")
        dsa = inp.get("DigitalSourceAsset", {})
        master_id = dsa.get("ID", "")

        # Clean asset ID
        asset_id = clean_asset_id(master_id)

        # Pull out bucket/key
        primary_loc = (
            dsa.get("MainRepresentation", {})
            .get("StorageInfo", {})
            .get("PrimaryLocation", {})
        )
        input_bucket = primary_loc.get("Bucket", "")
        input_key = primary_loc.get("ObjectKey", {}).get("FullPath", "")

        # Where to write it
        output_bucket = event.get("output_bucket", "")

        # mirror source bucket + path (without extension)
        # strip extension, leave off suffix and extension
        base = input_key.rsplit(".", 1)[0]
        output_key = f"{input_bucket}/{base}"  # e.g. "my-source-bucket/path/to/file"

        # Role + queue ARNs
        mediaconvert_role_arn = event.get(
            "mediaconvert_role_arn", "${MEDIACONVERT_ROLE_ARN}"
        )
        mediaconvert_queue_arn = event.get(
            "mediaconvert_queue_arn", "${MEDIACONVERT_QUEUE_ARN}"
        )

        return {
            "input_bucket": input_bucket,
            "input_key": input_key,
            "output_bucket": output_bucket,
            "output_key": output_key,
            "mediaconvert_role_arn": mediaconvert_role_arn,
            "mediaconvert_queue_arn": mediaconvert_queue_arn,
            "inventory_id": inventory_id,
            "asset_id": asset_id,
        }

    except Exception as e:
        raise ValueError(f"Error extracting parameters from event: {e}")


def clean_asset_id(input_string: str) -> str:
    parts = input_string.split(":")
    uuid = parts[-1] if parts[-1] != "master" else parts[-2]
    return f"asset:uuid:{uuid}"
