import json
import os
import random
import time
from decimal import Decimal
from typing import Any, Callable, Dict, Optional, Union
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


def sanitize_prompt_label(label: str) -> str:
    """
    Convert user-friendly label to DynamoDB-safe key.

    Examples:
        "Marketing Summary" → "MarketingSummary"
        "Security-Analysis_2024" → "SecurityAnalysis2024"
        "My Custom Prompt #1" → "MyCustomPrompt1"

    Rules:
        - Remove all non-alphanumeric characters except underscores
        - Remove leading/trailing whitespace
        - Capitalize first letter of each word
        - Max length: 50 characters
        - Must start with letter

    Args:
        label: User-provided friendly label

    Returns:
        Sanitized label safe for DynamoDB field name

    Raises:
        ValueError: If label is empty or doesn't start with a letter after sanitization
    """
    import re

    if not label:
        raise ValueError("Prompt label cannot be empty")

    # Remove leading/trailing whitespace
    label = label.strip()

    # Replace spaces with nothing, capitalize words
    words = label.split()
    camel_case = "".join(word.capitalize() for word in words)

    # Remove all non-alphanumeric characters except underscores
    sanitized = re.sub(r"[^a-zA-Z0-9_]", "", camel_case)

    # Ensure starts with letter
    if not sanitized or not sanitized[0].isalpha():
        raise ValueError(
            f"Prompt label must start with a letter: '{label}'. "
            f"After sanitization, got: '{sanitized}'"
        )

    # Truncate to max length
    sanitized = sanitized[:50]

    logger.info(f"Sanitized prompt label: '{label}' → '{sanitized}'")
    return sanitized


def generate_default_label() -> str:
    """
    Generate a default label when user doesn't provide one.

    Format: CustomPrompt_YYYYMMDD_HHMMSS

    Returns:
        Timestamp-based default label
    """
    from datetime import datetime

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    default_label = f"CustomPrompt_{timestamp}"
    logger.info(f"Generated default prompt label: {default_label}")
    return default_label


def check_key_exists(table, asset_id: str, key_name: str) -> tuple:
    """
    Check if a DynamoDB key already exists for the asset.

    IMPORTANT: This check is ASSET-SCOPED, not pipeline-scoped.
    If ANY pipeline has already written a result with this label,
    it will be detected regardless of which pipeline is currently running.

    This is the CORRECT behavior because:
    1. Asset results should not have duplicate labels (confusing to users)
    2. Labels are meant to be meaningful identifiers, not pipeline-specific
    3. If different pipelines need different analyses, use different labels

    Args:
        table: DynamoDB table resource
        asset_id: Asset InventoryID
        key_name: The field name to check

    Returns:
        tuple: (exists: bool, existing_data: dict or None)
               - exists: True if key exists and has a value
               - existing_data: The existing result data if found, None otherwise
    """
    try:
        response = table.get_item(
            Key={"InventoryID": asset_id}, ProjectionExpression=key_name
        )
        item = response.get("Item", {})

        if key_name in item and item[key_name] is not None:
            existing_data = item[key_name]
            logger.info(f"Key '{key_name}' exists for asset {asset_id}")
            return True, existing_data

        logger.info(f"Key '{key_name}' does not exist for asset {asset_id}")
        return False, None

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "")
        if error_code == "ValidationException":
            # Key doesn't exist in schema - this is expected for first use
            logger.info(f"Key '{key_name}' not found in schema (first use)")
            return False, None
        # Re-raise other errors
        logger.error(f"Error checking key existence: {e}")
        raise


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
# Prompt Configuration Extraction
# ────────────────────────────────────────────────────────────


