import os

import boto3


def translate_event_to_request(response_body_and_event):
    """
    Process Coactive status check API response and store external ID when completed
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
                asset.get("DigitalSourceAsset", {}).get("Type", "").lower()

                # Get dataset_id from event metadata or response
                dataset_id = event.get("metadata", {}).get("dataset_id") or data.get(
                    "dataset_id"
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

    return {
        # External job tracking for pipeline middleware
        "externalJobId": coactive_asset_id,
        "externalJobStatus": ext_status,
        "externalJobResult": ext_result,
        # Template variables
        "job_id": coactive_asset_id,
        "status": status,
        "coactive_status": status,
        "coactive_response": response_body,
    }
