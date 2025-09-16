def translate_event_to_request(event):
    """
    Extract job information for TwelveLabs Bedrock status check.

    Args:
        event: The incoming event containing job information

    Returns:
        Dict with job information for status checking
    """
    payload = event.get("payload", {})

    # Get job information from payload - check nested structure first
    job_info = payload
    if "data" in payload and "payload" in payload["data"]:
        job_info = payload["data"]["payload"]

    invocation_arn = job_info.get("invocation_arn", "")
    s3_bucket = job_info.get("s3_bucket", "")
    output_location = job_info.get("output_location", "")

    if not all([invocation_arn, s3_bucket, output_location]):
        raise ValueError(
            "Missing required job information: invocation_arn, s3_bucket, or output_location"
        )

    return {
        "invocation_arn": invocation_arn,
        "s3_bucket": s3_bucket,
        "output_location": output_location,
    }
