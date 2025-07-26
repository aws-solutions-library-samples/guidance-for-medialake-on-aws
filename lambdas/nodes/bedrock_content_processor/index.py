import importlib.util
import json
import os
from decimal import Decimal
from typing import Any, Callable, Dict, Union
from urllib.parse import urlparse

import boto3
from aws_lambda_powertools import Logger, Tracer
from botocore.exceptions import ClientError
from jinja2 import Environment, FileSystemLoader
from lambda_middleware import lambda_middleware

# ────────────────────────────────────────────────────────────
# Powertools & AWS clients
# ────────────────────────────────────────────────────────────
logger = Logger()
tracer = Tracer()

s3 = boto3.resource("s3")
# Bedrock runtime client will be created with region support in the handler
bedrock_rt = None
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["MEDIALAKE_ASSET_TABLE"])

# ────────────────────────────────────────────────────────────
# Constants
# ────────────────────────────────────────────────────────────

ImagePayload = Dict[str, str]

# Default prompts
DEFAULT_PROMPTS = {
    "summary_100": (
        "**You are a media‐asset‐management specialist.**\n"
        "The following is content from a media file (podcast, feature film, corporate video, etc.).\n"
        "In **100 words or less**, write a **single paragraph** that:\n"
        "  • Distills the **core topic or theme**,\n"
        "  • Highlights the **key messages & insights**,\n"
        "  • Summarizes the **major arguments or plot points**, and\n"
        "  • Conveys the **tone & style**.\n"
        "Use concise, industry‐standard terminology so a MAM user can immediately grasp the essence of the content."
    ),
    "describe_image": (
        "**You are an image-description assistant.**\n"
        "Given the content of an image, provide a clear, detailed description "
        "that covers:\n"
        "• **Objects & Subjects** – What is visible?\n"
        "• **Setting & Context** – Where is it and what's happening?\n"
        "• **Colors & Textures** – Key visual attributes.\n"
        "• **Relationships & Actions** – How elements interact.\n"
        "Use language suitable for accessibility and metadata tagging."
    ),
    "extract_key_points": (
        "**You are a content analysis specialist.**\n"
        "Extract the 5-7 most important key points from the provided content. "
        "For each key point:\n"
        "1. Provide a concise headline (5-8 words)\n"
        "2. Add 1-2 sentences of supporting detail\n"
        "Focus on the most significant information that would be valuable "
        "for content categorization and retrieval."
    ),
    "analyze_sentiment": (
        "**You are a sentiment analysis expert.**\n"
        "Analyze the emotional tone and sentiment of the provided content. "
        "In your analysis, include:\n"
        "1. Overall sentiment (positive, negative, neutral, mixed)\n"
        "2. Dominant emotions expressed\n"
        "3. Any significant sentiment shifts throughout the content\n"
        "4. Key phrases that strongly indicate sentiment\n"
        "Provide your analysis in a structured format suitable for metadata tagging."
    ),
    "structured_recap": (
        "**You are a video recapper crafting concise, structured outlines for versatile recap formats.**\n"
        "Given the content of the provided video, produce a clear, human‑readable outline that includes:\n"
        "1. **Usage Style:** a brief label describing the type of recap\n"
        "2. **Hook:** a 1–2 sentence opener to grab attention\n"
        "3. **Moments:**\n"
        "   - **Timestamp:** approximate time (e.g., “00:01:23”)\n"
        "     **Description:** vivid visual summary of the moment\n"
        "     **Tone:** emotional or pacing guidance\n"
        "   (repeat for 4–7 key moments)\n"
        "4. **Voiceover Suggestions:** 1–2 lines of narration corresponding to each moment\n"
        "5. **Audio Cues:** recommended music style or sound effects\n"
        "6. **Closing Summary:** a final line that leaves viewers wanting more\n"
        "Present your response as a structured outline with headings and bullets."
    ),
}


