import os
import json
import importlib.util
import time
import random
from typing import Dict, Any, List

import boto3
from botocore.exceptions import ClientError
from jinja2 import Environment, FileSystemLoader
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext
from lambda_middleware import lambda_middleware

# ── Powertools ────────────────────────────────────────────────────────────
logger = Logger()
tracer = Tracer()

# ── AWS clients ───────────────────────────────────────────────────────────
s3_client = boto3.client("s3")


# ── NEW HELPER: retry create_job on throttling ─────────────────────────────
def create_job_with_retry(mc_client, job_settings: Dict[str, Any], max_retries: int = 5) -> Dict[str, Any]:
    attempt = 0
    while True:
        try:
            return mc_client.create_job(**job_settings)
        except ClientError as e:
            code = e.response["Error"]["Code"]
            if code == "TooManyRequestsException" and attempt < max_retries:
                attempt += 1
                backoff = (2 ** attempt) + random.random()
                logger.warning(f"create_job throttled (attempt {attempt}/{max_retries}), retrying in {backoff:.1f}s")
                time.sleep(backoff)
                continue
            logger.error(f"create_job failed: {e}")
            raise


# ── tiny util ─────────────────────────────────────────────────────────────
def _raise(msg: str):
    raise RuntimeError(msg)


# ── helper functions ──────────────────────────────────────────────────────
def clean_asset_id(asset_str: str) -> str:
    parts = asset_str.split(":")
    uuid = parts[-1] if parts[-1] != "master" else parts[-2]
    return f"asset:uuid:{uuid}"


def load_and_execute_function_from_s3(bucket: str, key: str,
                                      fn_name: str,
                                      event: Dict[str, Any]) -> Any:
    obj = s3_client.get_object(Bucket=bucket, Key=f"api_templates/{key}")
    code = obj["Body"].read().decode()
    spec = importlib.util.spec_from_loader("dynamic_module", loader=None)
    mod = importlib.util.module_from_spec(spec)
    exec(code, mod.__dict__)
    if not hasattr(mod, fn_name):
        raise AttributeError(f"{fn_name} not found in {key}")
    return getattr(mod, fn_name)(event)


def download_s3_object(bucket: str, key: str) -> str:
    obj = s3_client.get_object(Bucket=bucket, Key=key)
    return obj["Body"].read().decode()


def create_request_body(tmpl_paths: Dict[str, str],
                        tmpl_bucket: str,
                        event: Dict[str, Any]) -> Dict[str, Any]:
    tmpl_text = download_s3_object(
        tmpl_bucket,
        f"api_templates/{tmpl_paths['request_template']}"
    )
    mapping = load_and_execute_function_from_s3(
        tmpl_bucket,
        tmpl_paths["mapping_file"],
        "translate_event_to_request",
        event,
    )
    env = Environment(loader=FileSystemLoader("/tmp/"))
    env.filters["jsonify"] = json.dumps
    rendered = env.from_string(tmpl_text).render(variables=mapping)
    return json.loads(rendered)


def create_response_output(tmpl_paths: Dict[str, str],
                           tmpl_bucket: str,
                           response_body: Dict[str, Any],
                           event: Dict[str, Any]) -> Dict[str, Any]:
    tmpl_text = download_s3_object(
        tmpl_bucket,
        f"api_templates/{tmpl_paths['response_template']}"
    )
    mapping = load_and_execute_function_from_s3(
        tmpl_bucket,
        tmpl_paths["response_mapping_file"],
        "translate_event_to_request",
        {"response_body": response_body, "event": event},
    )
    env = Environment(loader=FileSystemLoader("/tmp/"))
    env.filters["jsonify"] = json.dumps
    rendered = env.from_string(tmpl_text).render(variables=mapping)
    return json.loads(rendered)