def get_parameter_value(env_vars: Dict[str, str], param_name: str) -> Optional[str]:
    """
    Get parameter value from environment variables or local filesystem.

    This function implements the global pattern for retrieving parameter values:
    1. First checks for {PARAM_NAME}_FILE_PATH environment variable
    2. If file path exists, reads the content from the local file
    3. Otherwise, falls back to reading {PARAM_NAME} directly from env vars

    Args:
        env_vars: Dictionary of environment variables
        param_name: Name of the parameter to retrieve (e.g., 'CUSTOM_PROMPT_TEXT')

    Returns:
        Parameter value as string, or None if not found

    Example:
        value = get_parameter_value(os.environ, 'CUSTOM_PROMPT_TEXT')
        # Will check for CUSTOM_PROMPT_TEXT_FILE_PATH first, then CUSTOM_PROMPT_TEXT
    """
    file_path_key = f"{param_name}_FILE_PATH"

    # Check if parameter is stored as a file in the Lambda deployment package
    if file_path_key in env_vars:
        file_path = env_vars[file_path_key]
        logger.info(
            f"Parameter '{param_name}' stored in file, reading from: {file_path}"
        )

        try:
            # Read from local filesystem
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            logger.info(
                f"Successfully read '{param_name}' from file (size: {len(content)} bytes)"
            )
            return content
        except Exception as e:
            logger.error(
                f"Failed to read '{param_name}' from file at {file_path}: {e}. "
                f"Falling back to direct env var if available."
            )
            # Fall through to check direct env var

    # Check for direct environment variable
    if param_name in env_vars:
        value = env_vars[param_name]
        logger.info(
            f"Parameter '{param_name}' found in environment variables "
            f"(size: {len(value)} bytes)"
        )
        return value

    # Parameter not found
    logger.debug(
        f"Parameter '{param_name}' not found in environment variables or filesystem"
    )
    return None


