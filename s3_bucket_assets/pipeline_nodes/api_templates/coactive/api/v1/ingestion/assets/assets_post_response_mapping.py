# assets_post_response_mapping.py
import json
from typing import Any, Dict


def translate_response_to_output(
    response_body_and_event: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Process Coactive asset ingestion response and handle errors.

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

    # Extract key information from Coactive response
    job_id = response_data.get("id")
    dataset_id = response_data.get("dataset_id")
    status = response_data.get("status")
    total_assets = response_data.get("total_assets", 0)
    processed_assets = response_data.get("processed_assets", 0)
    errored_assets = response_data.get("errored_assets", 0)
    created_dt = response_data.get("created_dt")

    # Extract asset details
    details = response_data.get("details", {})
    assets_info = details.get("assets", [])

    # Process individual asset results
    asset_results = []
    for asset_detail in assets_info:
        asset = asset_detail.get("asset", {})
        asset_results.append(
            {
                "coactive_asset_id": asset.get("asset_id"),
                "source_path": asset.get("source_path"),
                "medialake_uuid": asset.get("metadata", {}).get("medialake_uuid"),
                "error": asset.get("error"),
            }
        )

    # Pass through the original assets from the event
    assets = event.get("payload", {}).get("assets", [])

    # Determine overall status
    if errored_assets == 0:
        if status == "pending":
            message = f"Successfully submitted {total_assets} assets to Coactive for ingestion"
        else:
            message = f"Ingestion job created with status: {status}"
    else:
        message = f"Partial success: {total_assets - errored_assets} submitted, {errored_assets} failed"

    return {
        "message": message,
        "job_id": job_id,
        "dataset_id": dataset_id,
        "ingestion_status": status,
        "total_assets": total_assets,
        "processed_assets": processed_assets,
        "errored_assets": errored_assets,
        "created_at": created_dt,
        "asset_results": asset_results,
        "coactive_response": response_data,
        "assets": assets,
    }
