# datasets_post_response_mapping.py
from typing import Any, Dict


def translate_event_to_request(
    response_body_and_event: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Process Coactive dataset creation response and handle errors.
    This function is called by the Lambda handler for response mapping.

    Args:
        response_body_and_event: Dictionary containing 'response_body' and 'event'

    Returns:
        Dictionary with processed response data

    Raises:
        RuntimeError: If the API call failed or returned an error status
    """
    response_body = response_body_and_event.get("response_body", {})
    response_body_and_event.get("event", {})

    # The response_body IS the direct Coactive API response
    # No need to check statusCode or unwrap body - that's handled by the Lambda middleware

    # Validate we have a response
    if not response_body:
        raise RuntimeError("No response received from Coactive API")

    # Check if this is an error response (would contain 'error' or 'detail' fields)
    if "error" in response_body or "detail" in response_body:
        error_msg = response_body.get("error") or response_body.get(
            "detail", "Unknown error"
        )
        raise RuntimeError(f"Coactive API error: {error_msg}")

    # Extract dataset information directly from response_body
    dataset_id = response_body.get("datasetId")
    dataset_name = response_body.get("name")
    dataset_status = response_body.get("status")

    if not dataset_id:
        raise RuntimeError("No dataset ID returned from Coactive API")

    # Return processed response with dataset information
    return {
        "dataset_id": dataset_id,
        "dataset_name": dataset_name,
        "dataset_status": dataset_status,
        "coactive_response": response_body,
    }
