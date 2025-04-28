import boto3
import json
import os
import importlib.util
from typing import Dict, Any, Optional
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
s3_client = boto3.client("s3")

# ────── helpers ──────────────────────────────────────────────────────────────
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
    """Pull a .py file from S3, import it dynamically, and run a given function."""
    try:
        code = download_s3_object(bucket, f"api_templates/{key}")
        spec = importlib.util.spec_from_loader("dynamic_module", loader=None)
        module = importlib.util.module_from_spec(spec)
        exec(code, module.__dict__)
        if not hasattr(module, function_name):
            raise AttributeError(f"{function_name} not found in {key}")
        return getattr(module, function_name)(event)
    except Exception as e:
        logger.error(f"Dynamic import failure: {e}")
        raise


def build_s3_templates_path(service: str, resource: str, method: str) -> dict:
    resource_name = resource.split("/")[-1]
    prefix = f"{resource_name}_{method.lower()}"
    return {
        "url_template":           f"{service}/{resource}/{prefix}_url.jinja",
        "url_mapping_file":       f"{service}/{resource}/{prefix}_url_mapping.py",
        "response_template":      f"{service}/{resource}/{prefix}_response.jinja",
        "response_mapping_file":  f"{service}/{resource}/{prefix}_response_mapping.py",
    }


def create_custom_url(s3_templates, bucket, event):
    fn = "translate_event_to_request"
    tmpl_str = download_s3_object(bucket, f"api_templates/{s3_templates['url_template']}")
    mapping   = load_and_execute_function_from_s3(bucket,
                                                  s3_templates["url_mapping_file"],
                                                  fn,
                                                  event)
    env = Environment(loader=FileSystemLoader("/tmp/"))
    env.filters["jsonify"] = json.dumps
    return env.from_string(tmpl_str).render(variables=mapping)


def create_response_output(s3_templates, bucket, response_body, event):
    fn = "translate_event_to_request"
    tmpl_str = download_s3_object(bucket, f"api_templates/{s3_templates['response_template']}")
    mapping  = load_and_execute_function_from_s3(bucket,
                                                 s3_templates["response_mapping_file"],
                                                 fn,
                                                 {"response_body": response_body, "event": event})
    env = Environment(loader=FileSystemLoader("/tmp/"))
    env.filters["jsonify"] = json.dumps
    rendered = env.from_string(tmpl_str).render(variables=mapping)
    return json.loads(rendered)

# ────── handler ──────────────────────────────────────────────────────────────
@lambda_middleware(event_bus_name=os.environ.get("EVENT_BUS_NAME", "default-event-bus"))
@logger.inject_lambda_context
@tracer.capture_lambda_handler
def lambda_handler(event: Dict[str, Any], context: LambdaContext):
    table = boto3.resource("dynamodb").Table(os.environ["MEDIALAKE_ASSET_TABLE"])
    api_template_bucket = os.environ.get("API_TEMPLATE_BUCKET", "medialake-assets")

    # ── NEW: pull job-id directly from metadata ──
    try:
        job_id = event["metadata"]["externalJobId"]
    except KeyError:
        raise ValueError("metadata.externalJobId not present in event")

    # ── asset basics ──
    assets = event.get("payload", {}).get("assets", [])
    if not assets:
        raise ValueError("payload.assets array missing/empty")

    asset_obj     = assets[0]
    media_type    = asset_obj["DigitalSourceAsset"]["Type"]          # 'Audio' / 'Video'
    inventory_id  = asset_obj["InventoryID"]
    asset_id      = clean_asset_id(asset_obj["DigitalSourceAsset"]["ID"])
    clean_inv_id  = clean_asset_id(inventory_id)

    # ── build & call API URL (template logic unchanged) ──
    s3_templates  = build_s3_templates_path("mediaconvert", "check_status", "get")
    try:
        api_full_url = create_custom_url(s3_templates, api_template_bucket, event)
    except Exception as e:
        logger.error(f"create_custom_url failed: {e}")
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}

    # ── MediaConvert get-job ──
    try:
        mc = boto3.client("mediaconvert", region_name="us-east-1")
        response = mc.get_job(Id=job_id)
        logger.info(response)
    except Exception as e:
        logger.error(f"MediaConvert get_job failed: {e}")
        raise

    # ── translate response via template ──
    try:
        result = create_response_output(s3_templates, api_template_bucket, response, event)
    except Exception as e:
        logger.error(f"create_response_output failed: {e}")
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}

    # ── if complete, update DynamoDB with proxy / thumbnail representations ──
    if response["Job"]["Status"] == "COMPLETE":
        out_grp = response["Job"]["Settings"]["OutputGroups"][0]["OutputGroupSettings"]["FileGroupSettings"]
        out_bucket = out_grp["Destination"].split("s3://")[1].split("/")[0]
        base_path  = out_grp["Destination"].split(f"s3://{out_bucket}/")[1]

        if media_type == "Video":
            proxy_path      = f"{base_path}.mp4"
            thumb_path      = f"{base_path}_thumbnail.0000000.jpg"
            proxy_format    = "MP4"
            has_thumb       = True
        else:  # Audio
            proxy_path      = f"{base_path}.mp3"
            thumb_path      = None
            proxy_format    = "MP3"
            has_thumb       = False
            for grp in response["Job"]["Settings"]["OutputGroups"]:
                if "Outputs" in grp and grp["Outputs"]:
                    desc = grp["Outputs"][0].get("AudioDescriptions", [{}])[0]
                    codec = desc.get("CodecSettings", {}).get("Codec")
                    if codec:
                        proxy_format = codec

        # Sizes can be pulled from S3 head-object if needed; hard-coded placeholders here
        proxy_size, thumb_size = 5_000_000, 12_670

        proxy_rep = {
            "ID":        f"{asset_id}:proxy",
            "Type":      media_type,
            "Format":    proxy_format,
            "Purpose":   "proxy",
            "StorageInfo": {
                "PrimaryLocation": {
                    "Bucket": out_bucket,
                    "ObjectKey": {"FullPath": proxy_path},
                    "FileInfo": {"Size": proxy_size},
                    "Provider": "aws",
                    "Status":   "active",
                    "StorageType": "s3",
                }
            },
        }

        reps = [proxy_rep]
        if has_thumb:
            reps.append({
                "ID":      f"{asset_id}:thumbnail",
                "Type":    "Image",
                "Format":  "JPEG",
                "Purpose": "thumbnail",
                "ImageSpec": {"Resolution": {"Height": 400, "Width": 300}},
                "StorageInfo": {
                    "PrimaryLocation": {
                        "Bucket": out_bucket,
                        "ObjectKey": {"FullPath": thumb_path},
                        "FileInfo": {"Size": thumb_size},
                        "Provider": "aws",
                        "Status":   "active",
                        "StorageType": "s3",
                    }
                },
            })

        try:
            table.update_item(
                Key={"InventoryID": clean_inv_id},
                UpdateExpression=(
                    "SET DerivedRepresentations = "
                    "list_append(if_not_exists(DerivedRepresentations, :empty), :r)"
                ),
                ConditionExpression=(
                    "attribute_not_exists(DerivedRepresentations) "
                    "OR NOT contains(DerivedRepresentations, :proxy_id)"
                ),
                ExpressionAttributeValues={
                    ":r": reps,
                    ":empty": [],
                    ":proxy_id": proxy_rep["ID"],
                },
                ReturnValues="UPDATED_NEW",
            )
        except botocore.exceptions.ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                logger.info("Proxy already present, skipping DynamoDB update")
            else:
                raise

    return result
