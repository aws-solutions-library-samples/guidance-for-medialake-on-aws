import json
import os
import random
import time
from decimal import Decimal
from typing import Any, Callable, Dict, Union
from urllib.parse import urlparse

import boto3
from aws_lambda_powertools import Logger, Tracer
from botocore.exceptions import ClientError
from lambda_middleware import lambda_middleware

# ────────────────────────────────────────────────────────────
# Powertools & AWS clients
# ────────────────────────────────────────────────────────────
logger = Logger()
tracer = Tracer()

s3 = boto3.resource("s3")
bedrock_rt = boto3.client("bedrock-runtime")
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
}


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


def _twelvelabs_pegasus_builder(
    instr: str, content: Union[str, Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Builder for TwelveLabs Pegasus model.
    Requires inputPrompt and mediaSource with S3 URI and bucketOwner.
    """
    if isinstance(content, dict) and "s3_uri" in content:
        # Get AWS account ID from STS
        import boto3

        sts = boto3.client("sts")
        account_id = sts.get_caller_identity()["Account"]

        return {
            "inputPrompt": instr,
            "mediaSource": {
                "s3Location": {"uri": content["s3_uri"], "bucketOwner": account_id}
            },
        }
    else:
        raise ValueError(
            "TwelveLabs Pegasus requires content dict with 's3_uri' field, "
            f"got: {type(content)}"
        )


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
    "twelvelabs.pegasus": _twelvelabs_pegasus_builder,
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


def estimate_tokens(text: str) -> int:
    """
    Rough token estimation (1 token ≈ 4 characters).
    This is a conservative estimate that works across most models.
    """
    return len(text) // 4


def validate_input_size(text: str, model_id: str, max_tokens: int = 100000):
    """
    Validate input doesn't exceed model limits.

    Args:
        text: The input text to validate
        model_id: The Bedrock model ID
        max_tokens: Maximum allowed tokens (default: 100K)

    Raises:
        ValueError: If input exceeds token limit
    """
    estimated_tokens = estimate_tokens(text)

    if estimated_tokens > max_tokens:
        raise ValueError(
            f"Input too large: {estimated_tokens} tokens (max: {max_tokens}). "
            f"Text length: {len(text)} characters. "
            f"Consider chunking or reducing input size."
        )

    logger.info(f"Input validation passed: {estimated_tokens}/{max_tokens} tokens")
    return estimated_tokens


def chunk_text(text: str, max_tokens: int = 50000) -> list:
    """
    Split text into chunks that fit within token limits.

    Args:
        text: The text to chunk
        max_tokens: Maximum tokens per chunk (default: 50K to leave room for prompt)

    Returns:
        List of text chunks
    """
    max_chars = max_tokens * 4
    chunks = []

    for i in range(0, len(text), max_chars):
        chunk = text[i : i + max_chars]
        chunks.append(chunk)

    logger.info(f"Split text into {len(chunks)} chunks")
    return chunks


def summarize_chunks(
    chunks: list, model_id: str, instr: str, bedrock_client, profile_id: str
) -> str:
    """
    Summarize each chunk and combine results.

    Args:
        chunks: List of text chunks to summarize
        model_id: Bedrock model ID
        instr: The instruction/prompt
        bedrock_client: Bedrock runtime client
        profile_id: Inference profile ID

    Returns:
        Combined summary of all chunks
    """
    summaries = []

    for i, chunk in enumerate(chunks):
        logger.info(f"Processing chunk {i+1}/{len(chunks)}")
        body_json = build_bedrock_body(model_id, instr, chunk).encode("utf-8")

        resp = invoke_bedrock_with_retry(
            bedrock_client, profile_id, body_json, "application/json"
        )
        data = json.loads(resp["body"].read())

        if "anthropic" in model_id.lower():
            summary = data["content"][0]["text"]
        elif "nova" in model_id.lower():
            summary = data["output"]["message"]["content"][0]["text"]
        elif "titan" in model_id.lower():
            summary = data["results"][0]["outputText"]
        else:
            summary = str(data)

        summaries.append(summary)

    if len(summaries) > 1:
        combined = "\n\n".join(summaries)
        final_instr = (
            "Combine these summaries into a single coherent summary. "
            "Maintain the key points and overall structure:\n\n" + combined
        )

        logger.info("Creating final combined summary")
        body_json = build_bedrock_body(model_id, final_instr, "").encode("utf-8")
        resp = invoke_bedrock_with_retry(
            bedrock_client, profile_id, body_json, "application/json"
        )
        data = json.loads(resp["body"].read())

        if "anthropic" in model_id.lower():
            return data["content"][0]["text"]
        elif "nova" in model_id.lower():
            return data["output"]["message"]["content"][0]["text"]
        elif "titan" in model_id.lower():
            return data["results"][0]["outputText"]
        else:
            return str(data)

    return summaries[0]


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
    exec(
        code, module.__dict__
    )  # nosec B102 - Controlled execution of trusted S3 templates
    return module


def create_request_body(tpl_paths, bucket, event):
    try:
        mod = _load_module_from_s3(bucket, tpl_paths["request_mapping"], "req_map")
        mapping = mod.translate_event_to_request(event)
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
        raise  # ← propagate


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
# Retry mechanism for Bedrock API calls
# ────────────────────────────────────────────────────────────


def invoke_bedrock_with_retry(
    bedrock_client,
    model_id: str,
    body: bytes,
    content_type: str = "application/json",
    max_retries: int = 50,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
):
    """
    Invoke Bedrock model with exponential backoff retry for throttling exceptions.

    Args:
        bedrock_client: The Bedrock runtime client
        model_id: The model ID to invoke
        body: The request body as bytes
        content_type: Content type for the request
        max_retries: Maximum number of retry attempts (default: 50)
        base_delay: Base delay in seconds for exponential backoff
        max_delay: Maximum delay in seconds between retries

    Returns:
        The response from Bedrock invoke_model

    Raises:
        ClientError: If all retries are exhausted or for non-throttling errors
    """
    for attempt in range(max_retries + 1):
        try:
            logger.info(f"Bedrock invoke attempt {attempt + 1}/{max_retries + 1}")
            response = bedrock_client.invoke_model(
                modelId=model_id, body=body, contentType=content_type
            )
            logger.info(f"Bedrock invoke succeeded on attempt {attempt + 1}")
            return response

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")

            # Check if this is a throttling error
            if error_code in [
                "ThrottlingException",
                "TooManyRequestsException",
                "ServiceQuotaExceededException",
            ]:
                if attempt < max_retries:
                    # Calculate delay with exponential backoff and jitter
                    delay = min(base_delay * (2**attempt), max_delay)
                    jitter = random.uniform(0, delay * 0.1)  # Add up to 10% jitter
                    total_delay = delay + jitter

                    logger.warning(
                        f"Bedrock throttling on attempt {attempt + 1}: {error_code}. "
                        f"Retrying in {total_delay:.2f} seconds..."
                    )
                    time.sleep(total_delay)
                    continue
                else:
                    logger.error(
                        f"Bedrock throttling: exhausted all {max_retries + 1} attempts. "
                        f"Final error: {error_code}"
                    )
                    raise
            else:
                # Non-throttling error, don't retry
                logger.error(f"Bedrock non-throttling error: {error_code}")
                raise
        except Exception as e:
            # Non-ClientError exceptions, don't retry
            logger.error(f"Bedrock unexpected error: {type(e).__name__}: {e}")
            raise

    # This should never be reached, but just in case
    raise RuntimeError("Unexpected end of retry loop")


# ────────────────────────────────────────────────────────────
# Lambda handler (all inner errors bubble up)                  ❶
# ────────────────────────────────────────────────────────────
@lambda_middleware(event_bus_name=os.getenv("EVENT_BUS_NAME", "default-event-bus"))
@logger.inject_lambda_context
@tracer.capture_lambda_handler
def lambda_handler(event, context):
    try:
        logger.info("Event received", extra={"event": event})

        # Extract parameters directly from event without S3 mapping files
        content_src = os.getenv("CONTENT_SOURCE", "proxy")
        prompt_name = os.getenv("PROMPT_NAME")
        model_id = os.getenv("MODEL_ID")

        if not model_id:
            raise KeyError("MODEL_ID environment variable is required")

        # Get instruction/prompt
        instr = DEFAULT_PROMPTS.get(prompt_name) or os.getenv(
            "PROMPT", DEFAULT_PROMPTS["summary_100"]
        )

        # ── Locate content ────────────────────────────────────────────────
        payload = event.get("payload", {})
        assets = payload.get("assets", [])
        if not assets:
            raise ValueError("No assets found in event.payload.assets")
        asset_detail = assets[0]

        # Extract asset_id from the asset
        asset_id = asset_detail.get("InventoryID")
        if not asset_id:
            raise ValueError("No InventoryID found in asset")

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
            logger.info(f"Loaded transcript from {uri}, length: {len(text)} chars")

            try:
                estimated_tokens = validate_input_size(
                    text, model_id, max_tokens=100000
                )
                body_json = build_bedrock_body(model_id, instr, text).encode("utf-8")
                use_chunking = False
            except ValueError as e:
                logger.warning(f"Input too large: {e}. Using chunking strategy.")
                use_chunking = True
                body_json = None

        elif content_src == "proxy":
            rep = next(
                r
                for r in asset_detail["DerivedRepresentations"]
                if r["Purpose"] == "proxy"
            )
            loc = rep["StorageInfo"]["PrimaryLocation"]
            fetched_uri = f"s3://{loc['Bucket']}/{loc['ObjectKey']['FullPath']}"

            # For TwelveLabs models, pass S3 URI directly instead of base64
            body_json = build_bedrock_body(
                model_id, instr, {"s3_uri": fetched_uri}
            ).encode("utf-8")
            use_chunking = False

        elif file_uri:
            text = get_file_content(file_uri)
            fetched_uri = file_uri
            logger.info(f"Loaded file from {file_uri}, length: {len(text)} chars")

            try:
                estimated_tokens = validate_input_size(
                    text, model_id, max_tokens=100000
                )
                body_json = build_bedrock_body(model_id, instr, text).encode("utf-8")
                use_chunking = False
            except ValueError as e:
                logger.warning(f"Input too large: {e}. Using chunking strategy.")
                use_chunking = True
                body_json = None

        else:
            raise ValueError(f"Unsupported content source '{content_src}'")

        try:
            profile_id = get_inference_profile_for_model(
                model_id, region_name=os.getenv("AWS_REGION")
            )
        except (PermissionError, ValueError) as e:
            logger.error("Bedrock setup error", exc_info=e)
            raise

        # ── Invoke Bedrock ────────────────────────────────────────────────
        logger.info(f"Invoking {model_id} with payload from {fetched_uri}")

        if use_chunking:
            logger.info("Using chunking strategy for large content")
            chunks = chunk_text(text, max_tokens=50000)
            result = summarize_chunks(chunks, model_id, instr, bedrock_rt, profile_id)
            logger.info(
                f"Chunked processing complete. Final result length: {len(result)}"
            )

            data = {"result": result, "chunked": True, "num_chunks": len(chunks)}
        else:
            try:
                resp = invoke_bedrock_with_retry(
                    bedrock_rt, profile_id, body_json, "application/json"
                )
            except ClientError as e:
                error_code = e.response.get("Error", {}).get("Code", "")
                if error_code == "ValidationException" and "token" in str(e).lower():
                    logger.warning(
                        "Token limit exceeded despite validation. Falling back to chunking."
                    )
                    chunks = chunk_text(text, max_tokens=50000)
                    result = summarize_chunks(
                        chunks, model_id, instr, bedrock_rt, profile_id
                    )
                    logger.info(
                        f"Fallback chunking complete. Final result length: {len(result)}"
                    )
                    data = {
                        "result": result,
                        "chunked": True,
                        "num_chunks": len(chunks),
                    }
                else:
                    logger.error(f"Bedrock invoke failed after retries. Error: {e}")
                    raise

            if not use_chunking:
                data = json.loads(resp["body"].read())
                logger.info(f"Bedrock response structure: {list(data.keys())}")

                # Extract result from Bedrock response
                if "anthropic" in model_id.lower():
                    result = data["content"][0]["text"]
                elif "twelvelabs" in model_id.lower() and "pegasus" in model_id.lower():
                    # TwelveLabs Pegasus returns message as a direct string
                    result = data.get("message", "")
                    logger.info(
                        f"TwelveLabs Pegasus result extraction: {result[:100]}..."
                        if result
                        else "TwelveLabs Pegasus result is empty"
                    )
                elif "nova" in model_id.lower():
                    result = (
                        data.get("output", {})
                        .get("message", {})
                        .get("content", [{}])[0]
                        .get("text", "")
                    )
                    logger.info(
                        f"Nova result extraction: {result[:100]}..."
                        if result
                        else "Nova result is empty"
                    )
                elif "images" in data:
                    result = data["images"][0]
                else:
                    result = data.get("completion", data.get("generated_text", ""))

                logger.info(
                    f"Final extracted result length: {len(result) if result else 0}"
                )

        # ── Persist back to DynamoDB ──────────────────────────────────────
        formatted_prompt_name = (
            _format_prompt_name_for_dynamo(prompt_name) if prompt_name else None
        )
        dynamo_key = (
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

        # Return response directly without S3 template mapping
        updated = table.get_item(Key={"InventoryID": asset_id}).get("Item", {})
        return {
            "statusCode": 200,
            "body": {
                "result": result,
                "model_id": model_id,
                "prompt_name": prompt_name,
                "content_source": content_src,
                "asset_id": asset_id,
            },
            "updatedAsset": _strip_decimals(updated),
            "metadata": event.get("metadata", {}),
            "payload": event.get("payload", {}),
        }

    except Exception:
        # Log *and* re-raise so the Lambda ends in an error state         ❶
        logger.exception("Lambda failed – propagating error to Step Functions")
        raise
