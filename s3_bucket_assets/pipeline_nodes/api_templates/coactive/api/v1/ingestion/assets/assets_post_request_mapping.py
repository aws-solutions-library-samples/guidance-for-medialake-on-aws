# assets_post_request_mapping.py
import boto3


def _generate_presigned_url(bucket: str, key: str) -> str:
    """Generate presigned URL for asset access (fallback only)"""
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

    print(f"=== DATASET ID EXTRACTION DEBUG ===")
    print(
        f"Event keys: {list(event.keys()) if isinstance(event, dict) else 'Not a dict'}"
    )

    # Check payload structure first
    if "payload" in event:
        payload = event["payload"]
        print(
            f"Payload keys: {list(payload.keys()) if isinstance(payload, dict) else 'Not a dict'}"
        )

        # Check if dataset_id is in the payload data from previous step
        if "data" in payload:
            payload_data = payload["data"]
            print(
                f"Payload data keys: {list(payload_data.keys()) if isinstance(payload_data, dict) else 'Not a dict'}"
            )
            dataset_id = payload_data.get("dataset_id")
            print(f"Dataset ID from payload.data: {dataset_id}")

            # Also check in dataset_info if available
            if not dataset_id and "dataset_info" in payload_data:
                dataset_info = payload_data.get("dataset_info", {})
                dataset_id = dataset_info.get("dataset_id") or dataset_info.get(
                    "datasetId"
                )
                print(f"Dataset ID from payload.data.dataset_info: {dataset_id}")

            # Also check in response_data if available
            if not dataset_id and "response_data" in payload_data:
                response_data = payload_data.get("response_data", {})
                dataset_id = response_data.get("dataset_id")
                print(f"Dataset ID from payload.data.response_data: {dataset_id}")

        # Check payload_history from middleware (preserves data from previous steps)
        if not dataset_id and "payload_history" in payload:
            payload_history = payload["payload_history"]
            print(
                f"Payload history keys: {list(payload_history.keys()) if isinstance(payload_history, dict) else 'Not a dict'}"
            )
            dataset_id = payload_history.get("dataset_id")
            print(f"Dataset ID from payload_history: {dataset_id}")

            # Also check in dataset_info within payload_history
            if not dataset_id and "dataset_info" in payload_history:
                dataset_info = payload_history.get("dataset_info", {})
                dataset_id = dataset_info.get("dataset_id") or dataset_info.get(
                    "datasetId"
                )
                print(f"Dataset ID from payload_history.dataset_info: {dataset_id}")

            # Also check in response_data within payload_history
            if not dataset_id and "response_data" in payload_history:
                response_data = payload_history.get("response_data", {})
                dataset_id = response_data.get("dataset_id")
                print(f"Dataset ID from payload_history.response_data: {dataset_id}")

    # Fallback: check direct event properties
    if not dataset_id:
        dataset_id = event.get("dataset_id")
        print(f"Dataset ID from direct event: {dataset_id}")

    print(f"Final dataset_id: {dataset_id}")
    print(f"=== END DATASET ID EXTRACTION DEBUG ===")

    if not dataset_id:
        raise RuntimeError(
            "No dataset_id found in event. Dataset validation step may have failed."
        )

    payload = event.get("payload", {})
    assets = payload.get("assets", [])

    if not assets:
        raise ValueError("No assets provided for ingestion")

    # Extract presigned URL from previous step (Generate Presigned URL step)
    presigned_url_from_step = None
    if "data" in payload:
        presigned_url_from_step = payload["data"].get("presignedUrl")
        print(f"Presigned URL from previous step: {presigned_url_from_step}")

    coactive_assets = []

    for asset in assets:
        asset_info = _extract_asset_info(asset)
        if not asset_info:
            continue

        # Use presigned URL from previous step, fallback to generating new one
        presigned_url = presigned_url_from_step
        if not presigned_url:
            print("No presigned URL from previous step, generating new one")
            presigned_url = _generate_presigned_url(
                asset_info["bucket"], asset_info["key"]
            )
            if not presigned_url:
                continue
        else:
            print("Using presigned URL from previous step")

        # Prepare metadata
        metadata = {
            "medialake_uuid": asset_info["asset_id"],
            "media_type": asset_info["asset_type"],
            "file_format": asset_info["format"],
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