def _pegasus_builder(
    instr: str, content: Union[str, ImagePayload, Dict[str, str]]
) -> Dict[str, Any]:
    """
    Builder for TwelveLabs Pegasus 1.2 via Amazon Bedrock.
    Supports either S3 URI ('s3Location') or base64-encoded video ('base64String').
    """
    # Base request structure
    body = {"inputPrompt": instr, "temperature": 0}
    if isinstance(content, dict):
        if "b64" in content:
            # Base64 payload
            body["mediaSource"] = {"base64String": content["b64"]}
        elif "uri" in content:
            # S3 location payload with bucket owner
            s3_location = {"uri": content["uri"]}
            if "bucketOwner" in content:
                s3_location["bucketOwner"] = content["bucketOwner"]
            body["mediaSource"] = {"s3Location": s3_location}
    else:
        # Simple S3 URI payload (fallback)
        body["mediaSource"] = {"s3Location": {"uri": content}}
    return body


def _anthropic_builder(instr: str, content: Union[str, ImagePayload]) -> Dict[str, Any]:
    # Always chat-style messages, support image or text
    if isinstance(content, dict):
        # image + follow-up text
        return {
            "anthropic_version": "bedrock-2023-05-31",
            "system": "You are an expert in processing and analyzing content",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": content["mime"],
                                "data": content["b64"],
                            },
                        },
                        {"type": "text", "text": instr},
                    ],
                }
            ],
            "max_tokens": 2000,
            "temperature": 1,
            "top_p": 0.999,
        }
    else:
        # pure text
        return {
            "anthropic_version": "bedrock-2023-05-31",
            "system": "You are an expert in processing and analyzing content",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": instr + "\n\ncontent: " + content}
                    ],
                }
            ],
            "max_tokens": 2000,
            "temperature": 1,
            "top_p": 0.999,
        }


def _nova_converse_builder(
    instr: str, content: Union[str, ImagePayload]
) -> Dict[str, Any]:
    # Build content blocks according to modality
    if isinstance(content, dict):
        # Image payload
        blocks = [
            {
                "image": {
                    "format": content["mime"].split("/")[-1] or "png",
                    "source": {"bytes": content["b64"]},
                }
            },
            {"text": instr},
        ]
    else:
        # Pure text
        blocks = [{"text": instr + "\n\ncontent: " + content}]

    return {
        "schemaVersion": "messages-v1",
        "system": [{"text": "You are an expert in processing and analyzing content"}],
        "messages": [{"role": "user", "content": blocks}],
        "inferenceConfig": {"maxTokens": 2000, "temperature": 1, "topP": 0.999},
    }


def _titan_text_builder(instr: str, txt: str) -> Dict[str, Any]:
    return {
        "inputText": f"User: {instr}\nBot:",
        "textGenerationConfig": {
            "maxTokenCount": 2000,
            "temperature": 1,
            "topP": 0.999,
            "stopSequences": [],
        },
    }


def _generic_prompt_builder(instr: str, txt: str) -> Dict[str, Any]:
    return {
        "prompt": instr + "\n\ncontent: " + txt,
        "max_tokens": 2000,
        "temperature": 1,
        "top_p": 0.999,
    }


# === 2) Map model IDs to builders ===

MODEL_BODY_BUILDERS: Dict[str, Callable[..., Dict[str, Any]]] = {
    "anthropic": _anthropic_builder,
    "amazon.nova-lite": _nova_converse_builder,
    "amazon.nova-premier": _nova_converse_builder,
    "amazon.nova-pro": _nova_converse_builder,
    "titan-text-express": _titan_text_builder,
    "titan-text-lite": _titan_text_builder,
    "titan-text-premier": _titan_text_builder,
    "meta.llama3": _generic_prompt_builder,
    "meta.llama4": _generic_prompt_builder,
    "pixtral-large": _generic_prompt_builder,
    "mistral.pixtral-large": _generic_prompt_builder,
    "pegasus": _pegasus_builder,
}

# === 3) Central body‐builder ===