def extract_prompt_configuration(env_vars: Dict[str, str]) -> Dict[str, Any]:
    """
    Extract and resolve prompt configuration based on prompt_source.

    Supports both new prompt_source structure and legacy parameters for backward compatibility.
    Automatically handles parameters stored in Lambda deployment package files.

    New Structure (preferred):
        - PROMPT_SOURCE: 'default', 'saved', or 'custom'
        - SAVED_PROMPT_NAME: name of pre-canned prompt (when prompt_source='saved')
        - CUSTOM_PROMPT_TEXT or CUSTOM_PROMPT_TEXT_FILE_PATH: user-provided prompt text
        - CUSTOM_PROMPT_LABEL: user-provided label (when prompt_source='custom')

    Legacy Structure (backward compatible):
        - PROMPT_NAME: name of pre-canned prompt
        - CUSTOM_PROMPT or CUSTOM_PROMPT_FILE_PATH: user-provided prompt text
        - PROMPT_LABEL: user-provided label

    Returns:
        {
            'prompt_text': str,      # The actual prompt to use
            'prompt_source': str,    # 'default', 'saved', or 'custom'
            'prompt_label': str,     # Label for DynamoDB storage
            'prompt_name': str,      # Name of prompt (if using saved)
        }

    Raises:
        ValueError: If configuration is invalid or required fields are missing
    """
    # Try new structure first
    prompt_source = env_vars.get("PROMPT_SOURCE")

    if prompt_source:
        logger.info(f"Using new prompt_source structure: {prompt_source}")

        if prompt_source == "default":
            return {
                "prompt_text": DEFAULT_PROMPTS["summary_100"],
                "prompt_source": "default",
                "prompt_label": "Summary100",
                "prompt_name": "summary_100",
            }

        elif prompt_source == "saved":
            saved_prompt_name = env_vars.get("SAVED_PROMPT_NAME")
            if not saved_prompt_name:
                raise ValueError(
                    "SAVED_PROMPT_NAME required when PROMPT_SOURCE is 'saved'"
                )

            if saved_prompt_name not in DEFAULT_PROMPTS:
                raise ValueError(f"Unknown saved prompt: {saved_prompt_name}")

            return {
                "prompt_text": DEFAULT_PROMPTS[saved_prompt_name],
                "prompt_source": "saved",
                "prompt_label": _format_prompt_name_for_dynamo(saved_prompt_name),
                "prompt_name": saved_prompt_name,
            }

        elif prompt_source == "custom":
            # Use the new get_parameter_value function to check file path first
            custom_prompt_text = get_parameter_value(env_vars, "CUSTOM_PROMPT_TEXT")
            custom_prompt_label = env_vars.get("CUSTOM_PROMPT_LABEL")

            if not custom_prompt_text:
                raise ValueError(
                    "CUSTOM_PROMPT_TEXT (or CUSTOM_PROMPT_TEXT_FILE_PATH) required when PROMPT_SOURCE is 'custom'"
                )

            if not custom_prompt_label:
                custom_prompt_label = generate_default_label()
                logger.info(
                    f"No custom label provided, generated: {custom_prompt_label}"
                )

            # Sanitize the label
            sanitized_label = sanitize_prompt_label(custom_prompt_label)

            return {
                "prompt_text": custom_prompt_text.strip(),
                "prompt_source": "custom",
                "prompt_label": sanitized_label,
                "prompt_name": None,
            }

        else:
            raise ValueError(
                f"Invalid PROMPT_SOURCE: {prompt_source}. Must be 'default', 'saved', or 'custom'"
            )

    else:
        # Fall back to legacy structure for backward compatibility
        logger.info("PROMPT_SOURCE not found, using legacy parameter structure")

        # Use get_parameter_value for backward compatibility with file storage
        custom_prompt = get_parameter_value(env_vars, "CUSTOM_PROMPT")
        prompt_name = env_vars.get("PROMPT_NAME")
        prompt_label = env_vars.get("PROMPT_LABEL")

        # Custom prompt takes precedence (legacy behavior)
        if custom_prompt:
            if not prompt_label:
                prompt_label = generate_default_label()
                logger.info(f"No label provided, generated default: {prompt_label}")

            sanitized_label = sanitize_prompt_label(prompt_label)

            return {
                "prompt_text": custom_prompt.strip(),
                "prompt_source": "custom",
                "prompt_label": sanitized_label,
                "prompt_name": None,
            }

        # Saved/pre-canned prompt
        elif prompt_name and prompt_name in DEFAULT_PROMPTS:
            return {
                "prompt_text": DEFAULT_PROMPTS[prompt_name],
                "prompt_source": "saved",
                "prompt_label": _format_prompt_name_for_dynamo(prompt_name),
                "prompt_name": prompt_name,
            }

        # Default fallback
        else:
            # Check for PROMPT env var as absolute fallback
            fallback_prompt = env_vars.get("PROMPT")
            if fallback_prompt:
                return {
                    "prompt_text": fallback_prompt,
                    "prompt_source": "default",
                    "prompt_label": "Summary100",
                    "prompt_name": "summary_100",
                }
            else:
                return {
                    "prompt_text": DEFAULT_PROMPTS["summary_100"],
                    "prompt_source": "default",
                    "prompt_label": "Summary100",
                    "prompt_name": "summary_100",
                }


