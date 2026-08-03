"""
Video reframe (Elemental Inference Smart Cropping) trigger Lambda.

- Accepts modern {"payload": {"assets": [...], "data": {...}}} events
- Submits a MediaConvert job whose video output uses
  VideoDescription.ScalingBehavior = "SMART_CROP", which delegates the crop to
  AWS Elemental Inference (AI reframes the source, keeping the region of
  interest centred) and produces a vertical (or square) output.
- Optionally reframes a single time-based segment via MediaConvert
  InputClippings (start/end supplied through the per-asset trigger params).
- The reframed output is saved as a *derived representation* of the source
  asset by the downstream check_media_convert_status node. Multiple reframes
  (different aspect ratios and/or segments) can coexist because the derived-rep
  ID encodes the aspect ratio and segment range.

The job is submitted to a dedicated Elemental Inference queue; the node's
"MediaConvert Queue Arn" parameter defaults to ${MEDIACONVERT_REFRAME_QUEUE_ARN}
which the pipeline builder resolves into this lambda's MEDIACONVERT_QUEUE_ARN.
"""

import decimal
import importlib.util
import json
import os
import os.path
import re
from typing import Any, Dict, List, Optional, Tuple

import boto3
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext
from jinja2 import Environment, FileSystemLoader
from lambda_middleware import lambda_middleware
from mediaconvert_utils import (
    MediaConvertEndpointError,
    MediaConvertThrottlingError,
    MediaConvertTimeoutError,
    emit_mediaconvert_metrics,
    get_mediaconvert_client_with_cache,
)

# ── Powertools & clients ─────────────────────────────────────────────────────
logger = Logger()
tracer = Tracer()
s3 = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")
asset_table = dynamodb.Table(os.environ["MEDIALAKE_ASSET_TABLE"])

# Default vertical aspect ratio for Elemental Inference smart cropping.
DEFAULT_ASPECT_RATIO = "9:16"

# Sentinel value of the "Aspect Ratio" node parameter that tells us to read the
# free-text "Custom Aspect Ratio" parameter (CUSTOM_ASPECT_RATIO env var) instead.
CUSTOM_ASPECT_RATIO_SENTINEL = "custom"

# Reference output height (px). Output width is derived from the aspect ratio.
# Smart cropping requires a vertical output (width <= height; 1:1 is widest).
DEFAULT_OUTPUT_HEIGHT = 1280


def _raise(msg: str):
    raise RuntimeError(msg)


def _strip_decimals(obj):
    """Recursively convert Decimal -> int/float so the Lambda JSON encoder is happy."""
    if isinstance(obj, list):
        return [_strip_decimals(v) for v in obj]
    if isinstance(obj, dict):
        return {k: _strip_decimals(v) for k, v in obj.items()}
    if isinstance(obj, decimal.Decimal):
        return int(obj) if obj % 1 == 0 else float(obj)
    return obj


def clean_asset_id(asset_str: str) -> str:
    """Normalize a DigitalSourceAsset ID to the ``asset:uuid:<uuid>`` form."""
    parts = asset_str.split(":")
    uuid = parts[-1] if parts[-1] != "master" else parts[-2]
    return f"asset:uuid:{uuid}"


def _sanitize_label(value: str) -> str:
    """Sanitize an aspect ratio / timecode into an S3- and ID-safe label."""
    return re.sub(r"[^A-Za-z0-9]+", "-", str(value)).strip("-")


def _configured_aspect_ratio() -> Optional[str]:
    """
    Resolve the aspect ratio configured on the node.

    The "Aspect Ratio" parameter (ASPECT_RATIO env var) is a preset dropdown;
    when the user picks "Custom" it carries the sentinel value "custom" and the
    actual ratio lives in the "Custom Aspect Ratio" parameter
    (CUSTOM_ASPECT_RATIO env var). Returns None when nothing is configured.
    """
    configured = (os.getenv("ASPECT_RATIO") or "").strip()
    if configured.lower() == CUSTOM_ASPECT_RATIO_SENTINEL:
        custom = (os.getenv("CUSTOM_ASPECT_RATIO") or "").strip()
        if not custom:
            _raise(
                "Aspect Ratio is set to 'Custom' but no Custom Aspect Ratio was "
                "provided. Enter a width:height value such as '3:5' on the "
                "Video Reframe node."
            )
        return custom
    return configured or None