def build_bedrock_body(
    model_id: str, instr: str, content: Union[str, ImagePayload]
) -> str:
    """
    Chooses the correct builder based on model_id substring.
    `content` may be a plain text string or an ImagePayload dict.
    """
    lower = model_id.lower()
    for key, builder in MODEL_BODY_BUILDERS.items():
        if key in lower:
            return json.dumps(builder(instr, content))
    # fallback generic
    return json.dumps(
        _generic_prompt_builder(instr, content if isinstance(content, str) else "")
    )


# ────────────────────────────────────────────────────────────
# Utility helpers
# ────────────────────────────────────────────────────────────


def get_inference_profile_for_model(model_id: str, region_name: str = None) -> str:
    """
    Find an inference profile that wraps the given model_id.
    Returns the inferenceProfileId (or ARN) you should pass to invoke_model().
    Raises:
      - PermissionError if you can’t list or describe profiles
      - ValueError if no accessible profile contains model_id
    """
    # 1) Build the Bedrock control-plane client
    kwargs = {}
    if region_name:
        kwargs["region_name"] = region_name
    bedrock = boto3.client("bedrock", **kwargs)

    # 2) Page through list_inference_profiles
    profiles = []
    next_token = None
    try:
        while True:
            resp = bedrock.list_inference_profiles(
                maxResults=50, **({"nextToken": next_token} if next_token else {})
            )
            profiles.extend(resp.get("inferenceProfileSummaries", []))
            next_token = resp.get("nextToken")
            if not next_token:
                break
    except ClientError as e:
        logger.error("Failed to list inference profiles", exc_info=e)
        raise PermissionError("Cannot list Bedrock inference profiles") from e

    # 3) For each profile, call get_inference_profile and look for your model
    for summary in profiles:
        profile_id = summary["inferenceProfileId"]
        try:
            detail = bedrock.get_inference_profile(
                inferenceProfileIdentifier=profile_id
            )
        except ClientError as e:
            code = e.response.get("Error", {}).get("Code", "")
            if code in ("AccessDeniedException", "AccessDenied"):
                logger.error(f"No permission to get profile {profile_id}", exc_info=e)
                raise PermissionError(
                    f"No access to inference profile {profile_id}"
                ) from e
            logger.warning(f"Skipping profile {profile_id} due to error", exc_info=e)
            continue

        # detail["models"] is a list of { "modelArn": "...foundation-model/<model-id>" }
        for m in detail.get("models", []):
            arn = m.get("modelArn", "")
            if model_id in arn or arn.endswith(f"/{model_id}"):
                # Found a profile that contains your model!
                return profile_id

    # 4) Nothing found
    raise ValueError(
        f"Model '{model_id}' not found in any accessible inference profile"
    )


def _format_prompt_name_for_dynamo(prompt_name: str) -> str:
    """
    Format prompt name for DynamoDB field name.
    Converts 'summary_100' to 'Summary100' by capitalizing first letter and removing underscores.
    """
    if not prompt_name:
        return prompt_name

    # Remove underscores and capitalize first letter
    formatted = prompt_name.replace("_", "").capitalize()
    return formatted


def _strip_decimals(obj):
    if isinstance(obj, list):
        return [_strip_decimals(v) for v in obj]
    if isinstance(obj, dict):
        return {k: _strip_decimals(v) for k, v in obj.items()}
    if isinstance(obj, Decimal):
        return int(obj) if obj % 1 == 0 else float(obj)
    return obj


def parse_s3_uri(uri: str):
    p = urlparse(uri)
    if p.scheme != "s3":
        raise ValueError(f"Not an S3 URI: {uri}")
    return p.netloc, p.path.lstrip("/")


def get_file_content(s3_uri: str) -> str:
    bucket, key = parse_s3_uri(s3_uri)
    return s3.Object(bucket, key).get()["Body"].read().decode("utf-8")


def get_s3_bytes(bucket: str, key: str) -> bytes:
    return s3.Object(bucket, key).get()["Body"].read()


