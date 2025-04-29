import boto3
import json
import os
import importlib.util
import time
import random
from typing import Dict, Any
from urllib.parse import urljoin
from botocore.exceptions import ClientError
from jinja2 import Environment, FileSystemLoader
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext
import botocore
from lambda_middleware import lambda_middleware

# ────── Powertools ──────
logger = Logger()
tracer = Tracer()

# ────── AWS clients ──────
s3_client = boto3.client("s3")
mc        = boto3.client("mediaconvert", region_name="us-east-1")


# ────── helper: retry get_job on throttling ──────
def get_job_with_retry(job_id: str, max_retries: int = 5) -> Dict[str, Any]:
    attempt = 0
    while True:
        try:
            return mc.get_job(Id=job_id)
        except ClientError as e:
            code = e.response["Error"]["Code"]
            if code == "TooManyRequestsException" and attempt < max_retries:
                attempt += 1
                backoff = (2 ** attempt) + random.random()
                logger.warning(f"Throttled (attempt {attempt}/{max_retries}), retrying in {backoff:.1f}s")
                time.sleep(backoff)
                continue
            # either non‐throttle or out of retries
            logger.error(f"get_job failed: {e}")
            raise


# ────── other helpers (unchanged) ──────
def clean_asset_id(input_string: str) -> str:
    parts = input_string.split(":")
    uuid = parts[-1] if parts[-1] != "master" else parts[-2]
    return f"asset:uuid:{uuid}"

def download_s3_object(bucket: str, key: str) -> str:
    try:
        obj = s3_client.get_object(Bucket=bucket, Key=key)
        return obj["Body"].read().decode("utf-8")
    except ClientError as e:
        logger.error(f"Error downloading S3 object: {e}")
        raise

def load_and_execute_function_from_s3(bucket: str, key: str, function_name: str, event: dict):
    code = download_s3_object(bucket, f"api_templates/{key}")
    spec = importlib.util.spec_from_loader("dynamic_module", loader=None)
    module = importlib.util.module_from_spec(spec)
    exec(code, module.__dict__)
    if not hasattr(module, function_name):
        raise AttributeError(f"{function_name} not found in {key}")
    return getattr(module, function_name)(event)

def build_s3_templates_path(service: str, resource: str, method: str) -> dict:
    resource_name = resource.split("/")[-1]
    prefix = f"{resource_name}_{method.lower()}"
    return {
        "url_template":          f"{service}/{resource}/{prefix}_url.jinja",
        "url_mapping_file":      f"{service}/{resource}/{prefix}_url_mapping.py",
        "response_template":     f"{service}/{resource}/{prefix}_response.jinja",
        "response_mapping_file": f"{service}/{resource}/{prefix}_response_mapping.py",
    }

def create_custom_url(s3_templates, bucket, event):
    tmpl_str = download_s3_object(bucket, f"api_templates/{s3_templates['url_template']}")
    mapping  = load_and_execute_function_from_s3(bucket, s3_templates["url_mapping_file"], "translate_event_to_request", event)
    env = Environment(loader=FileSystemLoader("/tmp/"))
    env.filters["jsonify"] = json.dumps
    return env.from_string(tmpl_str).render(variables=mapping)

def create_response_output(s3_templates, bucket, response_body, event):
    tmpl_str = download_s3_object(bucket, f"api_templates/{s3_templates['response_template']}")
    mapping  = load_and_execute_function_from_s3(bucket, s3_templates["response_mapping_file"], "translate_event_to_request", {"response_body": response_body, "event": event})
    env = Environment(loader=FileSystemLoader("/tmp/"))
    env.filters["jsonify"] = json.dumps
    return json.loads(env.from_string(tmpl_str).render(variables=mapping))


