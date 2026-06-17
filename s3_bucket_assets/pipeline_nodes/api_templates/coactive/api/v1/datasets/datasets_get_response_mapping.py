# dataset_id_get_response_mapping.py
import os
from typing import Any, Dict, Optional

import boto3


def _get_configured_dataset_id() -> Optional[str]:
    """
    Read a user-configured Coactive datasetId from the MediaLake system
    settings DynamoDB table. Returns None if not set or on any error.

    System settings location:
        Table: $SYSTEM_SETTINGS_TABLE_NAME
        Key:   PK=SYSTEM_SETTINGS, SK=SEARCH_PROVIDER
        Attr:  datasetId

    Only honored when the configured provider type is 'coactive'.
    Any failure (missing env var, missing item, DynamoDB error) falls
    through to return None so the pipeline continues with its default
    lookup/create behavior.
    """
    table_name = os.environ.get("SYSTEM_SETTINGS_TABLE_NAME")
    if not table_name:
        print("[dataset_id_resolver] SYSTEM_SETTINGS_TABLE_NAME not set")
        return None

    try:
        dynamodb = boto3.resource("dynamodb")
        response = dynamodb.Table(table_name).get_item(
            Key={"PK": "SYSTEM_SETTINGS", "SK": "SEARCH_PROVIDER"}
        )
        item = response.get("Item")
        if not item:
            print("[dataset_id_resolver] No search provider config in system settings")
            return None

        provider_type = item.get("type", "")
        if provider_type != "coactive":
            print(
                f"[dataset_id_resolver] Provider is '{provider_type}', "
                "not coactive — ignoring configured datasetId"
            )
            return None

        configured = item.get("datasetId")
        if configured:
            print(f"[dataset_id_resolver] Using configured datasetId: {configured}")
            return configured

        print("[dataset_id_resolver] No datasetId configured in system settings")
        return None
    except Exception as e:
        print(f"[dataset_id_resolver] Error reading system settings: {e}")
        return None


def translate_event_to_request(
    response_body_and_event: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Process Coactive dataset listing response and determine which dataset to use.

    Priority order:
    1. datasetId explicitly configured in system settings (user override)
    2. Existing MediaLake_Dataset_{ENVIRONMENT} found in the response
    3. Fall through to the dataset creation path (dataset_exists=false)

    Args:
        response_body_and_event: Dictionary containing 'response_body' and 'event'

    Returns:
        Dictionary with processed response data indicating if a dataset is available

    Raises:
        RuntimeError: If the API call failed or returned an error status
    """
    response_body = response_body_and_event.get("response_body", {})
    event = response_body_and_event.get("event", {})

    # Pass through the original assets from the event (used in both branches below)
    assets = event.get("payload", {}).get("assets", [])

    # Priority 1: Check for a user-configured datasetId override in system settings
    configured_dataset_id = _get_configured_dataset_id()
    if configured_dataset_id:
        print(
            f"Using configured datasetId from system settings: "
            f"{configured_dataset_id} — skipping dataset lookup/creation"
        )
        return {
            "dataset_exists": "true",
            "dataset_info": {"dataset_id": configured_dataset_id},
            "dataset_id": configured_dataset_id,
            "dataset_name": "",  # Not known — user supplied the ID directly
            "dataset_status": "",
            "response_data": {"dataset_id": configured_dataset_id},
            "assets": assets,
        }

    # Debug logging
    print("=== DATASET VALIDATION DEBUG ===")
    print(f"Response body type: {type(response_body)}")
    print(
        f"Response body keys: {list(response_body.keys()) if isinstance(response_body, dict) else 'Not a dict'}"
    )
    print(f"Response body content (first 500 chars): {str(response_body)[:500]}...")

    # The response_body is the direct API response data, not wrapped in statusCode/body
    # This is different from other API handlers - the lambda handler passes the raw response
    response_data = response_body

    print("Using response_body directly as response_data")

    # Extract datasets list from response - Coactive API uses 'data' field, not 'datasets'
    datasets = response_data.get("data", [])
    if not isinstance(datasets, list):
        datasets = []

    print(f"Response data type: {type(response_data)}")
    print(
        f"Response data keys: {list(response_data.keys()) if isinstance(response_data, dict) else 'Not a dict'}"
    )
    print(f"Datasets type: {type(datasets)}")
    print(
        f"Datasets length: {len(datasets) if isinstance(datasets, list) else 'Not a list'}"
    )
    print(
        f"First few datasets: {datasets[:3] if isinstance(datasets, list) and len(datasets) > 0 else 'No datasets'}"
    )

    # Look for exact match of "MediaLake_Dataset_{ENVIRONMENT}"
    environment = os.environ.get("ENVIRONMENT", "dev")
    target_dataset_name = f"MediaLake_Dataset_{environment}"
    medialake_dataset = None
    dataset_exists = False

    print(f"Looking for dataset with name: '{target_dataset_name}'")

    for i, dataset in enumerate(datasets):
        dataset_name = dataset.get("name") if isinstance(dataset, dict) else None
        print(f"Dataset {i}: name='{dataset_name}', type={type(dataset)}")

        if isinstance(dataset, dict) and dataset.get("name") == target_dataset_name:
            print(f"✓ Found matching dataset: {dataset}")
            medialake_dataset = dataset
            dataset_exists = True
            break

    print(f"Final result: dataset_exists={dataset_exists}")

    # Return processed response with dataset validation results
    if dataset_exists:
        dataset_id = medialake_dataset.get("datasetId", "")

        # Enhance dataset_info to include dataset_id for easy access by next step
        enhanced_dataset_info = dict(medialake_dataset)
        enhanced_dataset_info["dataset_id"] = dataset_id

        # Also put dataset_id in response_data for the asset ingestion step to find
        enhanced_response_data = dict(response_data)
        enhanced_response_data["dataset_id"] = dataset_id

        result = {
            "dataset_exists": "true",
            "dataset_info": enhanced_dataset_info,
            "dataset_id": dataset_id,
            "dataset_name": medialake_dataset.get("name", ""),
            "dataset_status": medialake_dataset.get("status", ""),
            "response_data": enhanced_response_data,
            "assets": assets,
        }
        print(f"Returning SUCCESS result with dataset_id: {dataset_id}")
        print(f"Dataset info keys: {list(enhanced_dataset_info.keys())}")
        print(f"Response data keys: {list(enhanced_response_data.keys())}")
        print("=== END DATASET VALIDATION DEBUG ===")
        return result
    else:
        result = {
            "dataset_exists": "false",
            "dataset_info": {},
            "dataset_id": "",
            "dataset_name": target_dataset_name,
            "dataset_status": "",
            "response_data": response_data,
            "assets": assets,
        }
        print(f"Returning FAILURE result: {result}")
        print("=== END DATASET VALIDATION DEBUG ===")
        return result
