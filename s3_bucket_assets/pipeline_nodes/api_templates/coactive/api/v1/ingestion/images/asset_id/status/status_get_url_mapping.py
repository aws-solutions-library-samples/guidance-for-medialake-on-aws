def translate_event_to_request(event):
    """
    Map MediaLake event to URL parameters for Coactive image status check
    """
    # Extract asset_id from external job tracking or previous step output
    asset_id = None
    subdomain = "api"  # Default subdomain for Coactive API

    if isinstance(event, dict):
        metadata = event.get("metadata", {})
        payload = event.get("payload", {})

        # Try multiple sources for the asset UUID (not job ID):
        # 1. Look for coactive_asset_id in external job result asset_results (primary source for status checks)
        external_job_result = metadata.get("externalJobResult")
        if isinstance(external_job_result, dict):
            asset_results = external_job_result.get("asset_results", [])
            if isinstance(asset_results, list) and len(asset_results) > 0:
                first_asset = asset_results[0]
                if isinstance(first_asset, dict):
                    asset_id = first_asset.get("coactive_asset_id")

        # 2. Also check in payload data externalJobResult
        if not asset_id:
            data = payload.get("data", {})
            external_job_result = data.get("externalJobResult")
            if isinstance(external_job_result, dict):
                asset_results = external_job_result.get("asset_results", [])
                if isinstance(asset_results, list) and len(asset_results) > 0:
                    first_asset = asset_results[0]
                    if isinstance(first_asset, dict):
                        asset_id = first_asset.get("coactive_asset_id")

        # 3. Look for coactive_response.details.assets[0].asset_id
        if not asset_id:
            external_job_result = metadata.get("externalJobResult")
            if isinstance(external_job_result, dict):
                coactive_response = external_job_result.get("coactive_response", {})
                if isinstance(coactive_response, dict):
                    details = coactive_response.get("details", {})
                    if isinstance(details, dict):
                        assets = details.get("assets", [])
                        if isinstance(assets, list) and len(assets) > 0:
                            first_asset = assets[0]
                            if isinstance(first_asset, dict):
                                asset_id = first_asset.get("asset_id")

        # 4. Fallback to external job ID (job ID, not asset ID - less preferred)
        if not asset_id:
            external_job_id = metadata.get("externalJobId")
            if external_job_id and external_job_id.strip():
                asset_id = external_job_id

        # 5. Payload data sources (fallback)
        if not asset_id:
            data = payload.get("data", {})
            asset_id = data.get("asset_id") or data.get("coactive_asset_id")

        # 6. Direct payload fields (fallback)
        if not asset_id:
            asset_id = payload.get("asset_id") or payload.get("coactive_asset_id")

    # Ensure we have a valid asset_id - fail fast if missing
    if not asset_id or not asset_id.strip():
        raise RuntimeError(
            "Cannot determine Coactive asset_id for status check. "
            "Expected to find coactive_asset_id in metadata.externalJobResult.asset_results[0].coactive_asset_id "
            "from the previous ingestion POST step. "
            "This usually indicates that the ingestion step did not complete successfully or "
            "the externalJobResult data was not properly passed through the pipeline."
        )

    return {"asset_id": asset_id, "subdomain": subdomain}
