def translate_event_to_request(response_body_and_event):
    """
    Transform the MediaConvert job status response into the desired output format.
    
    Maps MediaConvert job status to the required format:
    - "COMPLETE" → "Completed"
    - "IN_PROGRESS" → "inProgress"
    - "SUBMITTED" → "Started"
    
    Sets externalJobResult based on status:
    - "COMPLETE" → "Success"
    - Any other status → "Failed"
    
    Args:
        response_body_and_event: Dict containing the MediaConvert response and the original event
        
    Returns:
        Dict with the transformed response
    """
    response_body = response_body_and_event["response_body"]
    event = response_body_and_event["event"]
    
    # Extract job details from the response
    job = response_body.get("Job", {})
    job_id = job.get("Id", "")
    status = job.get("Status", "")
    
    # Map MediaConvert status to required format
    status_mapping = {
        "COMPLETE": "Completed",
        "IN_PROGRESS": "inProgress",
        "SUBMITTED": "Started"
    }
    
    mapped_status = status_mapping.get(status, "Started")
    
    # Determine job result
    job_result = "Success" if status == "COMPLETE" else "Failed"
    
    # Extract asset information from the event
    input_data = event.get("input", {})
    inventory_id = input_data.get("InventoryID", "")
    
    # Extract output details if job is complete
    result = {
        "externalJobId": job_id,
        "externalJobStatus": mapped_status,
        "externalJobResult": job_result,
        "status": status
    }
    
    if status == "COMPLETE":
        # Get the output bucket and base path
        output_groups = job.get("Settings", {}).get("OutputGroups", [])
        if output_groups:
            output_group_settings = output_groups[0].get("OutputGroupSettings", {}).get("FileGroupSettings", {})
            destination = output_group_settings.get("Destination", "")
            
            if destination.startswith("s3://"):
                parts = destination.split("s3://")[1].split("/", 1)
                if len(parts) == 2:
                    output_bucket = parts[0]
                    base_path = parts[1]
                    
                    # Determine if this is video or audio based on the event
                    is_video = "VideoProxyandThumbnailResult" in event.get("previous_task_output", {})
                    
                    # Add proxy information
                    if is_video:
                        proxy_path = f"{base_path}.mp4"
                        thumbnail_path = f"{base_path}_thumbnail.0000000.jpg"
                        proxy_format = "MP4"
                        has_thumbnail = True
                    else:
                        proxy_path = f"{base_path}.mp3"
                        thumbnail_path = None
                        proxy_format = "MP3"
                        has_thumbnail = False
                    
                    # Add proxy information to result
                    result["proxy"] = {
                        "StorageInfo": {
                            "PrimaryLocation": {
                                "StorageType": "s3",
                                "Bucket": output_bucket,
                                "path": proxy_path,
                                "status": "active",
                                "ObjectKey": {"FullPath": proxy_path}
                            }
                        }
                    }
                    
                    # Add thumbnail information if applicable
                    if has_thumbnail:
                        result["thumbnail"] = {
                            "StorageInfo": {
                                "PrimaryLocation": {
                                    "StorageType": "s3",
                                    "Bucket": output_bucket,
                                    "path": thumbnail_path,
                                    "status": "active",
                                    "ObjectKey": {"FullPath": thumbnail_path}
                                }
                            }
                        }
    
    return result