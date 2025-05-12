import boto3
import os
import json
import datetime
import base64
import mimetypes
import importlib.util
from urllib.parse import urlparse
from decimal import Decimal
from typing import Any, Callable, Dict, Union
from botocore.exceptions import ClientError

from aws_lambda_powertools import Logger, Tracer
from lambda_middleware import lambda_middleware
from jinja2 import Environment, FileSystemLoader

# Initialize Powertools
logger = Logger()
tracer = Tracer()


ImagePayload = Dict[str, str]

def get_s3_bytes(bucket: str, key: str) -> bytes:
    return s3.Object(bucket, key).get()["Body"].read()

# Default prompts
DEFAULT_PROMPTS = {
    "summary_100": (
        "**You are a media-asset-management specialist.**\n"
        "The following is a **content from a media file** "
        "(podcast, feature film, corporate video, etc.). In **100 words "
        "or less**, distill its **content**, emphasizing:\n"
        "1. **Core Topic or Theme**\n"
        "2. **Key Messages & Insights**\n"
        "3. **Major Arguments or Plot Points**\n"
        "4. **Tone & Style**\n"
        "Use concise, industry-standard terminology so a MAM user can "
        "immediately grasp the essence of the content."
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
    )
}

def _anthropic_builder(
    instr: str,
    content: Union[str, ImagePayload]
) -> Dict[str, Any]:
    # Always chat-style messages, support image or text
    if isinstance(content, dict):
        # image + follow-up text
        return {
            "anthropic_version": "bedrock-2023-05-31",
            "system": "You are an expert in processing and analyzing content",
            "messages": [{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": content["mime"],
                            "data": content["b64"]
                        }
                    },
                    {
                        "type": "text",
                        "text": instr
                    }
                ]
            }],
            "max_tokens": 2000,
            "temperature": 1,
            "top_p": 0.999
        }
    else:
        # pure text
        return {
            "anthropic_version": "bedrock-2023-05-31",
            "system": "You are an expert in processing and analyzing content",
            "messages": [{
                "role": "user",
                "content": [
                    { "type": "text", "text": instr + "\n\ncontent: " + content }
                ]
            }],
            "max_tokens": 2000,
            "temperature": 1,
            "top_p": 0.999
        }

def _nova_converse_builder(instr: str, content: Union[str, ImagePayload]) -> Dict[str, Any]:
    # Build content blocks according to modality
    if isinstance(content, dict):
        # Image payload
        blocks = [
            {
                "image": {
                    "format": content["mime"].split("/")[-1] or "png",
                    "source": {"bytes": content["b64"]}
                }
            },
            { "text": instr }
        ]
    else:
        # Pure text
        blocks = [{ "text": instr + "\n\ncontent: " + content }]

    return {
        "schemaVersion": "messages-v1",
        "system": [
            { "text": "You are an expert in processing and analyzing content" }
        ],
        "messages": [
            { "role": "user", "content": blocks }
        ],
        "inferenceConfig": {
            "maxTokens": 2000,
            "temperature": 1,
            "topP": 0.999
        }
    }



def _titan_text_builder(instr: str, txt: str) -> Dict[str, Any]:
    return {
        "inputText": f"User: {instr}\nBot:",
        "textGenerationConfig": {
            "maxTokenCount": 2000,
            "temperature": 1,
            "topP": 0.999,
            "stopSequences": []
        }
    }

def _generic_prompt_builder(instr: str, txt: str) -> Dict[str, Any]:
    return {
        "prompt": instr + "\n\ncontent: " + txt,
        "max_tokens": 2000,
        "temperature": 1,
        "top_p": 0.999
    }

# === 2) Map model IDs to builders ===

MODEL_BODY_BUILDERS: Dict[str, Callable[..., Dict[str, Any]]] = {
    "anthropic":            _anthropic_builder,
    "amazon.nova-lite":     _nova_converse_builder,
    "amazon.nova-premier":  _nova_converse_builder,
    "amazon.nova-pro":      _nova_converse_builder,
    "titan-text-express":   _titan_text_builder,
    "titan-text-lite":      _titan_text_builder,
    "titan-text-premier":   _titan_text_builder,
    "meta.llama3":          _generic_prompt_builder,
    "meta.llama4":          _generic_prompt_builder,
    "pixtral-large":        _generic_prompt_builder,
    "mistral.pixtral-large":_generic_prompt_builder,
}

# === 3) Central body‐builder ===