# ────────────────────────────────────────────────────────────
@lambda_middleware(event_bus_name=os.getenv("EVENT_BUS_NAME", "default-event-bus"))
@logger.inject_lambda_context
@tracer.capture_lambda_handler
def lambda_handler(event, context):
    try:
        logger.info("Event received", extra={"event": event})

        # ═══════════════════════════════════════════════════════════════════
        # PHASE 1: EARLY VALIDATION (Fast, No Cost)
        # Extract parameters and validate BEFORE expensive operations
        # ═══════════════════════════════════════════════════════════════════

        content_src = os.getenv("CONTENT_SOURCE", "proxy")

        # Determine which model_id to use based on content source
        if content_src == "transcript":
            model_id = os.getenv("MODEL_ID_TEXT")
            if not model_id:
                raise KeyError(
                    "MODEL_ID_TEXT environment variable is required when CONTENT_SOURCE is 'transcript'"
                )
        elif content_src == "proxy":
            model_id = os.getenv("MODEL_ID_MEDIA")
            if not model_id:
                raise KeyError(
                    "MODEL_ID_MEDIA environment variable is required when CONTENT_SOURCE is 'proxy'"
                )
        else:
            # Fallback to legacy MODEL_ID for backward compatibility
            model_id = os.getenv("MODEL_ID")
            if not model_id:
                raise KeyError(
                    f"MODEL_ID environment variable is required for content source '{content_src}'"
                )

        logger.info(f"Using model_id: {model_id} for content_source: {content_src}")

        # Get asset_id early for validation
        payload = event.get("payload", {})
        assets = payload.get("assets", [])
        if not assets:
            raise ValueError("No assets found in event.payload.assets")
        asset_detail = assets[0]

        asset_id = asset_detail.get("InventoryID")
        if not asset_id:
            raise ValueError("No InventoryID found in asset")

        # ═══════════════════════════════════════════════════════════════════
        # PHASE 2: PROMPT CONFIGURATION (Supports new + legacy structure)
        # Extract and validate prompt configuration
        # ═══════════════════════════════════════════════════════════════════

        try:
            prompt_config = extract_prompt_configuration(dict(os.environ))
            instr = prompt_config["prompt_text"]
            prompt_source = prompt_config["prompt_source"]
            prompt_label = prompt_config["prompt_label"]
            prompt_name = prompt_config["prompt_name"]

            logger.info(
                f"Prompt configuration: source={prompt_source}, label={prompt_label}"
            )
        except ValueError as e:
            logger.error(f"Invalid prompt configuration: {e}")
            raise

        # ═══════════════════════════════════════════════════════════════════
        # PHASE 3: LABEL VALIDATION (Fast DynamoDB Read, Minimal Cost)
        # Must happen BEFORE content processing and Bedrock invocation!
        # This prevents wasting money on Bedrock calls that will fail later.
        # ═══════════════════════════════════════════════════════════════════

        # Build DynamoDB key based on prompt type
        if prompt_source == "custom":
            dynamo_key = f"BedrockPrompt_{prompt_label}"

            # CHECK IF KEY EXISTS - Critical validation before expensive operations!
            exists, existing_data = check_key_exists(table, asset_id, dynamo_key)

            if exists:
                # Fail fast with detailed error - BEFORE spending money on Bedrock
                pipeline_name = (
                    event.get("metadata", {})
                    .get("execution", {})
                    .get("Name", "Unknown")
                )
                previous_pipeline = (
                    existing_data.get("pipeline_name", "Unknown")
                    if isinstance(existing_data, dict)
                    else "Unknown"
                )
                previous_timestamp = (
                    existing_data.get("timestamp", "Unknown")
                    if isinstance(existing_data, dict)
                    else "Unknown"
                )
                previous_model = (
                    existing_data.get("model_id", "Unknown")
                    if isinstance(existing_data, dict)
                    else "Unknown"
                )

                error_msg = (
                    f"Label Conflict: A Bedrock result with label '{prompt_label}' already exists on this asset.\n\n"
                    f"Existing Result Details:\n"
                    f"  - Created by pipeline: {previous_pipeline}\n"
                    f"  - Timestamp: {previous_timestamp}\n"
                    f"  - Model: {previous_model}\n\n"
                    f"Current Pipeline: {pipeline_name}\n\n"
                    f"Solutions:\n"
                    f"  1. Use a more specific label (e.g., '{prompt_label} - {pipeline_name}')\n"
                    f"  2. Delete the existing result if it should be replaced\n"
                    f"  3. Choose a different prompt label\n\n"
                    f"Note: This validation prevented wasting costs on a Bedrock API call that would not be stored."
                )
                logger.error(error_msg)
                raise ValueError(error_msg)

            logger.info(
                f"Label validation passed: '{prompt_label}' is available for asset {asset_id}"
            )
        else:
            # Saved or default prompts use standard key format
            dynamo_key = f"{prompt_label}Result"
            logger.info(f"Using standard DynamoDB key: {dynamo_key}")
            dynamo_key = "Summary100Result"
            logger.info("Using default prompt: summary_100")

        # ═══════════════════════════════════════════════════════════════════
        # PHASE 3: CONTENT PROCESSING (Expensive - S3 reads, processing)
        # Only reached if validation passed!
        # ═══════════════════════════════════════════════════════════════════

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
        from datetime import datetime

        # Get original prompt label (before sanitization) from environment
        original_prompt_label = os.getenv("CUSTOM_PROMPT_LABEL", "")
        if not original_prompt_label and prompt_source == "custom":
            original_prompt_label = prompt_label
        elif prompt_source in ["saved", "default"]:
            # For saved prompts, create a user-friendly label
            if prompt_name == "summary_100":
                original_prompt_label = "Summary 100"
            elif prompt_name:
                # Convert snake_case to Title Case
                original_prompt_label = prompt_name.replace("_", " ").title()
            else:
                original_prompt_label = prompt_label

        # Build result data with metadata
        result_data = {
            "result": result,
            "model_id": model_id,
            "timestamp": datetime.utcnow().isoformat(),
            "content_source": content_src,
            "prompt_label": original_prompt_label,  # Store ORIGINAL label, not sanitized
        }

        # Add prompt-specific metadata
        if prompt_source == "custom":
            result_data["prompt_type"] = "custom"
            result_data["prompt_preview"] = instr[:200]  # First 200 chars of prompt
            result_data["pipeline_name"] = (
                event.get("metadata", {}).get("execution", {}).get("Name", "Unknown")
            )
            result_data["pipeline_execution_id"] = (
                event.get("metadata", {}).get("execution", {}).get("Id")
            )
            logger.info(
                f"Storing custom prompt result with label: {original_prompt_label}"
            )
        elif prompt_source in ["saved", "default"]:
            result_data["prompt_type"] = prompt_source
            if prompt_name:
                result_data["prompt_name"] = prompt_name
            logger.info(f"Storing {prompt_source} prompt result: {prompt_name}")

        # Store in Metadata.Descriptive.[PROMPTKEY] structure
        descriptive_key = prompt_label  # Use sanitized version for key
        logger.info(f"Storing result at Metadata.Descriptive.{descriptive_key}")

        # Try to set the nested value directly
        # If parent paths don't exist, DynamoDB will fail with ValidationException
        # In that case, create the entire structure at once
        try:
            table.update_item(
                Key={"InventoryID": asset_id},
                UpdateExpression="SET Metadata.Descriptive.#k = :v",
                ExpressionAttributeNames={"#k": descriptive_key},
                ExpressionAttributeValues={":v": result_data},
            )
            logger.info(
                "Successfully stored result in existing Metadata.Descriptive structure"
            )
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            if (
                error_code == "ValidationException"
                and "document path" in str(e).lower()
            ):
                # Parent path doesn't exist, create the entire structure
                logger.info(
                    "Parent paths don't exist, creating Metadata.Descriptive structure"
                )
                table.update_item(
                    Key={"InventoryID": asset_id},
                    UpdateExpression="SET Metadata.Descriptive = :desc",
                    ExpressionAttributeValues={":desc": {descriptive_key: result_data}},
                )
                logger.info(
                    "Successfully created Metadata.Descriptive structure with result"
                )
            else:
                # Re-raise other errors
                logger.error(f"Unexpected error storing result: {e}")
                raise

        # Return response directly without S3 template mapping
        updated = table.get_item(Key={"InventoryID": asset_id}).get("Item", {})
        return {
            "statusCode": 200,
            "body": {
                "result": result,
                "model_id": model_id,
                "prompt_source": prompt_source,
                "prompt_label": original_prompt_label,
                "prompt_name": (
                    prompt_name if prompt_source in ["saved", "default"] else None
                ),
                "dynamo_key": f"Metadata.Descriptive.{descriptive_key}",
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
