"""
Video-proxy + thumbnail trigger Lambda (no DynamoDB cache)

• Accepts modern {"payload": {"assets": […]} events
• Renders a MediaConvert job (proxy MP4 + FRAME_CAPTURE JPEG) from Jinja in S3
• Retries describe_endpoints with exponential back-off
• Cleans up any existing proxy or thumbnail before submitting a new job
"""

import decimal
import importlib.util
import json
import os
import os.path
import random
import time
from typing import Any, Dict, List

import boto3
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext
from botocore.exceptions import ClientError
from jinja2 import Environment, FileSystemLoader
from lambda_middleware import lambda_middleware

# ── Powertools & clients ─────────────────────────────────────────────────────
logger = Logger()
tracer = Tracer()
s3 = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")
asset_table = dynamodb.Table(os.environ["MEDIALAKE_ASSET_TABLE"])


def _raise(msg: str):
    raise RuntimeError(msg)


def _strip_decimals(obj):
    """Recursively convert Decimal → int/float so the Lambda JSON encoder is happy."""
    if isinstance(obj, list):
        return [_strip_decimals(v) for v in obj]
    if isinstance(obj, dict):
        return {k: _strip_decimals(v) for k, v in obj.items()}
    if isinstance(obj, decimal.Decimal):
        return int(obj) if obj % 1 == 0 else float(obj)
    return obj


def get_mediaconvert_endpoint() -> str:
    override = os.getenv("MEDIACONVERT_ENDPOINT_URL")
    if override:
        return override

    mc = boto3.client("mediaconvert")
    for attempt in range(60):
        try:
            return mc.describe_endpoints()["Endpoints"][0]["Url"]
        except ClientError as e:
            if e.response["Error"]["Code"] != "TooManyRequestsException":
                raise
            delay = (2**attempt) + random.random()
            logger.warning("describe_endpoints throttled, retrying in %.2fs", delay)
            time.sleep(delay)
    _raise("Unable to obtain MediaConvert endpoint after retries")


def create_job_with_retry(
    mc_client, job_settings: Dict[str, Any], max_retries: int = 5
) -> Dict[str, Any]:
    """
    Wrap mc.create_job() in exponential-backoff on TooManyRequestsException.
    """
    attempt = 0
    while True:
        try:
            return mc_client.create_job(**job_settings)
        except ClientError as e:
            code = e.response["Error"]["Code"]
            if code == "TooManyRequestsException" and attempt < max_retries:
                attempt += 1
                backoff = (2**attempt) + random.random()
                logger.warning(
                    "create_job throttled (attempt %d/%d), retrying in %.2fs",
                    attempt,
                    max_retries,
                    backoff,
                )
                time.sleep(backoff)
                continue
            logger.error("create_job failed: %s", e)
            raise


def _exec_s3_py(bucket: str, key: str, fn: str, arg: dict) -> dict:
    obj = s3.get_object(Bucket=bucket, Key=f"api_templates/{key}")
    code = obj["Body"].read().decode()
    spec = importlib.util.spec_from_loader("dyn_mod", loader=None)
    mod = importlib.util.module_from_spec(spec)
    exec(code, mod.__dict__)
    return getattr(mod, fn)(arg)


def _dl_s3(bucket: str, key: str) -> str:
    return s3.get_object(Bucket=bucket, Key=key)["Body"].read().decode()


def _tmpl_paths(service: str, resource: str, method: str) -> Dict[str, str]:
    base = f"{resource.split('/')[-1]}_{method.lower()}"
    return {
        "request_template": f"{service}/{resource}/{base}_request.jinja",
        "mapping_file": f"{service}/{resource}/{base}_request_mapping.py",
        "response_template": f"{service}/{resource}/{base}_response.jinja",
        "response_mapping_file": f"{service}/{resource}/{base}_response_mapping.py",
    }


def _render_request(paths: dict, bucket: str, event: dict) -> dict:
    tmpl = _dl_s3(bucket, f"api_templates/{paths['request_template']}")
    mapping = _exec_s3_py(
        bucket, paths["mapping_file"], "translate_event_to_request", event
    )
    env = Environment(loader=FileSystemLoader("/tmp/"))
    env.filters["jsonify"] = json.dumps
    rendered = env.from_string(tmpl).render(variables=mapping)
    try:
        return json.loads(rendered)
    except json.JSONDecodeError:
        logger.error("Broken job-settings JSON ↓\n%s", rendered)
        raise


