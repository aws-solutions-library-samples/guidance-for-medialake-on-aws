# assets_post_request_mapping.py
import boto3


def _generate_presigned_url(bucket: str, key: str) -> str:
    """Generate presigned URL for asset access"""
    try:
        s3_client = boto3.client("s3")
        presigned_url = s3_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=3600 * 24,  # 24 hours
        )
        return presigned_url
    except Exception:
        return None


def _extract_asset_info(asset: dict) -> dict:
    """Extract asset information from MediaLake asset structure"""
    try:
        digital_source_asset = asset.get("DigitalSourceAsset", {})
        main_rep = digital_source_asset.get("MainRepresentation", {})
        storage_info = main_rep.get("StorageInfo", {}).get("PrimaryLocation", {})

        asset_type = digital_source_asset.get("Type", "").lower()
        bucket = storage_info.get("Bucket")
        key = storage_info.get("ObjectKey", {}).get("FullPath")

        if not bucket or not key or asset_type not in ["video", "audio", "image"]:
            return None

        return {
            "bucket": bucket,
            "key": key,
            "asset_type": asset_type,
            "asset_id": asset.get("InventoryID", ""),
            "format": main_rep.get("Format", ""),
            "file_size": storage_info.get("FileSize", 0),
        }
    except Exception:
        return None


def translate_event_to_request(event: dict) -> dict:
    """
    Build variables for Coactive **/api/v1/ingestion/assets** (ingest assets).

    Processes MediaLake assets and prepares them for Coactive ingestion.
    Authentication is handled by the custom code system.
    """

    # Extract dataset_id from the previous step's output
    dataset_id = None

    # Check if dataset_id is in the payload data from previous step
    if "payload" in event and "data" in event["payload"]:
        dataset_id = event["payload"]["data"].get("dataset_id")

    # Fallback: check direct event properties
    if not dataset_id:
        dataset_id = event.get("dataset_id")

    if not dataset_id:
        raise RuntimeError(
            "No dataset_id found in event. Dataset validation step may have failed."
        )

    payload = event.get("payload", {})
    assets = payload.get("assets", [])

    if not assets:
        raise ValueError("No assets provided for ingestion")

    coactive_assets = []

    for asset in assets:
        asset_info = _extract_asset_info(asset)
        if not asset_info:
            continue

        # Generate presigned URL
        presigned_url = _generate_presigned_url(asset_info["bucket"], asset_info["key"])
        if not presigned_url:
            continue

        # Prepare metadata
        metadata = {
            "medialake_uuid": asset_info["asset_id"],
            "media_type": asset_info["asset_type"],
            "file_format": asset_info["format"],
            "file_size": asset_info["file_size"],
        }

        # Add consolidated metadata if available
        consolidated_metadata = asset.get("Metadata", {}).get("Consolidated", {})
        if consolidated_metadata:
            field_mappings = {
                "duration": "duration_ms",
                "width": "width",
                "height": "height",
                "title": "title",
                "description": "description",
            }

            for source_field, target_field in field_mappings.items():
                if source_field in consolidated_metadata:
                    metadata[target_field] = consolidated_metadata[source_field]

        coactive_assets.append(
            {
                "source_path": presigned_url,
                "metadata": metadata,
                "asset_type": asset_info["asset_type"],
            }
        )

    if not coactive_assets:
        raise ValueError("No valid assets found for Coactive ingestion")

    return {"dataset_id": dataset_id, "assets": coactive_assets}
