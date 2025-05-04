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

def parse_s3_uri(s3_uri):
    """Parse an S3 URI into bucket and key."""
    parsed = urlparse(s3_uri)
    if parsed.scheme != 's3':
        raise ValueError(f"Not an S3 URI: {s3_uri}")
    bucket = parsed.netloc
    key = parsed.path.lstrip('/')
    return bucket, key

def get_asset_details(asset_id):
    """Get asset details from DynamoDB."""
    try:
        response = table.get_item(Key={"InventoryID": asset_id})
        return response.get("Item", {})
    except Exception as e:
        logger.error(f"Error getting asset details: {str(e)}")
        raise

def get_file_content(s3_uri):
    """Get file content from S3."""
    try:
        bucket, key = parse_s3_uri(s3_uri)
        obj = s3.Object(bucket, key)
        content = obj.get()['Body'].read().decode('utf-8')
        return content
    except Exception as e:
        logger.error(f"Error getting file content: {str(e)}")
        raise

def build_s3_templates_path(service_name, resource, method):
    """Build S3 template paths."""
    return {
        "request_template": f"api_templates/{service_name}/{resource}/{resource}_{method}_request.jinja",
        "request_mapping": f"api_templates/{service_name}/{resource}/{resource}_{method}_request_mapping.py",
        "response_template": f"api_templates/{service_name}/{resource}/{resource}_{method}_response.jinja",
        "response_mapping": f"api_templates/{service_name}/{resource}/{resource}_{method}_response_mapping.py",
    }

def create_request_body(s3_templates, api_template_bucket, event):
    """Create request body using templates."""
    try:
        # Get the request mapping module
        request_mapping_obj = s3.Object(api_template_bucket, s3_templates["request_mapping"])
        request_mapping_code = request_mapping_obj.get()['Body'].read().decode('utf-8')
        
        # Create a module from the code
        spec = importlib.util.spec_from_loader('request_mapping', loader=None)
        request_mapping_module = importlib.util.module_from_spec(spec)
        exec(request_mapping_code, request_mapping_module.__dict__)
        
        # Call the translate_event_to_request function
        mapping = request_mapping_module.translate_event_to_request(event)
        
        # Get the request template
        request_template_obj = s3.Object(api_template_bucket, s3_templates["request_template"])
        request_template = request_template_obj.get()['Body'].read().decode('utf-8')
        
        # Render the template
        env = Environment(loader=FileSystemLoader('/'))
        template = env.from_string(request_template)
        rendered_template = template.render(variables=mapping)
        
        # Parse the rendered template
        request_params = json.loads(rendered_template)
        
        return request_params, mapping
    except Exception as e:
        logger.error(f"Error creating request body: {str(e)}")
        raise

def create_response_output(s3_templates, api_template_bucket, result, event, mapping):
    """Create response output using templates."""
    try:
        # Get the response mapping module
        response_mapping_obj = s3.Object(api_template_bucket, s3_templates["response_mapping"])
        response_mapping_code = response_mapping_obj.get()['Body'].read().decode('utf-8')
        
        # Create a module from the code
        spec = importlib.util.spec_from_loader('response_mapping', loader=None)
        response_mapping_module = importlib.util.module_from_spec(spec)
        exec(response_mapping_code, response_mapping_module.__dict__)
        
        # Call the translate_event_to_request function with the result and event
        response_mapping = response_mapping_module.translate_event_to_request({
            "response_body": result,
            "event": event
        })
        
        # Get the response template
        response_template_obj = s3.Object(api_template_bucket, s3_templates["response_template"])
        response_template = response_template_obj.get()['Body'].read().decode('utf-8')
        
        # Render the template
        env = Environment(loader=FileSystemLoader('/'))
        template = env.from_string(response_template)
        rendered_template = template.render(variables=response_mapping)
        
        # Parse the rendered template
        response_output = json.loads(rendered_template)
        
        return response_output
    except Exception as e:
        logger.error(f"Error creating response output: {str(e)}")
        raise

