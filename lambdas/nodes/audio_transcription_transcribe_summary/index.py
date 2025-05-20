import boto3
import os
import json
import datetime
import ast
import importlib.util
from aws_lambda_powertools import Logger, Tracer
from lambda_middleware import lambda_middleware
from decimal import Decimal
from typing import Dict, Any
from botocore.exceptions import ClientError
from urllib.parse import urlparse
from jinja2 import Environment, FileSystemLoader

# Initialize Powertools
logger = Logger()
tracer = Tracer()

# Default prompts moved into index.py
DEFAULT_PROMPTS = {
    "summary_100": (
        "**You are a media-asset-management specialist.**\n"
        "The following is an **audio transcript from a media file** "
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
        "• **Setting & Context** – Where is it and what’s happening?\n"
        "• **Colors & Textures** – Key visual attributes.\n"
        "• **Relationships & Actions** – How elements interact.\n"
        "Use language suitable for accessibility and metadata tagging."
    ),
    # Add more prompts here...
}

# Initialize AWS clients
s3 = boto3.resource('s3')
s3_client = boto3.client('s3')
bedrock_runtime_client = boto3.client("bedrock-runtime")
dynamodb = boto3.resource('dynamodb')

table = dynamodb.Table(os.environ["MEDIALAKE_ASSET_TABLE"])

class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal) or isinstance(obj, datetime.datetime):
            return str(obj)
        return super().default(obj)

# ... other helper functions unchanged ...

@lambda_middleware(
    event_bus_name=os.environ.get("EVENT_BUS_NAME", "default-event-bus"),
)
@logger.inject_lambda_context
@tracer.capture_lambda_handler
def lambda_handler(event, context):
    try:
        logger.info("Received event", extra={"event": event})
        api_template_bucket = os.environ.get("API_TEMPLATE_BUCKET", "medialake-assets")

        # Build the S3 template paths
        s3_templates = build_s3_templates_path(
            service_name="transcribe",
            resource="transcribe_summary",
            method="post"
        )

        # Create the request body using the template (now only includes asset_id)
        try:
            request_params, mapping = create_request_body(s3_templates, api_template_bucket, event)
        except Exception as e:
            logger.error(f"Error creating request body: {str(e)}")
            return {
                "statusCode": 500,
                "body": json.dumps({"error": f"Error creating request body: {str(e)}"})
            }

        # Extract the asset ID
        asset_id = request_params.get("asset_id")

        # Determine the prompt
        custom_prompt = mapping.get("custom_prompt")
        prompt_name = mapping.get("prompt_name")
        if custom_prompt:
            summary_instructions = custom_prompt
        elif prompt_name and prompt_name in DEFAULT_PROMPTS:
            summary_instructions = DEFAULT_PROMPTS[prompt_name]
        else:
            summary_instructions = os.environ.get("PROMPT", "")

        # Determine the model ID
        bedrock_model_id = os.environ.get("MODEL_ID")
        if not bedrock_model_id:
            raise KeyError("Environment variable MODEL_ID is not set")

        # Fetch asset details and transcript as before
        asset_details = get_asset_details(asset_id)
        if "TranscriptionS3Uri" not in asset_details:
            error_response = {
                "statusCode": 404,
                "body": {"message": "Asset transcript not found"},
                "status": "FAILED"
            }
            return create_response_output(s3_templates, api_template_bucket, error_response, event, mapping)

        transcript_full = get_asset_transcript(asset_details["TranscriptionS3Uri"])
        transcript = json.dumps(transcript_full['results']['transcripts'][0]['transcript'])

        # Build Bedrock request
        messages = [{
            "role": "user",
            "content": [{"text": summary_instructions + "\n\ntranscript: " + transcript}]
        }]

        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 2000,
            "messages": messages,
            "system": "You are an expert in summarizing audio transcription",
            "temperature": 1,
            "top_p": 0.999
        })

        logger.info(f'Invoking model: {bedrock_model_id}')
        response = bedrock_runtime_client.invoke_model(body=body, modelId=bedrock_model_id)
        assistant_response = json.loads(response.get('body').read())

        # Save summary and update DynamoDB as before
        _bucket, _key = parse_s3_uri(asset_details["TranscriptionS3Uri"])
        summary_base_path = os.path.splitext(_key)[0]
        summary_file_name = f"{summary_base_path}-summary.txt"
        s3_client.put_object(
            Bucket=_bucket,
            Key=summary_file_name,
            Body=assistant_response['content'][0]['text'],
            ContentType='text/plain'
        )
        table.update_item(
            Key={"InventoryID": asset_id},
            UpdateExpression="SET TranscriptionSummaryS3Uri = :val",
            ExpressionAttributeValues={":val": f"s3://{_bucket}/{summary_file_name}"}
        )

        result = {
            "summary_s3_uri": f"s3://{_bucket}/{summary_file_name}",
            "status": "SUCCEEDED"
        }
        try:
            final_response = create_response_output(s3_templates, api_template_bucket, result, event, mapping)
            return final_response
        except Exception as e:
            logger.error(f"Error processing response: {str(e)}")
            return {
                "statusCode": 500,
                "body": json.dumps({"error": f"Error processing response: {str(e)}"})
            }

    except Exception as e:
        error_message = f"Error processing transcription summary: {str(e)}"
        logger.exception(error_message)
        return {
            "statusCode": 500,
            "body": json.dumps({"error": error_message})
        }