def _parse_aspect_ratio(aspect: str) -> Tuple[int, int, int]:
    """
    Resolve an aspect-ratio string (e.g. "9:16") to output (width, height) plus
    the numeric ratio parts. Height is fixed to DEFAULT_OUTPUT_HEIGHT and width
    is derived and rounded to an even number (required by most codecs).

    Raises RuntimeError for malformed ratios or non-vertical outputs (Smart
    Cropping requires width <= height; 1:1 is the widest supported).
    """
    match = re.match(r"^\s*(\d+(?:\.\d+)?)\s*[:x/]\s*(\d+(?:\.\d+)?)\s*$", aspect)
    if not match:
        _raise(
            f"Invalid aspect ratio '{aspect}'. Expected a 'W:H' value such as '9:16'."
        )
    w_ratio = float(match.group(1))
    h_ratio = float(match.group(2))
    if w_ratio <= 0 or h_ratio <= 0:
        _raise(f"Invalid aspect ratio '{aspect}': parts must be positive.")

    height = DEFAULT_OUTPUT_HEIGHT
    width = int(round(height * (w_ratio / h_ratio)))
    width -= width % 2  # ensure even dimension
    if width <= 0:
        _raise(f"Computed a non-positive width for aspect ratio '{aspect}'.")
    if width > height:
        _raise(
            f"Aspect ratio '{aspect}' is not vertical. Elemental Inference smart "
            "cropping requires the output width to be <= the output height "
            "(1:1 is the widest supported aspect ratio)."
        )
    return width, height, height


def _extract_frame_rate(asset: Dict[str, Any]) -> float:
    """Best-effort extraction of the source frame rate; defaults to 25 fps."""
    try:
        metadata = asset.get("Metadata", {}) or {}
        embedded = metadata.get("EmbeddedMetadata", {}) or {}
        video_meta = embedded.get("video")
        if isinstance(video_meta, list) and video_meta:
            fr = video_meta[0].get("FrameRate")
            if fr:
                return float(fr)
        technical = (metadata.get("Technical", {}) or {}).get("Video", {}) or {}
        fr = technical.get("FrameRate")
        if fr:
            return float(fr)
    except (ValueError, TypeError):
        pass
    return 25.0


def _seconds_to_timecode(seconds: float, fps: float) -> str:
    """Convert seconds to an HH:MM:SS:FF timecode string (ZEROBASED)."""
    if fps <= 0:
        fps = 25.0
    total_frames = int(round(seconds * fps))
    frames = int(total_frames % round(fps))
    total_seconds = total_frames // int(round(fps))
    hh = total_seconds // 3600
    mm = (total_seconds % 3600) // 60
    ss = total_seconds % 60
    return f"{hh:02d}:{mm:02d}:{ss:02d}:{frames:02d}"


def _is_timecode(value: Any) -> bool:
    return isinstance(value, str) and bool(
        re.match(r"^\d{1,2}:\d{2}:\d{2}[:;]\d{1,3}$", value)
    )


def _resolve_segment(params: Dict[str, Any], fps: float) -> Optional[Tuple[str, str]]:
    """
    Resolve an optional segment (start, end) timecode pair from the trigger
    params. Accepts either explicit HH:MM:SS:FF timecodes
    (start_timecode/end_timecode) or numeric seconds (start_time/end_time).
    Returns None when no segment is supplied (whole-asset reframe).
    """
    start_tc = params.get("start_timecode")
    end_tc = params.get("end_timecode")
    if _is_timecode(start_tc) and _is_timecode(end_tc):
        return start_tc.replace(";", ":"), end_tc.replace(";", ":")

    start_s = params.get("start_time", params.get("start"))
    end_s = params.get("end_time", params.get("end"))
    if start_s is None or end_s is None:
        return None
    try:
        start_s = float(start_s)
        end_s = float(end_s)
    except (ValueError, TypeError):
        return None
    if end_s <= start_s:
        _raise(
            f"Invalid segment: end ({end_s}) must be greater than start ({start_s})."
        )
    return _seconds_to_timecode(start_s, fps), _seconds_to_timecode(end_s, fps)