def get_content_from_asset(asset_details, content_source):
    """Get content from asset based on content source."""
    content_uri = None
    
    # Map content_source to asset field
    source_field_mapping = {
        "transcript": "TranscriptionS3Uri",
        "proxy": "ProxyS3Uri",
        "metadata": "MetadataS3Uri",
    }
    
    # Try to get the content URI based on content_source
    if content_source in source_field_mapping:
        field = source_field_mapping[content_source]
        if field in asset_details:
            content_uri = asset_details[field]
    
    # If content_source is custom or the specified field doesn't exist,
    # try to find content in common fields
    if not content_uri:
        for field in ["TranscriptionS3Uri", "TextS3Uri", "ContentS3Uri", "ProxyS3Uri", "MetadataS3Uri"]:
            if field in asset_details:
                content_uri = asset_details[field]
                break
    
    if not content_uri:
        raise ValueError(f"No content found for source '{content_source}'")
    
    # Get the content from S3
    content = get_file_content(content_uri)
    
    return content, content_uri

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
            service_name="bedrock",
            resource="content_processor",
            method="post"
        )

        # Create the request body using the template
        try:
            request_params, mapping = create_request_body(s3_templates, api_template_bucket, event)
        except Exception as e:
            logger.error(f"Error creating request body: {str(e)}")
            return {
                "statusCode": 500,
                "body": json.dumps({"error": f"Error creating request body: {str(e)}"})
            }

        # Extract parameters
        asset_id = request_params.get("asset_id")
        file_s3_uri = request_params.get("file_s3_uri")
        content_source = mapping.get("content_source", "transcript")

        # Determine the prompt
        custom_prompt = mapping.get("custom_prompt")
        prompt_name = mapping.get("prompt_name")
        if custom_prompt:
            processing_instructions = custom_prompt
        elif prompt_name and prompt_name in DEFAULT_PROMPTS:
            processing_instructions = DEFAULT_PROMPTS[prompt_name]
        else:
            processing_instructions = os.environ.get("PROMPT", DEFAULT_PROMPTS["summary_100"])

        # Determine the model ID
        bedrock_model_id = mapping.get("model_id") or os.environ.get("MODEL_ID")
        if not bedrock_model_id:
            raise KeyError("Model ID not provided and environment variable MODEL_ID is not set")

        # Get file content
        if file_s3_uri:
            # Use the provided file URI directly
            content = get_file_content(file_s3_uri)
            source_s3_uri = file_s3_uri
        else:
            # Fetch asset details
            asset_details = get_asset_details(asset_id)
            
            # Get content based on content_source
            try:
                content, source_s3_uri = get_content_from_asset(asset_details, content_source)
            except ValueError as e:
                error_response = {
                    "statusCode": 404,
                    "body": {"message": str(e)},
                    "status": "FAILED"
                }
                return create_response_output(s3_templates, api_template_bucket, error_response, event, mapping)

        # Build Bedrock request based on model
        if "anthropic" in bedrock_model_id.lower():
            # Anthropic Claude models
            messages = [{
                "role": "user",
                "content": [{"text": processing_instructions + "\n\ncontent: " + content}]
            }]
            
            body = json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 2000,
                "messages": messages,
                "system": "You are an expert in processing and analyzing content",
                "temperature": 1,
                "top_p": 0.999
            })
        else:
            # Generic format for other models (can be expanded for specific models)
            body = json.dumps({
                "prompt": processing_instructions + "\n\ncontent: " + content,
                "max_tokens": 2000,
                "temperature": 1,
                "top_p": 0.999
            })

        # Invoke Bedrock model
        logger.info(f'Invoking model: {bedrock_model_id}')
        response = bedrock_runtime_client.invoke_model(body=body, modelId=bedrock_model_id)
        
        # Parse response based on model
        if "anthropic" in bedrock_model_id.lower():
            assistant_response = json.loads(response.get('body').read())
            result_text = assistant_response['content'][0]['text']
        else:
            # Generic response parsing (can be expanded for specific models)
            response_body = json.loads(response.get('body').read())
            result_text = response_body.get('completion', response_body.get('generated_text', ''))

        # Store result directly in DynamoDB in the TranscriptSummary field
        table.update_item(
            Key={"InventoryID": asset_id},
            UpdateExpression="SET TranscriptSummary = :val",
            ExpressionAttributeValues={":val": result_text}
        )

        # Prepare result
        result = {
            "result": result_text,
            "status": "SUCCEEDED"
        }
        
        # Create response
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
        error_message = f"Error processing content with Bedrock: {str(e)}"
        logger.exception(error_message)
        return {
            "statusCode": 500,
            "body": json.dumps({"error": error_message})
        }