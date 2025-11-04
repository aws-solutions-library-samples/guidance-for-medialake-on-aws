# dataset_id_get_response_mapping.py
import os
from typing import Any, Dict


def translate_event_to_request(
    response_body_and_event: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Process Coactive dataset listing response and check if MediaLake_Dataset_{ENVIRONMENT} exists.

    Args:
        response_body_and_event: Dictionary containing 'response_body' and 'event'

    Returns:
        Dictionary with processed response data indicating if MediaLake_Dataset_{ENVIRONMENT} exists

    Raises:
        RuntimeError: If the API call failed or returned an error status
    """
    response_body = response_body_and_event.get("response_body", {})
    event = response_body_and_event.get("event", {})

    # Debug logging
    print(f"=== DATASET VALIDATION DEBUG ===")
    print(f"Response body type: {type(response_body)}")
    print(
        f"Response body keys: {list(response_body.keys()) if isinstance(response_body, dict) else 'Not a dict'}"
    )
    print(f"Response body content (first 500 chars): {str(response_body)[:500]}...")

    # The response_body is the direct API response data, not wrapped in statusCode/body
    # This is different from other API handlers - the lambda handler passes the raw response
    response_data = response_body

    print(f"Using response_body directly as response_data")

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

    # Pass through the original assets from the event
    assets = event.get("payload", {}).get("assets", [])

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
        print(f"=== END DATASET VALIDATION DEBUG ===")
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
        print(f"=== END DATASET VALIDATION DEBUG ===")
        return result
