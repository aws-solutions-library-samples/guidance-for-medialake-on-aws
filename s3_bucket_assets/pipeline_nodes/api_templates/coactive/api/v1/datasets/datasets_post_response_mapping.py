# datasets_post_response_mapping.py
import json
from typing import Any, Dict


def translate_response_to_output(
    response_body_and_event: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Process Coactive dataset creation response and handle errors.

    Args:
        response_body_and_event: Dictionary containing 'response_body' and 'event'

    Returns:
        Dictionary with processed response data

    Raises:
        RuntimeError: If the API call failed or returned an error status
    """
    response_body = response_body_and_event.get("response_body", {})
    response_body_and_event.get("event", {})

    # Check if the API call failed
    status_code = response_body.get("statusCode", 200)

    if status_code != 200:
        # API call failed - raise error to stop Step Functions execution
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

    if not dataset_id:
        raise RuntimeError("No dataset ID returned from Coactive API")

    # Return processed response with dataset information
    return {
        "dataset_id": dataset_id,
        "dataset_name": dataset_name,
        "dataset_status": dataset_status,
        "coactive_response": response_data,
    }