def create_job_with_retry(
    mc_client, job_settings: Dict[str, Any], max_retries: int = 5
) -> Dict[str, Any]:
    """Wrap mc.create_job() in exponential-backoff on TooManyRequestsException."""
    import random
    import time

    from botocore.exceptions import ClientError

    attempt = 0
    while True:
        try:
            start_time = time.time()
            response = mc_client.create_job(**job_settings)
            latency_ms = (time.time() - start_time) * 1000
            emit_mediaconvert_metrics(
                "JobCreationLatency",
                latency_ms,
                unit="Milliseconds",
                dimensions={"Operation": "CreateReframeJob"},
            )
            return response
        except ClientError as e:
            code = e.response["Error"]["Code"]
            if code == "TooManyRequestsException" and attempt < max_retries:
                attempt += 1
                backoff = (2**attempt) + random.random()
                emit_mediaconvert_metrics(
                    "JobCreationThrottled",
                    1,
                    dimensions={"Operation": "CreateReframeJob"},
                )
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
    exec(
        code, mod.__dict__
    )  # nosec B102 - Controlled execution of trusted S3 templates
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
    env = Environment(
        loader=FileSystemLoader("/tmp/")
    )  # nosec B701 - Controlled template rendering with trusted input
    env.filters["jsonify"] = json.dumps
    rendered = env.from_string(tmpl).render(variables=mapping)
    try:
        return json.loads(rendered)
    except json.JSONDecodeError:
        logger.error("Broken job-settings JSON \u2193\n%s", rendered)
        raise


def _render_response(paths: dict, bucket: str, resp: dict, event: dict) -> dict:
    tmpl = _dl_s3(bucket, f"api_templates/{paths['response_template']}")
    mapping = _exec_s3_py(
        bucket,
        paths["response_mapping_file"],
        "translate_event_to_request",
        {"response_body": resp, "event": event},
    )
    env = Environment(
        loader=FileSystemLoader("/tmp/")
    )  # nosec B701 - Controlled template rendering with trusted input
    env.filters["jsonify"] = json.dumps
    return json.loads(env.from_string(tmpl).render(variables=mapping))


def _normalize_event(evt: dict) -> dict:
    assets: List[dict] = evt.get("payload", {}).get("assets", [])
    if not assets:
        _raise("Event missing payload.assets list")
    evt["input"] = assets[0]
    return assets[0]


def _get_run_params(evt: dict) -> Dict[str, Any]:
    """
    Extract per-run parameters supplied via the manual/per-segment trigger.

    The trigger delivers {"item": {"inventory_id", "params"}} which the
    middleware standardizes into payload.data. Segment ranges and an optional
    aspect-ratio override live under that params dict.
    """
    data = evt.get("payload", {}).get("data", {})
    if isinstance(data, dict):
        params = data.get("params")
        if isinstance(params, dict):
            return params
        # Some map paths nest the original item under data.item
        item = data.get("item")
        if isinstance(item, dict) and isinstance(item.get("params"), dict):
            return item["params"]
    return {}


