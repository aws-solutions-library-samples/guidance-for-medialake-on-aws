# assets_post_response_mapping.py
import json
import logging
from typing import Any, Dict

# Set up logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def translate_event_to_request(
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

    # The response_body is already the parsed JSON response from Coactive
    response_data = response_body

    # Extract key information from Coactive response
    # The job ID can be at the top level or nested in details
    job_id = response_data.get("id") or response_data.get("details", {}).get("id")

    # Validate that we have a job ID - fail fast if missing
    if not job_id:
        raise RuntimeError(
            f"Coactive API response missing job ID. Response structure: {json.dumps(response_data, indent=2)}"
        )

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
        asset_id = asset_detail.get("asset_id")
        asset = asset_detail.get("asset", {})
        error = asset_detail.get("error")

        asset_results.append(
            {
                "coactive_asset_id": asset_id,
                "source_path": asset.get("source_path"),
                "medialake_uuid": asset.get("metadata", {}).get("medialake_uuid"),
                "error": error,
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

    # For single asset ingestion, use the asset ID as externalJobId for status tracking
    # For batch ingestion, use the job ID
    logger.info("=== EXTERNAL JOB ID SELECTION DEBUG ===")
    logger.info(f"Job ID from response: {job_id}")
    logger.info(f"Number of asset results: {len(asset_results)}")
    logger.info(f"Asset results: {json.dumps(asset_results, indent=2)}")

    external_job_id = job_id
    if len(asset_results) == 1 and asset_results[0].get("coactive_asset_id"):
        asset_id = asset_results[0]["coactive_asset_id"]
        logger.info(f"Single asset detected - using asset ID: {asset_id}")
        external_job_id = asset_id
    else:
        logger.info(f"Multiple assets or no asset ID - using job ID: {job_id}")

    logger.info(f"Final externalJobId: {external_job_id}")
    logger.info("=== END DEBUG ===")

    return {
        # External job tracking for pipeline middleware
        "externalJobId": external_job_id,
        "externalJobStatus": "Started",
        "externalJobResult": {
            "message": message,
            "dataset_id": dataset_id,
            "total_assets": total_assets,
            "processed_assets": processed_assets,
            "errored_assets": errored_assets,
            "created_at": created_dt,
            "asset_results": asset_results,
            "coactive_response": response_data,
        },
        # Template variables for Jinja rendering
        "task_id": job_id,
        "job_id": job_id,
        "ingestion_status": status,
        "processed_assets": processed_assets,  # For template: {{ processed_assets }}
        "assets_processed": processed_assets,  # For template: {{ assets_processed }}
        # Keep all original data for backward compatibility
        "message": message,
        "dataset_id": dataset_id,
        "total_assets": total_assets,
        "processed_assets": processed_assets,
        "errored_assets": errored_assets,
        "created_at": created_dt,
        "asset_results": asset_results,
        "coactive_response": response_data,
        "assets": assets,
    }
