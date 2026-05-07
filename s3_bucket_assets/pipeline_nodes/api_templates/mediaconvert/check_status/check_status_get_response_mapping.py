# check_status_get_response_mapping.py
"""
Translate MediaConvert GetJob → structure consumed by
check_status_get_response.jinja.

Fields produced
───────────────
externalJobId       – MediaConvert job ID
externalJobStatus   – Completed / inProgress / Started / Failed
externalJobResult   – Success / InProgress / Pending / Failed   ← **always set**
status              – Raw MediaConvert status
proxy, thumbnail    – Added only when status == COMPLETE
"""

from __future__ import annotations

from typing import Any, Dict


def translate_event_to_request(
    response_body_and_event: Dict[str, Any],
) -> Dict[str, Any]:
    response_body = response_body_and_event["response_body"]
    event = response_body_and_event["event"]

    job = response_body.get("Job", {})
    job_id = job.get("Id", "")
    status = job.get("Status", "")  # COMPLETE / IN_PROGRESS / ERROR …

    # ── unified mapping (status → (externalJobStatus, externalJobResult)) ──
    status_map = {
        "COMPLETE": ("Completed", "Success"),
        "IN_PROGRESS": ("inProgress", "InProgress"),
        "PROGRESSING": ("inProgress", "InProgress"),
        "SUBMITTED": ("Started", "Pending"),
        "QUEUED": ("Started", "Pending"),
        "CANCELED": ("Failed", "Failed"),
        "ERROR": ("Failed", "Failed"),
    }
    ext_status, ext_result = status_map.get(status, ("Started", "Failed"))

    result: Dict[str, Any] = {
        "externalJobId": job_id,
        "externalJobStatus": ext_status,
        "externalJobResult": ext_result,
        "status": status,
    }

    # ── add proxy / thumbnail only when COMPLETE ────────────────────────────
    if status == "COMPLETE":
        out_grp = (
            job.get("Settings", {})
            .get("OutputGroups", [{}])[0]
            .get("OutputGroupSettings", {})
            .get("FileGroupSettings", {})
        )
        destination = out_grp.get("Destination", "")
        bucket, key_prefix = ("", "")
        if destination.startswith("s3://"):
            bucket, key_prefix = destination.replace("s3://", "", 1).split("/", 1)

        # media-type from original asset (fall back to Audio)
        try:
            media_type = event["payload"]["assets"][0]["DigitalSourceAsset"]["Type"]
        except Exception:
            media_type = "Audio"

        if media_type == "Video":
            proxy_path, thumb_path = (
                f"{key_prefix}.mp4",
                f"{key_prefix}_thumbnail.0000000.jpg",
            )
            result["thumbnail"] = {
                "StorageInfo": {
                    "PrimaryLocation": {
                        "StorageType": "s3",
                        "Bucket": bucket,
                        "path": thumb_path,
                        "status": "active",
                        "ObjectKey": {"FullPath": thumb_path},
                    }
                }
            }
        else:  # Audio
            proxy_path, thumb_path = f"{key_prefix}.mp3", None

        result["proxy"] = {
            "StorageInfo": {
                "PrimaryLocation": {
                    "StorageType": "s3",
                    "Bucket": bucket,
                    "path": proxy_path,
                    "status": "active",
                    "ObjectKey": {"FullPath": proxy_path},
                }
            }
        }

    return result
