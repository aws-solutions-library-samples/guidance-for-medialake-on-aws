# datasets_post_request_mapping.py
import os


def translate_event_to_request(event: dict) -> dict:
    """
    Build variables for Coactive **/api/v1/datasets** (create dataset).

    Creates a dataset with environment-specific name.
    Authentication is handled by the custom code system (coactive_auth.py).
    """

    # Generate environment-specific dataset name
    environment = os.environ.get("ENVIRONMENT", "dev")
    dataset_name = f"MediaLake_Dataset_{environment}"

    print(f"Dataset creation request mapping - generated dataset name: {dataset_name}")
    print("Authentication handled by custom code")

    return {
        "dataset_name": dataset_name,
        "dataset_description": f"MediaLake managed dataset for multimodal asset ingestion and semantic search ({environment} environment)",
        "encoder": "multimodal-tx-large3",
    }