# ────────────────────────────────────────────────────────────
# S3-template helpers  (now fail-fast)                                ❶
# ────────────────────────────────────────────────────────────
def build_s3_templates_path(service: str, resource: str, method: str) -> Dict[str, str]:
    base = f"api_templates/{service}/{resource}/{resource}_{method}"
    return {
        "request_template": f"{base}_request.jinja",
        "request_mapping": f"{base}_request_mapping.py",
        "response_template": f"{base}_response.jinja",
        "response_mapping": f"{base}_response_mapping.py",
    }


def _load_module_from_s3(bucket: str, key: str, alias: str):
    code = s3.Object(bucket, key).get()["Body"].read().decode("utf-8")
    spec = importlib.util.spec_from_loader(alias, loader=None)
    module = importlib.util.module_from_spec(spec)
    exec(code, module.__dict__)
    return module


def create_request_body(tpl_paths, bucket, event):
    try:
        # ── Normalize payload.body ──────────────────────────────────────
        payload = event.get("payload", {})
        body = payload.get("body") or payload.get("data") or {}
        payload["body"] = body

        # ── Inject inventory_id or file_s3_uri if missing ────────────────
        if "inventory_id" not in body and "file_s3_uri" not in body:
            # Try inventory_id from assets
            assets = payload.get("assets", [])
            if assets and assets[0].get("InventoryID"):
                body["inventory_id"] = assets[0]["InventoryID"]
            else:
                # Fallback to proxy S3 URI
                data = payload.get("data", {})
                proxy = data.get("proxy")
                if proxy:
                    loc = proxy["StorageInfo"]["PrimaryLocation"]
                    bucket_name = loc.get("Bucket")
                    # path field or ObjectKey.FullPath
                    key = loc.get("path") or loc.get("ObjectKey", {}).get("FullPath")
                    if bucket_name and key:
                        body["file_s3_uri"] = f"s3://{bucket_name}/{key}"

        # Update event with our enriched payload
        event["payload"] = payload

        # ── Load and invoke the S3‑hosted mapping module ────────────────────
        mod = _load_module_from_s3(bucket, tpl_paths["request_mapping"], "req_map")
        mapping = mod.translate_event_to_request(event)

        # ── Render the Jinja request template ──────────────────────────────
        tmpl = (
            s3.Object(bucket, tpl_paths["request_template"])
            .get()["Body"]
            .read()
            .decode("utf-8")
        )
        env = Environment(loader=FileSystemLoader("/"), autoescape=True)
        rendered = env.from_string(tmpl).render(variables=mapping)

        return json.loads(rendered), mapping

    except Exception:
        logger.exception("create_request_body failed")
        raise


def create_response_output(tpl_paths, bucket, result, event, mapping):
    try:
        mod = _load_module_from_s3(bucket, tpl_paths["response_mapping"], "resp_map")
        resp_map = mod.translate_event_to_request(
            {"response_body": result, "event": event}
        )
        tmpl = (
            s3.Object(bucket, tpl_paths["response_template"])
            .get()["Body"]
            .read()
            .decode("utf-8")
        )
        env = Environment(loader=FileSystemLoader("/"), autoescape=True)
        rendered = env.from_string(tmpl).render(variables=resp_map)
        return json.loads(rendered)
    except Exception:
        logger.exception("create_response_output failed")
        raise  # ← propagate