def build_bedrock_body(
    model_id: str,
    instr: str,
    content: Union[str, ImagePayload]
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
    return json.dumps(_generic_prompt_builder(instr, content if isinstance(content, str) else ""))



def _strip_decimals(obj):
    """Recursively convert Decimal → int/float so JSON serialization works."""
    if isinstance(obj, list):
        return [_strip_decimals(v) for v in obj]
    if isinstance(obj, dict):
        return {k: _strip_decimals(v) for k, v in obj.items()}
    if isinstance(obj, Decimal):
        return int(obj) if obj % 1 == 0 else float(obj)
    return obj

# Initialize AWS clients
s3 = boto3.resource("s3")
s3_client = boto3.client("s3")
bedrock_runtime_client = boto3.client("bedrock-runtime")
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["MEDIALAKE_ASSET_TABLE"])

class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (Decimal, datetime.datetime)):
            return str(obj)
        return super().default(obj)

def parse_s3_uri(s3_uri: str):
    parsed = urlparse(s3_uri)
    if parsed.scheme != "s3":
        raise ValueError(f"Not an S3 URI: {s3_uri}")
    return parsed.netloc, parsed.path.lstrip("/")

def get_asset_details(asset_id: str) -> Dict[str, Any]:
    try:
        resp = table.get_item(Key={"InventoryID": asset_id})
        return resp.get("Item", {})
    except ClientError as e:
        logger.error(f"Error getting asset details: {e}")
        raise

def get_file_content(s3_uri: str) -> str:
    bucket, key = parse_s3_uri(s3_uri)
    obj = s3.Object(bucket, key)
    return obj.get()["Body"].read().decode("utf-8")

def build_s3_templates_path(service_name: str, resource: str, method: str) -> Dict[str, str]:
    base = f"api_templates/{service_name}/{resource}/{resource}_{method}"
    return {
        "request_template":   f"{base}_request.jinja",
        "request_mapping":    f"{base}_request_mapping.py",
        "response_template":  f"{base}_response.jinja",
        "response_mapping":   f"{base}_response_mapping.py",
    }

def create_request_body(s3_templates, bucket_name: str, event: dict):

    request_mapping_obj = s3.Object(bucket_name, s3_templates["request_mapping"])
    code = request_mapping_obj.get()["Body"].read().decode("utf-8")
    spec = importlib.util.spec_from_loader("rm", loader=None)
    mod = importlib.util.module_from_spec(spec)
    exec(code, mod.__dict__)
    mapping = mod.translate_event_to_request(event)
    tmpl_obj = s3.Object(bucket_name, s3_templates["request_template"])
    tmpl = tmpl_obj.get()["Body"].read().decode("utf-8")
    env = Environment(
        loader=FileSystemLoader("/"),
        autoescape=True
    )
    rendered = env.from_string(tmpl).render(variables=mapping)
    return json.loads(rendered), mapping

def create_response_output(s3_templates, bucket_name: str, result: dict, event: dict, mapping: dict):

    resp_map_obj = s3.Object(bucket_name, s3_templates["response_mapping"])
    code = resp_map_obj.get()["Body"].read().decode("utf-8")
    spec = importlib.util.spec_from_loader("rm2", loader=None)
    mod = importlib.util.module_from_spec(spec)
    exec(code, mod.__dict__)
    resp_mapping = mod.translate_event_to_request({"response_body": result, "event": event})
    tmpl_obj = s3.Object(bucket_name, s3_templates["response_template"])
    tmpl = tmpl_obj.get()["Body"].read().decode("utf-8")
    env = Environment(
        loader=FileSystemLoader("/"),
        autoescape=True
    )
    rendered = env.from_string(tmpl).render(variables=resp_mapping)
    return json.loads(rendered)

def get_content_from_asset(asset_details: dict, content_source: str):
    source_map = {
        "transcript": "TranscriptionS3Uri",
        "proxy":      "ProxyS3Uri",
        "metadata":   "MetadataS3Uri",
    }
    uri = asset_details.get(source_map.get(content_source, ""), None)
    if not uri:
        for fld in ["TranscriptionS3Uri","TextS3Uri","ContentS3Uri","ProxyS3Uri","MetadataS3Uri"]:
            if fld in asset_details:
                uri = asset_details[fld]
                break
    if not uri:
        raise ValueError(f"No content for source '{content_source}'")
    return get_file_content(uri), uri