# ────── Lambda handler ──────
@lambda_middleware(event_bus_name=os.environ.get("EVENT_BUS_NAME", "default-event-bus"))
@logger.inject_lambda_context
@tracer.capture_lambda_handler
def lambda_handler(event: Dict[str, Any], context: LambdaContext):
    table               = boto3.resource("dynamodb").Table(os.environ["MEDIALAKE_ASSET_TABLE"])
    api_template_bucket = os.environ.get("API_TEMPLATE_BUCKET", "medialake-assets")

    # ── pull job-id ──
    try:
        job_id = event["metadata"]["externalJobId"]
    except KeyError:
        raise ValueError("metadata.externalJobId not present in event")

    # ── asset basics ──
    assets       = event.get("payload", {}).get("assets", [])
    if not assets:
        raise ValueError("payload.assets array missing/empty")

    asset_obj    = assets[0]
    media_type   = asset_obj["DigitalSourceAsset"]["Type"]   # 'Audio' / 'Video'
    inventory_id = asset_obj["InventoryID"]
    asset_id     = clean_asset_id(asset_obj["DigitalSourceAsset"]["ID"])
    clean_inv_id = clean_asset_id(inventory_id)

    # ── build & call API URL ──
    s3_templates = build_s3_templates_path("mediaconvert", "check_status", "get")
    try:
        api_full_url = create_custom_url(s3_templates, api_template_bucket, event)
    except Exception as e:
        logger.error(f"create_custom_url failed: {e}")
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}

    # ── get_job with retry ──
    response = get_job_with_retry(job_id)
    logger.info(response)

    # ── translate response ──
    try:
        result = create_response_output(s3_templates, api_template_bucket, response, event)
    except Exception as e:
        logger.error(f"create_response_output failed: {e}")
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}

    # ── on COMPLETE, append reps to DDB ──
    if response["Job"]["Status"] == "COMPLETE":
        dest       = response["Job"]["Settings"]["OutputGroups"][0]["OutputGroupSettings"]["FileGroupSettings"]["Destination"]
        out_bucket = dest.split("s3://")[1].split("/")[0]
        base_path  = dest.split(f"s3://{out_bucket}/")[1].rstrip("/")

        reps = []
        if media_type == "Video":
            proxy_group   = response["Job"]["Settings"]["OutputGroups"][0]
            proxy_output  = proxy_group.get("Outputs", [{}])[0]
            name_mod      = proxy_output.get("NameModifier", "")
            proxy_ext     = ".mp4"
            proxy_path    = f"{base_path}{name_mod}{proxy_ext}"
            thumb_path    = f"{base_path}_thumbnail.0000000.jpg"

            reps.extend([
                {
                    "ID":      f"{asset_id}:proxy",
                    "Type":    media_type,
                    "Format":  "MP4",
                    "Purpose": "proxy",
                    "StorageInfo": {
                        "PrimaryLocation": {
                            "Bucket": out_bucket,
                            "ObjectKey": {"FullPath": proxy_path},
                            "FileInfo": {"Size": 5_000_000},
                            "Provider": "aws",
                            "Status":   "active",
                            "StorageType": "s3",
                        }
                    },
                },
                {
                    "ID":      f"{asset_id}:thumbnail",
                    "Type":    "Image",
                    "Format":  "JPEG",
                    "Purpose": "thumbnail",
                    "ImageSpec": {"Resolution": {"Height": 400, "Width": 300}},
                    "StorageInfo": {
                        "PrimaryLocation": {
                            "Bucket": out_bucket,
                            "ObjectKey": {"FullPath": thumb_path},
                            "FileInfo": {"Size": 12_670},
                            "Provider": "aws",
                            "Status":   "active",
                            "StorageType": "s3",
                        }
                    },
                }
            ])
        else:
            # AUDIO path
            for grp in response["Job"]["Settings"]["OutputGroups"]:
                outs = grp.get("Outputs", [])
                if outs and outs[0].get("AudioDescriptions"):
                    audio_output = outs[0]
                    break
            else:
                raise RuntimeError("No audio Outputs found in job")

            name_mod = audio_output.get("NameModifier", "")
            codec    = audio_output["AudioDescriptions"][0]["CodecSettings"]["Codec"]
            ext      = f".{codec.lower()}"
            proxy_path = f"{base_path}{name_mod}{ext}"

            reps.append({
                "ID":      f"{asset_id}:proxy",
                "Type":    media_type,
                "Format":  codec,
                "Purpose": "proxy",
                "StorageInfo": {
                    "PrimaryLocation": {
                        "Bucket": out_bucket,
                        "ObjectKey": {"FullPath": proxy_path},
                        "FileInfo": {"Size": 5_000_000},
                        "Provider": "aws",
                        "Status":   "active",
                        "StorageType": "s3",
                    }
                },
            })

        # write to DynamoDB
        try:
            table.update_item(
                Key={"InventoryID": clean_inv_id},
                UpdateExpression=(
                    "SET DerivedRepresentations = list_append(if_not_exists(DerivedRepresentations, :empty), :r)"
                ),
                ConditionExpression=(
                    "attribute_not_exists(DerivedRepresentations) "
                    "OR NOT contains(DerivedRepresentations, :proxy_id)"
                ),
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

    return result