@lambda_middleware(event_bus_name=os.getenv("EVENT_BUS_NAME", "default-event-bus"))
@logger.inject_lambda_context
@tracer.capture_lambda_handler
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    try:
        context.get_remaining_time_in_millis()
        timeout_buffer_seconds = 30

        asset = _normalize_event(event)
        dsa = asset["DigitalSourceAsset"]
        primary = dsa["MainRepresentation"]["StorageInfo"]["PrimaryLocation"]
        in_bucket = primary["Bucket"]
        in_key = primary["ObjectKey"]["FullPath"]

        out_bucket = os.getenv("MEDIA_ASSETS_BUCKET_NAME") or _raise(
            "MEDIA_ASSETS_BUCKET_NAME env-var missing"
        )

        # ── Resolve aspect ratio: per-run override > node config > default ──
        run_params = _get_run_params(event)
        aspect_ratio = (
            run_params.get("aspect_ratio")
            or _configured_aspect_ratio()
            or DEFAULT_ASPECT_RATIO
        )
        width, height, _ = _parse_aspect_ratio(aspect_ratio)
        aspect_label = _sanitize_label(aspect_ratio)  # "9:16" -> "9-16"

        # ── Optional segment (InputClippings) ──
        fps = _extract_frame_rate(asset)
        segment = _resolve_segment(run_params, fps)
        segment_label = ""
        if segment:
            segment_label = (
                f"{_sanitize_label(segment[0])}_{_sanitize_label(segment[1])}"
            )

        # ── Output naming: mirror source path, keep reframes distinct ──
        input_key_no_ext, orig_ext = os.path.splitext(in_key)
        orig_ext = orig_ext.lstrip(".").lower() if orig_ext else "unknown"
        output_key = f"{in_bucket}/{input_key_no_ext}-{orig_ext}"

        name_modifier = f"_reframe_{aspect_label}"
        if segment_label:
            name_modifier = f"{name_modifier}_{segment_label}"

        asset_id = clean_asset_id(dsa["ID"])
        derived_id = f"{asset_id}:smartcrop:{aspect_label}"
        if segment_label:
            derived_id = f"{derived_id}:{_sanitize_label(segment_label)}"

        # Values consumed by the Jinja request template + mapping.
        event.update(
            {
                "input_bucket": in_bucket,
                "input_key": in_key,
                "output_bucket": out_bucket,
                "output_key": output_key,
                "mediaconvert_role_arn": os.environ["MEDIACONVERT_ROLE_ARN"],
                "mediaconvert_queue_arn": os.environ["MEDIACONVERT_QUEUE_ARN"],
                "reframe_width": width,
                "reframe_height": height,
                "reframe_name_modifier": name_modifier,
                "reframe_aspect_ratio": aspect_ratio,
                "reframe_segment_start": segment[0] if segment else None,
                "reframe_segment_end": segment[1] if segment else None,
                # UserMetadata used by check_media_convert_status to create the
                # derived representation once the job completes.
                "reframe_purpose": "smartcrop",
                "reframe_derived_id": derived_id,
                "reframe_inventory_id": asset["InventoryID"],
            }
        )

        logger.info(
            "Submitting reframe job",
            extra={
                "aspect_ratio": aspect_ratio,
                "width": width,
                "height": height,
                "segment": segment,
                "name_modifier": name_modifier,
                "derived_id": derived_id,
            },
        )

        tmpl_bucket = os.getenv("API_TEMPLATE_BUCKET", "medialake-assets")
        paths = _tmpl_paths("mediaconvert", "video_reframe", "post")
        job_settings = _render_request(paths, tmpl_bucket, event)

        dest = job_settings["Settings"]["OutputGroups"][0]["OutputGroupSettings"][
            "FileGroupSettings"
        ]["Destination"]
        if not dest.startswith("s3://") or "None" in dest:
            _raise(f"Invalid destination rendered: {dest}")

        try:
            region = os.environ.get("AWS_REGION", "us-east-1")
            mc = get_mediaconvert_client_with_cache(
                region=region, timeout_buffer_seconds=timeout_buffer_seconds
            )
        except MediaConvertEndpointError as e:
            emit_mediaconvert_metrics(
                "EndpointLookupFailure", 1, dimensions={"Region": region}
            )
            raise RuntimeError(f"Failed to obtain MediaConvert endpoint: {e}") from e
        except MediaConvertTimeoutError as e:
            raise RuntimeError(f"Lambda timeout approaching: {e}") from e
        except MediaConvertThrottlingError:
            emit_mediaconvert_metrics(
                "ThrottlingError", 1, dimensions={"Region": region}
            )
            raise

        job_response = create_job_with_retry(mc, job_settings)
        result = _render_response(paths, tmpl_bucket, job_response, event)

        try:
            inv_id = asset["InventoryID"]
            ddb_resp = asset_table.get_item(Key={"InventoryID": inv_id})
            updated_item = ddb_resp.get("Item", {})
        except Exception as e:
            logger.warning(
                "Failed to fetch updated DynamoDB item", extra={"error": str(e)}
            )
            updated_item = {}

        result["updatedAsset"] = _strip_decimals(updated_item)
        return result

    except MediaConvertTimeoutError as e:
        emit_mediaconvert_metrics(
            "LambdaTimeout", 1, dimensions={"Operation": "VideoReframe"}
        )
        raise RuntimeError(f"Lambda timeout approaching: {e}") from e
    except MediaConvertThrottlingError as e:
        emit_mediaconvert_metrics(
            "ThrottlingFailure", 1, dimensions={"Operation": "VideoReframe"}
        )
        raise RuntimeError(f"MediaConvert API throttled: {e}") from e
    except MediaConvertEndpointError as e:
        emit_mediaconvert_metrics(
            "EndpointError", 1, dimensions={"Operation": "VideoReframe"}
        )
        raise RuntimeError(f"MediaConvert endpoint error: {e}") from e
    except Exception as e:
        logger.exception("Video reframe failed", extra={"error": str(e)})
        emit_mediaconvert_metrics(
            "UnexpectedError", 1, dimensions={"Operation": "VideoReframe"}
        )
        raise RuntimeError(f"Error processing reframe: {e}") from e