def build_s3_templates_path(service: str, resource: str,
                            method: str) -> Dict[str, str]:
    base = f"{resource.split('/')[-1]}_{method.lower()}"
    return {
        "request_template":       f"{service}/{resource}/{base}_request.jinja",
        "mapping_file":           f"{service}/{resource}/{base}_request_mapping.py",
        "response_template":      f"{service}/{resource}/{base}_response.jinja",
        "response_mapping_file":  f"{service}/{resource}/{base}_response_mapping.py",
    }


def _extract_asset(event: Dict[str, Any]) -> Dict[str, Any]:
    if "input" in event:
        return event["input"]
    assets: List[dict] = event.get("payload", {}).get("assets", [])
    if not assets:
        _raise("Event missing assets list")
    asset = assets[0]
    event["input"] = asset
    return asset


# ── MediaConvert endpoint retrieval ────────────────────────────────────────
def get_mediaconvert_endpoint() -> str:
    override = os.getenv("MEDIACONVERT_ENDPOINT_URL")
    if override:
        return override

    mc = boto3.client("mediaconvert", region_name="us-east-1")
    for attempt in range(60):
        try:
            return mc.describe_endpoints()["Endpoints"][0]["Url"]
        except ClientError as e:
            if e.response["Error"]["Code"] != "TooManyRequestsException":
                raise
            delay = (2 ** attempt) + random.random()
            logger.warning("describe_endpoints throttled, retrying in %.2fs", delay)
            time.sleep(delay)
    _raise("Unable to obtain MediaConvert endpoint after retries")


# ── Lambda handler ────────────────────────────────────────────────────────
@lambda_middleware(
    event_bus_name=os.environ.get("EVENT_BUS_NAME", "default-event-bus")
)
@logger.inject_lambda_context
@tracer.capture_lambda_handler
def lambda_handler(event: Dict[str, Any], _: LambdaContext) -> Dict[str, Any]:
    try:
        asset = _extract_asset(event)

        inventory_id  = asset.get("InventoryID") or _raise("InventoryID missing")
        source_asset  = asset.get("DigitalSourceAsset", {})
        main_repr     = source_asset.get("MainRepresentation", {})
        storage_info  = main_repr.get("StorageInfo", {})
        primary_loc   = storage_info.get("PrimaryLocation", {})

        bucket        = primary_loc.get("Bucket")
        key           = primary_loc.get("ObjectKey", {}).get("FullPath")
        output_bucket = (
            event.get("output_bucket") or
            os.environ.get("MEDIA_ASSETS_BUCKET_NAME") or
            _raise("MEDIA_ASSETS_BUCKET_NAME env-var missing")
        )

        if not all([bucket, key]):
            _raise("Missing S3 location details in event")

        clean_inventory_id = clean_asset_id(inventory_id)

        s3_tmpl = build_s3_templates_path(
            service="mediaconvert",
            resource="audio_proxy",
            method="post",
        )

        # Extra vars for Jinja mapping
        event.update({
            "mediaconvert_role_arn":  os.environ["MEDIACONVERT_ROLE_ARN"],
            "mediaconvert_queue_arn": os.environ["MEDIACONVERT_QUEUE_ARN"],
            "output_bucket":          output_bucket,
        })

        api_tmpl_bucket = os.environ.get("API_TEMPLATE_BUCKET", "medialake-assets")
        job_settings    = create_request_body(s3_tmpl, api_tmpl_bucket, event)

        # get endpoint & submit job with retry
        mc_endpoint = get_mediaconvert_endpoint()
        mc_client   = boto3.client("mediaconvert", endpoint_url=mc_endpoint)
        response    = create_job_with_retry(mc_client, job_settings)

        return create_response_output(s3_tmpl, api_tmpl_bucket, response, event)

    except Exception as e:
        logger.exception("Processing failed", extra={"error": str(e)})
        return {
            "externalJobResult": "Failed",
            "externalJobStatus": "Started",
            "error":             f"Error processing audio: {e}"
        }
