# """
# Video-proxy trigger Lambda (no DynamoDB cache)
# • Accepts both legacy {"input": …} and modern {"payload": {"assets": …}} events
# • Renders MediaConvert job via Jinja template stored in S3
# • Retries describe_endpoints with exponential back-off
# """

# import os, json, time, random, importlib.util
# from typing import Dict, Any, List

# import boto3
# from botocore.exceptions import ClientError
# from jinja2 import Environment, FileSystemLoader
# from aws_lambda_powertools import Logger, Tracer
# from aws_lambda_powertools.utilities.typing import LambdaContext
# from lambda_middleware import lambda_middleware

# # ── Powertools ────────────────────────────────────────────────────────────
# logger = Logger()
# tracer = Tracer()

# # ── AWS clients ───────────────────────────────────────────────────────────
# s3_client = boto3.client("s3")

# # ── tiny util ─────────────────────────────────────────────────────────────
# def _raise(msg: str):  # one-liner helper
#     raise RuntimeError(msg)


# # ── MediaConvert endpoint helper (no DynamoDB) ────────────────────────────
# def get_mediaconvert_endpoint() -> str:
#     """Retry describe_endpoints() up to 60 × with exponential back-off."""
#     override = os.getenv("MEDIACONVERT_ENDPOINT_URL")
#     if override:
#         return override                              # static override if you want

#     mc = boto3.client("mediaconvert", region_name="us-east-1")
#     for attempt in range(60):
#         try:
#             return mc.describe_endpoints()["Endpoints"][0]["Url"]
#         except ClientError as e:
#             if e.response["Error"]["Code"] != "TooManyRequestsException":
#                 raise
#             delay = (2 ** attempt) + random.random()
#             logger.warning(f"describe_endpoints throttled, retrying in {delay:.2f}s")
#             time.sleep(delay)
#     _raise("Unable to obtain MediaConvert endpoint after retries")


# # ── template helpers ──────────────────────────────────────────────────────
# def _exec_s3_py(bucket: str, key: str, fn: str, arg: dict) -> dict:
#     obj  = s3_client.get_object(Bucket=bucket, Key=f"api_templates/{key}")
#     code = obj["Body"].read().decode()
#     spec = importlib.util.spec_from_loader("dyn_mod", loader=None)
#     mod  = importlib.util.module_from_spec(spec)
#     exec(code, mod.__dict__)
#     return getattr(mod, fn)(arg)

# def _dl_s3(bucket: str, key: str) -> str:
#     return s3_client.get_object(Bucket=bucket, Key=key)["Body"].read().decode()

# def _tmpl_paths(service: str, resource: str, method: str) -> Dict[str, str]:
#     base = f"{resource.split('/')[-1]}_{method.lower()}"
#     return {
#         "request_template"     : f"{service}/{resource}/{base}_request.jinja",
#         "mapping_file"         : f"{service}/{resource}/{base}_request_mapping.py",
#         "response_template"    : f"{service}/{resource}/{base}_response.jinja",
#         "response_mapping_file": f"{service}/{resource}/{base}_response_mapping.py",
#     }

# def _render_request(paths: dict, bucket: str, event: dict) -> dict:
#     tmpl = _dl_s3(bucket, f"api_templates/{paths['request_template']}")
#     mapping = _exec_s3_py(bucket, paths["mapping_file"],
#                           "translate_event_to_request", event)
#     env = Environment(loader=FileSystemLoader("/tmp/")); env.filters["jsonify"] = json.dumps
#     return json.loads(env.from_string(tmpl).render(variables=mapping))

# def _render_response(paths: dict, bucket: str,
#                      resp: dict, event: dict) -> dict:
#     tmpl = _dl_s3(bucket, f"api_templates/{paths['response_template']}")
#     mapping = _exec_s3_py(bucket, paths["response_mapping_file"],
#                           "translate_event_to_request",
#                           {"response_body": resp, "event": event})
#     env = Environment(loader=FileSystemLoader("/tmp/")); env.filters["jsonify"] = json.dumps
#     return json.loads(env.from_string(tmpl).render(variables=mapping))


# # ── event shim ────────────────────────────────────────────────────────────
# def _normalize_event(evt: dict) -> dict:
#     """
#     Ensures evt['input'] always exists for the mapping script.
#     Accepts both legacy and new event shapes.
#     """
#     if "input" in evt:
#         return evt["input"]

#     assets: List[dict] = evt.get("payload", {}).get("assets", [])
#     if not assets:
#         _raise("Event missing payload.assets list")
#     asset = assets[0]
#     evt["input"] = asset
#     return asset


# # ── Lambda handler ────────────────────────────────────────────────────────
# @lambda_middleware(event_bus_name=os.getenv("EVENT_BUS_NAME", "default-event-bus"))
# @logger.inject_lambda_context
# @tracer.capture_lambda_handler
# def lambda_handler(event: Dict[str, Any], _: LambdaContext) -> Dict[str, Any]:
#     try:
#         asset = _normalize_event(event)

#         # source S3 location
#         primary = (asset["DigitalSourceAsset"]["MainRepresentation"]
#                    ["StorageInfo"]["PrimaryLocation"])
#         in_bucket = primary["Bucket"]
#         in_key    = primary["ObjectKey"]["FullPath"]

#         # destination S3 location (prefix must end "/")
#         out_bucket = os.getenv("MEDIA_ASSETS_BUCKET_NAME") or _raise("MEDIA_ASSETS_BUCKET_NAME env-var missing")
#         asset_uuid = asset["InventoryID"].split(":")[-1]
#         out_prefix = f"video_proxies/{asset_uuid}/"

