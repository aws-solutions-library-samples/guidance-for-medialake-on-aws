# datasets_post_request_mapping.py


def translate_event_to_request(event: dict) -> dict:
    """
    Build variables for Coactive **/api/v1/datasets** (create dataset).

    Creates a dataset with a unique name based on timestamp.
    Authentication is handled by the custom code system (coactive_auth.py).
    """
    from datetime import datetime

    # Generate unique dataset name with timestamp (using underscores for Coactive compatibility)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dataset_name = f"MediaLake_Dataset_{timestamp}"

    print(f"Dataset creation request mapping - generated dataset name: {dataset_name}")
    print("Authentication handled by custom code")

    return {
        "dataset_name": dataset_name,
        "dataset_description": "MediaLake managed dataset for multimodal asset ingestion and semantic search",
        "encoder": "multimodal-tx-large3",
    }
