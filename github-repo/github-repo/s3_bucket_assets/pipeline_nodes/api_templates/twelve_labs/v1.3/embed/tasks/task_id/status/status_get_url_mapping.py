def translate_event_to_request(event):
    """
    Build the variables dict for status_get_url.jinja
    using the value already stored in metadata.externalJobId.
    """

    task_id = event.get("metadata", {}).get("externalJobId")
    if not task_id:
        raise KeyError(
            "metadata.externalJobId is missing—cannot build Twelve Labs status URL"
        )

    return {"task_id": task_id}