#         # expose variables for mapping / template
#         event.update({
#             "output_bucket"         : out_bucket,
#             "output_key"            : out_prefix,                 # <- prefix, ends “/”
#             "mediaconvert_role_arn" : os.environ["MEDIACONVERT_ROLE_ARN"],
#             "mediaconvert_queue_arn": os.environ["MEDIACONVERT_QUEUE_ARN"],
#         })

#         tmpl_bucket = os.getenv("API_TEMPLATE_BUCKET", "medialake-assets")
#         paths       = _tmpl_paths("mediaconvert", "video_proxy", "post")
#         job_settings = _render_request(paths, tmpl_bucket, event)

#         # validate Destination so we never hit the regex error again
#         dest = (job_settings["Settings"]["OutputGroups"][0]
#                                ["OutputGroupSettings"]["FileGroupSettings"]["Destination"])
#         logger.info(f"Rendered Destination → {dest}")
#         if not dest.startswith("s3://") or "None" in dest:
#             _raise(f"Invalid Destination rendered: {dest}")

#         # submit the job
#         mc = boto3.client("mediaconvert", endpoint_url=get_mediaconvert_endpoint())
#         job_response = mc.create_job(**job_settings)

#         return _render_response(paths, tmpl_bucket, job_response, event)

#     except Exception as e:
#         logger.exception("Video proxy failed", extra={"error": str(e)})
#         return {
#             "externalJobResult": "Failed",
#             "externalJobStatus": "Started",
#             "error"           : f"Error processing video: {e}",
#         }


"""
Video-proxy + thumbnail trigger Lambda (no DynamoDB cache)

• Accepts legacy {"input": …} and modern {"payload": {"assets": …}} events
• Renders a MediaConvert job (proxy MP4 + FRAME_CAPTURE JPEG) from Jinja in S3
• Retries describe_endpoints with exponential back-off
"""

import os, json, time, random, importlib.util
from typing import Dict, Any, List

import boto3
from botocore.exceptions import ClientError
from jinja2 import Environment, FileSystemLoader
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext
from lambda_middleware import lambda_middleware

# ── Powertools ───────────────────────────────────────────────────────────
logger = Logger()
tracer = Tracer()

s3 = boto3.client("s3")


# ── tiny util ────────────────────────────────────────────────────────────
def _raise(msg: str):
    raise RuntimeError(msg)


# ── MediaConvert endpoint helper ─────────────────────────────────────────
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
            logger.warning(
                "describe_endpoints throttled, retrying in %.2fs", delay
            )
            time.sleep(delay)
    _raise("Unable to obtain MediaConvert endpoint after retries")


# ── helpers for loading / executing artefacts stored in S3 ───────────────
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
    return json.loads(env.from_string(tmpl).render(variables=mapping))


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


# ── event shim ───────────────────────────────────────────────────────────
def _normalize_event(evt: dict) -> dict:
    if "input" in evt:
        return evt["input"]

    assets: List[dict] = evt.get("payload", {}).get("assets", [])
    if not assets:
        _raise("Event missing payload.assets list")

    asset = assets[0]
    evt["input"] = asset
    return asset


# ── Lambda handler ───────────────────────────────────────────────────────
@lambda_middleware(event_bus_name=os.getenv("EVENT_BUS_NAME", "default-event-bus"))
@logger.inject_lambda_context
@tracer.capture_lambda_handler
def lambda_handler(event: Dict[str, Any], _: LambdaContext) -> Dict[str, Any]:
    try:
        asset = _normalize_event(event)

        # ── source file ──────────────────────────────────────────
        primary = (
            asset["DigitalSourceAsset"]["MainRepresentation"]["StorageInfo"][
                "PrimaryLocation"
            ]
        )
        in_bucket = primary["Bucket"]
        in_key = primary["ObjectKey"]["FullPath"]

        # ── destination location ────────────────────────────────
        out_bucket = os.getenv("MEDIA_ASSETS_BUCKET_NAME") or _raise(
            "MEDIA_ASSETS_BUCKET_NAME env-var missing"
        )
        asset_uuid = asset["InventoryID"].split(":")[-1]
        out_prefix = f"video_proxies/{asset_uuid}/"  # MUST end “/”

        # ── values for mapping / template ───────────────────────
        event.update(
            {
                "output_bucket": out_bucket,
                "output_key": out_prefix,
                "mediaconvert_role_arn": os.environ["MEDIACONVERT_ROLE_ARN"],
                "mediaconvert_queue_arn": os.environ["MEDIACONVERT_QUEUE_ARN"],
                "thumbnail_width": event.get("thumbnail_width", 300),
                "thumbnail_height": event.get("thumbnail_height", 400),
                # let mapping dig a frame-count out of metadata if desired
            }
        )

        tmpl_bucket = os.getenv("API_TEMPLATE_BUCKET", "medialake-assets")
        paths = _tmpl_paths(
            "mediaconvert", "video_proxy_thumbnail", "post"
        )  # <── NEW resource name
        job_settings = _render_request(paths, tmpl_bucket, event)

        # sanity-check the destination
        dest = (
            job_settings["Settings"]["OutputGroups"][0]["OutputGroupSettings"][
                "FileGroupSettings"
            ]["Destination"]
        )
        logger.info("Rendered MediaConvert destination: %s", dest)
        if not dest.startswith("s3://") or "None" in dest:
            _raise(f"Invalid destination rendered: {dest}")

        mc = boto3.client("mediaconvert", endpoint_url=get_mediaconvert_endpoint())
        job_response = mc.create_job(**job_settings)

        return _render_response(paths, tmpl_bucket, job_response, event)

    except Exception as e:
        logger.exception("Video proxy + thumbnail failed", extra={"error": str(e)})
        return {
            "externalJobResult": "Failed",
            "externalJobStatus": "Started",
            "error": f"Error processing video: {e}",
        }