def _render_response(paths: dict, bucket: str, resp: dict, event: dict) -> dict:
    tmpl = _dl_s3(bucket, f"api_templates/{paths['response_template']}")
    mapping = _exec_s3_py(
        bucket,
        paths["response_mapping_file"],
        "translate_event_to_request",
        {"response_body": resp, "event": event},
    )
    env = Environment(loader=FileSystemLoader("/tmp/"))
    env.filters["jsonify"] = json.dumps
    return json.loads(env.from_string(tmpl).render(variables=mapping))


def _normalize_event(evt: dict) -> dict:
    assets: List[dict] = evt.get("payload", {}).get("assets", [])
    if not assets:
        _raise("Event missing payload.assets list")
    evt["input"] = assets[0]
    return assets[0]


@lambda_middleware(event_bus_name=os.getenv("EVENT_BUSINESS", "default-event-bus"))
@logger.inject_lambda_context
@tracer.capture_lambda_handler
def lambda_handler(event: Dict[str, Any], _: LambdaContext) -> Dict[str, Any]:
    try:
        asset = _normalize_event(event)
        primary = asset["DigitalSourceAsset"]["MainRepresentation"]["StorageInfo"][
            "PrimaryLocation"
        ]
        in_bucket = primary["Bucket"]
        in_key = primary["ObjectKey"]["FullPath"]

        out_bucket = os.getenv("MEDIA_ASSETS_BUCKET_NAME") or _raise(
            "MEDIA_ASSETS_BUCKET_NAME env-var missing"
        )

        # mirror source bucket + path (without extension)
        input_key_no_ext = os.path.splitext(in_key)[0]
        output_key = f"{in_bucket}/{input_key_no_ext}"

        # delete existing proxy (.mp4) and thumbnail (.jpg) if any
        for ext in (".mp4", ".jpg"):
            old_key = f"{output_key}{ext}"
            try:
                s3.delete_object(Bucket=out_bucket, Key=old_key)
                logger.info("Deleted existing object: s3://%s/%s", out_bucket, old_key)
            except ClientError as e:
                if e.response["Error"]["Code"] != "NoSuchKey":
                    logger.warning("Failed deleting %s: %s", old_key, e)

        # inject into event for Jinja template
        event.update(
            {
                "output_bucket": out_bucket,
                "output_key": output_key,
                "mediaconvert_role_arn": os.environ["MEDIACONVERT_ROLE_ARN"],
                "mediaconvert_queue_arn": os.environ["MEDIACONVERT_QUEUE_ARN"],
                "thumbnail_width": event.get("thumbnail_width", 300),
                "thumbnail_height": event.get("thumbnail_height", 400),
            }
        )

        tmpl_bucket = os.getenv("API_TEMPLATE_BUCKET", "medialake-assets")
        paths = _tmpl_paths("mediaconvert", "video_proxy_thumbnail", "post")
        job_settings = _render_request(paths, tmpl_bucket, event)

        dest = job_settings["Settings"]["OutputGroups"][0]["OutputGroupSettings"][
            "FileGroupSettings"
        ]["Destination"]
        logger.info("Rendered MediaConvert destination: %s", dest)
        if not dest.startswith("s3://") or "None" in dest:
            _raise(f"Invalid destination rendered: {dest}")

        mc = boto3.client("mediaconvert", endpoint_url=get_mediaconvert_endpoint())
        job_response = create_job_with_retry(mc, job_settings)

        # render the API response
        result = _render_response(paths, tmpl_bucket, job_response, event)

        # ── FETCH UPDATED DYNAMODB RECORD ────────────────────────────────────
        try:
            inv_id = asset["InventoryID"]
            ddb_resp = asset_table.get_item(Key={"InventoryID": inv_id})
            updated_item = ddb_resp.get("Item", {})
        except Exception as e:
            logger.warning(
                "Failed to fetch updated DynamoDB item", extra={"error": str(e)}
            )
            updated_item = {}

        # cleanse Decimals so the Lambda JSON encoder won’t choke
        result["updatedAsset"] = _strip_decimals(updated_item)
        return result

    except Exception as e:
        logger.exception("Video proxy + thumbnail failed", extra={"error": str(e)})
        return {
            "externalJobResult": "Failed",
            "externalJobStatus": "Started",
            "error": f"Error processing video: {e}",
        }