@lambda_middleware(event_bus_name=os.environ.get("EVENT_BUS_NAME","default-event-bus"))
@logger.inject_lambda_context
@tracer.capture_lambda_handler
def lambda_handler(event, context):
    try:
        logger.info("Event received", extra={"event": event})
        bucket = os.environ.get("API_TEMPLATE_BUCKET","medialake-assets")
        s3_templates = build_s3_templates_path("bedrock","content_processor","post")

        # build request & mapping
        try:
            params, mapping = create_request_body(s3_templates, bucket, event)
        except Exception as e:
            logger.error(f"Request body error: {e}")
            return {"statusCode":500, "body":json.dumps({"error":str(e)})}

        asset_id      = params.get("asset_id")
        file_uri      = params.get("file_s3_uri")
        
        content_src   = os.environ.get("CONTENT_SOURCE")
        custom_prompt = mapping.get("custom_prompt")
        prompt_name   = os.environ.get("PROMPT_NAME")

        # choose instructions
        if custom_prompt:
            instr = custom_prompt
        elif prompt_name in DEFAULT_PROMPTS:
            instr = DEFAULT_PROMPTS[prompt_name]
        else:
            instr = os.environ.get("PROMPT",DEFAULT_PROMPTS["summary_100"])

        # choose model
        model_id =  os.environ.get("MODEL_ID")
        if not model_id:
            raise KeyError("Model ID missing")

        # ── fetch content ────────────────────────────────────────────────
        assets = event.get("payload", {}).get("assets", [])
        if not assets:
            raise ValueError("No assets found in event.payload.assets")

        asset_detail = assets[0]

        if content_src == "transcript":
            transcript_uri = (
                asset_detail.get("TranscriptionS3Uri")
                or asset_detail.get("TextS3Uri")
                or asset_detail.get("ContentS3Uri")
            )
            text = get_file_content(transcript_uri)
            fetched_uri = transcript_uri
            body_json = build_bedrock_body(model_id, instr, text)

        elif content_src == "proxy":
            rep = next(r for r in asset_detail["DerivedRepresentations"] if r["Purpose"]=="proxy")
            loc = rep["StorageInfo"]["PrimaryLocation"]
            raw = get_s3_bytes(loc["Bucket"], loc["ObjectKey"]["FullPath"])
            b64  = base64.b64encode(raw).decode("utf-8")
            mime = mimetypes.guess_type(loc["ObjectKey"]["FullPath"])[0] or "application/octet-stream"

            # record where it came from
            fetched_uri = f"s3://{loc['Bucket']}/{loc['ObjectKey']['FullPath']}"

            body_json = build_bedrock_body(model_id, instr, {"b64": b64, "mime": mime})

        elif file_uri:
            text = get_file_content(file_uri)
            fetched_uri = file_uri
            body_json = build_bedrock_body(model_id, instr, text)

        else:
            raise ValueError(f"Unsupported content source '{content_src}'")

        # ── now invoke ──────────────────────────────────────────────────────────────
        logger.info(f"Invoking {model_id} with payload from {fetched_uri}")

      
        try:
            resp = bedrock_runtime_client.invoke_model(
                modelId=model_id,
                body=body_json,
                contentType="application/json"
            )
        except ClientError as e:
            # dump again at error
            logger.error(f"InvokeModel failed for model {model_id}. Payload was: {body_json}")
            raise

        # parse response
        data = json.loads(resp["body"].read())
        if "anthropic" in model_id.lower():
            result = data["content"][0]["text"]
        elif "images" in data:
            result = data["images"][0]
        else:
            result = data.get("completion", data.get("generated_text",""))

        # ── persist ───────────────────────────────────────────────────────────
        if mapping.get("dynamo_key"):
            dynamo_key = mapping["dynamo_key"]
        elif prompt_name:
            dynamo_key = f"{prompt_name}Result"
        else:
            dynamo_key = "customPromptResult"

        update_expr      = "SET #k = :t"
        expr_attr_names  = {"#k": dynamo_key}
        expr_attr_values = {":t": result}

        table.update_item(
            Key={"InventoryID": asset_id},
            UpdateExpression=update_expr,
            ExpressionAttributeNames=expr_attr_names,
            ExpressionAttributeValues=expr_attr_values
        )

        # respond
        final = create_response_output(
            s3_templates,
            bucket,
            data,        # <-- raw JSON from Bedrock invoke_model
            event,
            mapping
        )

        updated_item = table.get_item(Key={"InventoryID": asset_id}).get("Item", {})
        final["updatedAsset"] = _strip_decimals(updated_item)

        return final

    except Exception as e:
        logger.exception("Processing failed")
        return {"statusCode":500, "body":json.dumps({"error":str(e)})}
