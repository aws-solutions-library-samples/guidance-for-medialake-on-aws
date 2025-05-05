def translate_event_to_request(event: dict) -> dict:
    """
    Build the parameters that will be substituted into
    `check_status_get_url.jinja`.

    The MediaConvert Job-ID is now provided by the pipeline in
    `event["metadata"]["externalJobId"]`.

    Returns
    -------
    {
        "job_id":  "<job-id>",
        "region":  "<aws-region>"   # defaults to us-east-1
    }
    """
    try:
        job_id = event["metadata"]["externalJobId"]
    except KeyError as exc:
        raise ValueError("metadata.externalJobId missing from event") from exc

    # Prefer the region captured in metadata (if your workflow sets it),
    # otherwise fall back to a fixed default.
    region = event.get("metadata", {}).get("awsRegion", "us-east-1")

    return {"job_id": job_id, "region": region}
