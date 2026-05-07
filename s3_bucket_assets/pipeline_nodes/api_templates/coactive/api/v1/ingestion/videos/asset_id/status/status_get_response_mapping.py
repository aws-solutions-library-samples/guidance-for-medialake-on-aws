import os

import boto3


def translate_event_to_request(response_body_and_event):
    """
    Process Coactive video status check API response and store external ID when completed
    """
    response_body = response_body_and_event.get("response_body", {})
    event = response_body_and_event.get("event", {})

    # Extract status information from Coactive response
    data = response_body.get("data", {})
    status = data.get("status", "unknown")
    coactive_asset_id = data.get("asset_id")

    # Preserve previous externalJobId if missing from response
    if not coactive_asset_id:
        coactive_asset_id = event.get("metadata", {}).get("externalJobId")

    # Extract additional fields from the response
    dataset_id = data.get("dataset_id")
    error_code = data.get("error_code")
    error_reason = data.get("error_reason")
    source_path = data.get("source_path")
    asset_type = data.get("asset_type")

    # Extract latest event information
    latest_event = data.get("latest_event", {})
    latest_event_type = (
        latest_event.get("event_type") if isinstance(latest_event, dict) else None
    )
    latest_event_entity = (
        latest_event.get("event_entity") if isinstance(latest_event, dict) else None
    )
    latest_event_timestamp = (
        latest_event.get("timestamp_dt") if isinstance(latest_event, dict) else None
    )

    # Unified status mapping
    status_mapping = {
        "completed": ("Completed", "Success"),
        "failed": ("Failed", "Failed"),
        "error": ("Failed", "Failed"),
        "processing": ("Started", "InProgress"),
        "processing_started": ("Started", "InProgress"),
        "in_progress": ("Started", "InProgress"),
        "pending": ("Started", "Pending"),
    }

    ext_status, ext_result = status_mapping.get(status, ("Started", "InProgress"))

    # Store Coactive ID in DynamoDB when ingestion completes successfully
    if status == "completed" and coactive_asset_id:
        try:
            # Get asset information from event
            assets = event.get("payload", {}).get("assets", [])
            if assets:
                asset = assets[0]
                inventory_id = asset.get("InventoryID")
                asset_type_from_asset = (
                    asset.get("DigitalSourceAsset", {}).get("Type", "").lower()
                )

                # Use asset_type from response if available, otherwise from asset
                asset_type if asset_type else asset_type_from_asset

                # Get dataset_id from event metadata or response
                final_dataset_id = (
                    event.get("metadata", {}).get("dataset_id") or dataset_id
                )

                if inventory_id:
                    # Initialize DynamoDB
                    dynamodb = boto3.resource("dynamodb")
                    table = dynamodb.Table(os.environ.get("MEDIALAKE_ASSET_TABLE"))

                    # Get current record
                    response = table.get_item(Key={"InventoryID": inventory_id})
                    item = response.get("Item", {})

                    # Create simple external ID entry
                    external_id_entry = {"coactive": coactive_asset_id}

                    # Initialize or update ExternalIDs array
                    metadata = item.get("Metadata", {})
                    external_ids = metadata.get("ExternalIDs", [])

                    # Check if coactive entry already exists
                    existing_index = next(
                        (i for i, eid in enumerate(external_ids) if "coactive" in eid),
                        None,
                    )

                    if existing_index is not None:
                        external_ids[existing_index] = external_id_entry
                    else:
                        external_ids.append(external_id_entry)

                    # Update DynamoDB
                    table.update_item(
                        Key={"InventoryID": inventory_id},
                        UpdateExpression="SET Metadata.ExternalIDs = :external_ids",
                        ExpressionAttributeValues={":external_ids": external_ids},
                    )

                    print(
                        f"Stored Coactive ID {coactive_asset_id} for asset {inventory_id}"
                    )

        except Exception as e:
            # Log error but don't fail the pipeline
            print(f"Warning: Failed to store Coactive external ID: {str(e)}")

    # Determine completion timestamp from latest event or use current time for completed status
    completed_at = ""
    if status == "completed" and latest_event_timestamp:
        completed_at = latest_event_timestamp

    # Create message based on latest event or error information
    message = ""
    if error_reason:
        message = error_reason
    elif latest_event_type:
        message = f"Latest event: {latest_event_type}"

    return {
        # External job tracking for pipeline middleware
        "externalJobId": coactive_asset_id,
        "externalJobStatus": ext_status,
        "externalJobResult": ext_result,  # Simple string, not complex object
        # Template variables
        "job_id": coactive_asset_id,
        "status": status,
        "coactive_status": status,
        "coactive_response": response_body,  # Keep full response for debugging
        # Additional Coactive-specific fields
        "dataset_id": dataset_id,
        "error_code": error_code,
        "error_reason": error_reason,
        "source_path": source_path,
        "asset_type": asset_type,
        "latest_event_type": latest_event_type,
        "latest_event_entity": latest_event_entity,
        "latest_event_timestamp": latest_event_timestamp,
        "completed_at": completed_at,
        "message": message,
    }
