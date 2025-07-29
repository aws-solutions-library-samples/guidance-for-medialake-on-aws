import decimal
import importlib.util
import json
import os
import random
import time
from typing import Any, Dict, List

import boto3
import botocore
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext
from botocore.exceptions import ClientError
from jinja2 import Environment, FileSystemLoader
from lambda_middleware import lambda_middleware

# ────── Powertools ──────
logger = Logger()
tracer = Tracer()

# ────── AWS clients ──────
s3_client = boto3.client("s3")
mc = boto3.client("mediaconvert")


# ────── Fix helper ──────
def _strip_decimals(obj):
    """Recursively convert Decimal → int/float so the Lambda encoder is happy."""
    if isinstance(obj, list):
        return [_strip_decimals(v) for v in obj]
    if isinstance(obj, dict):
        return {k: _strip_decimals(v) for k, v in obj.items()}
    if isinstance(obj, decimal.Decimal):
        return int(obj) if obj % 1 == 0 else float(obj)
    return obj


# ────── helper: retry get_job on throttling ──────
def get_job_with_retry(job_id: str, max_retries: int = 5) -> Dict[str, Any]:
    attempt = 0
    while True:
        try:
            return mc.get_job(Id=job_id)
        except ClientError as e:
            if (
                e.response["Error"]["Code"] == "TooManyRequestsException"
                and attempt < max_retries
            ):
                attempt += 1
                backoff = (2**attempt) + random.random()
                logger.warning(
                    f"Throttled (attempt {attempt}/{max_retries}), retrying in {backoff:.1f}s"
                )
                time.sleep(backoff)
                continue
            logger.error(f"get_job failed: {e}")
            raise


# ────── other helpers (unchanged) ──────
def clean_asset_id(s: str) -> str:
    parts = s.split(":")
    uuid = parts[-1] if parts[-1] != "master" else parts[-2]
    return f"asset:uuid:{uuid}"


def download_s3_object(bucket: str, key: str) -> str:
    return s3_client.get_object(Bucket=bucket, Key=key)["Body"].read().decode("utf-8")


def load_and_execute_function_from_s3(bucket: str, key: str, fn: str, event: dict):
    code = download_s3_object(bucket, f"api_templates/{key}")
    spec = importlib.util.spec_from_loader("dynamic_module", loader=None)
    mod = importlib.util.module_from_spec(spec)
    exec(code, mod.__dict__)
    if not hasattr(mod, fn):
        raise AttributeError(f"{fn} not found in {key}")
    return getattr(mod, fn)(event)


def build_s3_templates_path(service: str, resource: str, method: str) -> dict:
    base = f"{resource.split('/')[-1]}_{method.lower()}"
    return {
        "url_template": f"{service}/{resource}/{base}_url.jinja",
        "url_mapping_file": f"{service}/{resource}/{base}_url_mapping.py",
        "response_template": f"{service}/{resource}/{base}_response.jinja",
        "response_mapping_file": f"{service}/{resource}/{base}_response_mapping.py",
    }


def create_custom_url(tmpls, bucket, event):
    tmpl = download_s3_object(bucket, f"api_templates/{tmpls['url_template']}")
    mapping = load_and_execute_function_from_s3(
        bucket, tmpls["url_mapping_file"], "translate_event_to_request", event
    )
    env = Environment(loader=FileSystemLoader("/tmp/"))
    env.filters["jsonify"] = json.dumps
    return env.from_string(tmpl).render(variables=mapping)


def create_response_output(tmpls, bucket, resp, event):
    tmpl = download_s3_object(bucket, f"api_templates/{tmpls['response_template']}")
    mapping = load_and_execute_function_from_s3(
        bucket,
        tmpls["response_mapping_file"],
        "translate_event_to_request",
        {"response_body": resp, "event": event},
    )
    env = Environment(loader=FileSystemLoader("/tmp/"))
    env.filters["jsonify"] = json.dumps
    return json.loads(env.from_string(tmpl).render(variables=mapping))


