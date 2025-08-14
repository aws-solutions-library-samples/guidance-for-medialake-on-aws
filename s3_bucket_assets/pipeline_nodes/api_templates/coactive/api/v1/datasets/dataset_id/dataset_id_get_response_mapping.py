# dataset_id_get_response_mapping.py
import json
from typing import Any, Dict


def translate_response_to_output(
    response_body_and_event: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Process Coactive dataset validation response and handle errors.

    Args:
        response_body_and_event: Dictionary containing 'response_body' and 'event'

    Returns:
        Dictionary with processed response data

    Raises:
        RuntimeError: If the API call failed or returned an error status
    """
    response_body = response_body_and_event.get("response_body", {})
    event = response_body_and_event.get("event", {})

    # Check if the API call failed
    status_code = response_body.get("statusCode", 200)

    if status_code == 404:
        # Dataset doesn't exist - this might be expected, don't raise error
        # Pass through the original assets from the event
        assets = event.get("payload", {}).get("assets", [])

        return {
            "dataset_exists": False,
            "dataset_info": {},
            "dataset_id": event.get("payload", {})
            .get("data", {})
            .get("dataset_id", ""),
            "assets": assets,
        }
    elif status_code != 200:
        # Other API errors - raise error to stop Step Functions execution
        body = response_body.get("body", "{}")

        # Try to parse the error details
        try:
            if isinstance(body, str):
                error_details = json.loads(body)
            else:
                error_details = body
        except json.JSONDecodeError:
            error_details = {"error": "Unknown error", "details": str(body)}

        error_message = f"Coactive API call failed with status {status_code}"
        if "error" in error_details:
            error_message += f": {error_details['error']}"
        if "details" in error_details:
            error_message += f" - {error_details['details']}"
        elif "detail" in error_details:
            error_message += f" - {error_details['detail']}"

        raise RuntimeError(error_message)

    # Parse successful response
    try:
        if isinstance(response_body.get("body"), str):
            response_data = json.loads(response_body["body"])
        else:
            response_data = response_body.get("body", {})
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Failed to parse Coactive API response: {str(e)}")

    # Extract dataset information
    dataset_id = response_data.get("datasetId")
    dataset_name = response_data.get("name")
    dataset_status = response_data.get("status")

    # Pass through the original assets from the event
    assets = event.get("payload", {}).get("assets", [])

    # Return processed response with dataset validation results
    return {
        "dataset_exists": True,
        "dataset_info": response_data,
        "dataset_id": dataset_id,
        "dataset_name": dataset_name,
        "dataset_status": dataset_status,
        "assets": assets,
    }