# ────────────────────────────────────────────────────────────
# Lambda handler (all inner errors bubble up)                  ❶
# ────────────────────────────────────────────────────────────
@lambda_middleware(event_bus_name=os.getenv("EVENT_BUS_NAME", "default-event-bus"))
@logger.inject_lambda_context
@tracer.capture_lambda_handler
def lambda_handler(event, context):
    try:
        logger.info("Event received", extra={"event": event})
        bucket = os.getenv("API_TEMPLATE_BUCKET", "medialake-assets")
        tpl_paths = build_s3_templates_path("bedrock", "content_processor", "post")

        params, mapping = create_request_body(tpl_paths, bucket, event)

        asset_id = params.get("asset_id")
        file_uri = params.get("file_s3_uri")
        content_src = os.getenv("CONTENT_SOURCE")
        prompt_name = os.getenv("PROMPT_NAME")
        custom_prompt = mapping.get("custom_prompt")

        instr = (
            custom_prompt
            or DEFAULT_PROMPTS.get(prompt_name)
            or os.getenv("PROMPT", DEFAULT_PROMPTS["summary_100"])
        )

        model_id = os.getenv("MODEL_ID")
        if not model_id:
            raise KeyError("MODEL_ID environment variable is required")

        # Get model region if specified, otherwise use default AWS region
        model_region = (
            os.getenv("MODEL_REGION")
            or os.getenv("BEDROCK_REGION")
            or os.getenv("AWS_REGION")
        )

        # Create bedrock runtime client with region support
        bedrock_rt_kwargs = {}
        if model_region:
            bedrock_rt_kwargs["region_name"] = model_region
            logger.info(f"Using Bedrock region: {model_region} for model: {model_id}")
        else:
            logger.info(f"Using default region for model: {model_id}")
        bedrock_rt = boto3.client("bedrock-runtime", **bedrock_rt_kwargs)

        # ── Locate content ────────────────────────────────────────────────
        assets = event.get("payload", {}).get("assets", [])
        if not assets:
            raise ValueError("No assets found in event.payload.assets")
        asset_detail = assets[0]

        if content_src == "transcript":
            uri = (
                asset_detail.get("TranscriptionS3Uri")
                or asset_detail.get("TextS3Uri")
                or asset_detail.get("ContentS3Uri")
            )
            if not uri:
                raise ValueError("Asset has no transcript/text/content S3 URI")
            text = get_file_content(uri)
            fetched_uri = uri
            body_json = build_bedrock_body(model_id, instr, text).encode("utf-8")

        elif content_src == "proxy":
            rep = next(
                r
                for r in asset_detail["DerivedRepresentations"]
                if r["Purpose"] == "proxy"
            )
            loc = rep["StorageInfo"]["PrimaryLocation"]
            fetched_uri = f"s3://{loc['Bucket']}/{loc['ObjectKey']['FullPath']}"

            # Check if we should use S3 URI or fall back to base64
            # For TwelveLabs Pegasus, S3 bucket must be in same region as inference profile
            use_s3_uri = True

            # If model region is specified and different from bucket region, use base64
            if model_region and model_region != os.getenv("AWS_REGION", "us-east-1"):
                logger.info(
                    f"Model region {model_region} differs from default region, checking bucket region compatibility"
                )
                # For cross-region scenarios, fall back to base64 to avoid region mismatch
                try:
                    # Get bucket region
                    s3_client = boto3.client("s3")
                    bucket_location = s3_client.get_bucket_location(
                        Bucket=loc["Bucket"]
                    )
                    bucket_region = (
                        bucket_location.get("LocationConstraint") or "us-east-1"
                    )

                    if bucket_region != model_region:
                        logger.info(
                            f"Bucket region {bucket_region} differs from model region {model_region}, using base64 encoding"
                        )
                        use_s3_uri = False
                except Exception as e:
                    logger.warning(
                        f"Could not determine bucket region, falling back to base64: {e}"
                    )
                    use_s3_uri = False

            if use_s3_uri:
                # Use S3 URI approach for same-region scenarios
                # Get bucket owner - try multiple sources
                bucket_owner = (
                    loc.get("BucketOwner")
                    or os.environ.get("AWS_ACCOUNT_ID")
                    or context.invoked_function_arn.split(":")[4]
                    if context
                    else None
                )

                if not bucket_owner:
                    # Extract account ID from the event payload if available
                    try:
                        bucket_owner = event.get("payload", {}).get(
                            "account"
                        ) or event.get("account")
                    except:
                        pass

                if not bucket_owner:
                    logger.warning(
                        "Unable to determine AWS account ID, falling back to base64 encoding"
                    )
                    use_s3_uri = False
                else:
                    s3_content = {"uri": fetched_uri, "bucketOwner": bucket_owner}
                    body_json = build_bedrock_body(model_id, instr, s3_content).encode(
                        "utf-8"
                    )

            if not use_s3_uri:
                # For cross-region scenarios with large video files, we cannot use base64
                # due to Bedrock's 100MB payload limit. Raise an informative error.
                logger.error(
                    "Cannot process proxy file: S3 URI approach failed due to region mismatch or missing bucket owner"
                )
                raise RuntimeError(
                    f"Unable to process proxy video file. The TwelveLabs Pegasus model requires that "
                    f"the S3 bucket containing the video file be in the same region as the Bedrock inference profile. "
                    f"Base64 encoding is not suitable for video files due to size limitations. "
                    f"Please ensure the S3 bucket and Bedrock model are configured in the same region. "
                    f"Current model region: {model_region or 'default'}, "
                    f"S3 URI: {fetched_uri}"
                )

        elif file_uri:
            text = get_file_content(file_uri)
            fetched_uri = file_uri
            body_json = build_bedrock_body(model_id, instr, text).encode("utf-8")

        else:
            raise ValueError(f"Unsupported content source '{content_src}'")

        try:
            profile_id = get_inference_profile_for_model(
                model_id, region_name=model_region
            )
        except (PermissionError, ValueError) as e:
            logger.error("Bedrock setup error", exc_info=e)
            raise

        # ── Invoke Bedrock ────────────────────────────────────────────────
        logger.info(f"Invoking {model_id} with payload from {fetched_uri}")
        try:
            resp = bedrock_rt.invoke_model(
                modelId=profile_id, body=body_json, contentType="application/json"
            )
        except ClientError:
            logger.error(f"Bedrock invoke failed. Payload: {body_json}")
            raise  # ← propagate

        data = json.loads(resp["body"].read())
        logger.info(f"Bedrock response structure: {list(data.keys())}")

        if "anthropic" in model_id.lower():
            result = data["content"][0]["text"]
        elif "nova" in model_id.lower():
            result = (
                data.get("output", {})
                .get("message", {})
                .get("content", [{}])[0]
                .get("text", "")
            )
        elif "message" in data:
            # Pegasus (and other streaming models) return their output under "message"
            msg = data["message"]
            if isinstance(msg, dict):
                # e.g. { "content": "...", "stopReason": "..." }
                result = msg.get("content", msg.get("text", json.dumps(msg)))
            else:
                result = msg
        elif "images" in data:
            result = data["images"][0]
        else:
            result = data.get("completion", data.get("generated_text", ""))

        logger.info(f"Final extracted result length: {len(result) if result else 0}")

        # ── Persist back to DynamoDB ──────────────────────────────────────
        formatted_prompt_name = (
            _format_prompt_name_for_dynamo(prompt_name) if prompt_name else None
        )
        dynamo_key = mapping.get("dynamo_key") or (
            f"{formatted_prompt_name}Result"
            if formatted_prompt_name
            else "customPromptResult"
        )
        logger.info(
            f"DynamoDB key formatting: prompt_name='{prompt_name}' -> formatted='{formatted_prompt_name}' -> dynamo_key='{dynamo_key}'"
        )
        table.update_item(
            Key={"InventoryID": asset_id},
            UpdateExpression="SET #k = :v",
            ExpressionAttributeNames={"#k": dynamo_key},
            ExpressionAttributeValues={":v": result},
        )

        final = create_response_output(tpl_paths, bucket, data, event, mapping)
        updated = table.get_item(Key={"InventoryID": asset_id}).get("Item", {})
        final["updatedAsset"] = _strip_decimals(updated)
        return final

    except Exception:
        # Log *and* re-raise so the Lambda ends in an error state         ❶
        logger.exception("Lambda failed – propagating error to Step Functions")
        raise