# ────── Lambda handler ──────
@lambda_middleware(event_bus_name=os.environ.get("EVENT_BUS_NAME", "default-event-bus"))
@logger.inject_lambda_context
@tracer.capture_lambda_handler
def lambda_handler(event: Dict[str, Any], _: LambdaContext):
    table = boto3.resource("dynamodb").Table(os.environ["MEDIALAKE_ASSET_TABLE"])
    api_template_bucket = os.environ.get("API_TEMPLATE_BUCKET", "medialake-assets")

    # ── pull job-id ──
    job_id = event.get("metadata", {}).get("externalJobId")
    if not job_id:
        raise ValueError("metadata.externalJobId not present in event")

    # ── asset basics ──
    assets = event.get("payload", {}).get("assets", [])
    if not assets:
        raise ValueError("payload.assets array missing/empty")

    asset_obj = assets[0]
    media_type = asset_obj["DigitalSourceAsset"]["Type"]  # 'Audio' / 'Video'
    inventory_id = asset_obj["InventoryID"]
    asset_id = clean_asset_id(asset_obj["DigitalSourceAsset"]["ID"])
    clean_inv_id = clean_asset_id(inventory_id)

    # ── build & call API URL ──
    s3_tmpls = build_s3_templates_path("mediaconvert", "check_status", "get")
    api_url = create_custom_url(
        s3_tmpls, api_template_bucket, event
    )  # not used further, kept for parity

    # ── get_job with retry ──
    response = get_job_with_retry(job_id)
    logger.info(response)

    # ── translate response ──
    result = create_response_output(s3_tmpls, api_template_bucket, response, event)

    # ── on COMPLETE, append reps to DDB ──
    if response["Job"]["Status"] == "COMPLETE":
        dest = response["Job"]["Settings"]["OutputGroups"][0]["OutputGroupSettings"][
            "FileGroupSettings"
        ]["Destination"]
        out_bucket = dest.split("s3://")[1].split("/")[0]
        base_path = dest.split(f"s3://{out_bucket}/")[1].rstrip("/")

        reps: List[Dict[str, Any]] = []
        if media_type == "Video":
            proxy_group = response["Job"]["Settings"]["OutputGroups"][0]
            proxy_output = proxy_group.get("Outputs", [{}])[0]
            name_mod = proxy_output.get("NameModifier", "")
            proxy_path = f"{base_path}{name_mod}.mp4"
            thumb_path = f"{base_path}_thumbnail.0000000.jpg"
            reps.extend(
                [
                    {
                        "ID": f"{asset_id}:proxy",
                        "Type": media_type,
                        "Format": "MP4",
                        "Purpose": "proxy",
                        "StorageInfo": {
                            "PrimaryLocation": {
                                "Bucket": out_bucket,
                                "ObjectKey": {"FullPath": proxy_path},
                                "FileInfo": {"Size": 5_000_000},
                                "Provider": "aws",
                                "Status": "active",
                                "StorageType": "s3",
                            }
                        },
                    },
                    {
                        "ID": f"{asset_id}:thumbnail",
                        "Type": "Image",
                        "Format": "JPEG",
                        "Purpose": "thumbnail",
                        "ImageSpec": {"Resolution": {"Height": 400, "Width": 300}},
                        "StorageInfo": {
                            "PrimaryLocation": {
                                "Bucket": out_bucket,
                                "ObjectKey": {"FullPath": thumb_path},
                                "FileInfo": {"Size": 12_670},
                                "Provider": "aws",
                                "Status": "active",
                                "StorageType": "s3",
                            }
                        },
                    },
                ]
            )
        else:
            # AUDIO
            for grp in response["Job"]["Settings"]["OutputGroups"]:
                outs = grp.get("Outputs", [])
                if outs and outs[0].get("AudioDescriptions"):
                    audio_output = outs[0]
                    break
            else:
                raise RuntimeError("No audio Outputs found in job")

            name_mod = audio_output.get("NameModifier", "")
            codec = audio_output["AudioDescriptions"][0]["CodecSettings"]["Codec"]
            proxy_path = f"{base_path}{name_mod}.{codec.lower()}"
            reps.append(
                {
                    "ID": f"{asset_id}:proxy",
                    "Type": media_type,
                    "Format": codec,
                    "Purpose": "proxy",
                    "StorageInfo": {
                        "PrimaryLocation": {
                            "Bucket": out_bucket,
                            "ObjectKey": {"FullPath": proxy_path},
                            "FileInfo": {"Size": 5_000_000},
                            "Provider": "aws",
                            "Status": "active",
                            "StorageType": "s3",
                        }
                    },
                }
            )

        try:
            table.update_item(
                Key={"InventoryID": clean_inv_id},
                UpdateExpression="SET DerivedRepresentations = list_append(if_not_exists(DerivedRepresentations, :empty), :r)",
                ConditionExpression="attribute_not_exists(DerivedRepresentations) OR NOT contains(DerivedRepresentations, :proxy_id)",
                ExpressionAttributeValues={
                    ":r": reps,
                    ":empty": [],
                    ":proxy_id": reps[0]["ID"],
                },
                ReturnValues="UPDATED_NEW",
            )
        except botocore.exceptions.ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                logger.info("Proxy already present, skipping DynamoDB update")
            else:
                raise

    # ── FETCH UPDATED DYNAMO RECORD & strip Decimals ───────────────────────
    updated_item = table.get_item(Key={"InventoryID": clean_inv_id}).get("Item", {})
    result["updatedAsset"] = _strip_decimals(updated_item)

    return result
