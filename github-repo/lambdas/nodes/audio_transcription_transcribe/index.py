import importlib.util
import json
import os
import re

import boto3
from aws_lambda_powertools import Logger, Tracer
from botocore.exceptions import ClientError
from jinja2 import Environment, FileSystemLoader
from lambda_middleware import lambda_middleware

# Initialize Powertools
logger = Logger()
tracer = Tracer()

# Initialize AWS clients
transcribe_client = boto3.client("transcribe")
s3_client = boto3.client("s3")


def clean_asset_id(input_string: str) -> str:
    parts = input_string.split(":")
    uuid_part = parts[-1]
    if uuid_part == "master":
        uuid_part = parts[-2]
    return f"asset:uuid:{uuid_part}"


def sanitize_job_name(name: str) -> str:
    """Sanitize job name to fit AWS requirements."""
    sanitized = re.sub(r"[^a-zA-Z0-9._-]", "_", name)
    return sanitized[:200]


def load_and_execute_function_from_s3(
    bucket: str, key: str, function_name: str, event: dict
):
    try:
        response = s3_client.get_object(Bucket=bucket, Key=f"api_templates/{key}")
        file_content = response["Body"].read().decode("utf-8")
        spec = importlib.util.spec_from_loader("dynamic_module", loader=None)
        module = importlib.util.module_from_spec(spec)
        exec(file_content, module.__dict__)
        if not hasattr(module, function_name):
            raise AttributeError(
                f"Function '{function_name}' not found in downloaded file."
            )
        return getattr(module, function_name)(event)
    except ClientError as e:
        logger.error(f"S3 error: {e}", exc_info=True)
        raise
    except Exception as e:
        logger.error(
            f"Unexpected error during dynamic function load: {e}", exc_info=True
        )
        raise


def download_s3_object(bucket: str, key: str) -> str:
    try:
        response = s3_client.get_object(Bucket=bucket, Key=key)
        return response["Body"].read().decode("utf-8")
    except ClientError as e:
        logger.error(f"Error downloading S3 object: {e}", exc_info=True)
        raise


def create_request_body(s3_templates, api_template_bucket, event):
    logger.info("Building request body")
    function_name = "translate_event_to_request"
    request_template_path = f"api_templates/{s3_templates['request_template']}"
    mapping_path = s3_templates["mapping_file"]
    request_template = download_s3_object(api_template_bucket, request_template_path)
    mapping = load_and_execute_function_from_s3(
        api_template_bucket, mapping_path, function_name, event
    )
    env = Environment(loader=FileSystemLoader("/tmp/"))
    env.filters["jsonify"] = json.dumps
    query_template = env.from_string(request_template)
    request_body = json.loads(query_template.render(variables=mapping))

    # Sanitize job name if present
    if "TranscriptionJobName" in request_body:
        request_body["TranscriptionJobName"] = sanitize_job_name(
            request_body["TranscriptionJobName"]
        )

    return request_body


def create_response_output(s3_templates, api_template_bucket, response_body, event):
    function_name = "translate_event_to_request"
    response_template_path = f"api_templates/{s3_templates['response_template']}"
    response_mapping_path = s3_templates["response_mapping_file"]
    response_template = download_s3_object(api_template_bucket, response_template_path)
    response_mapping = load_and_execute_function_from_s3(
        api_template_bucket,
        response_mapping_path,
        function_name,
        {"response_body": response_body, "event": event},
    )
    env = Environment(loader=FileSystemLoader("/tmp/"))
    env.filters["jsonify"] = json.dumps
    query_template = env.from_string(response_template)
    return json.loads(query_template.render(variables=response_mapping))


def build_s3_templates_path(service_name: str, resource: str, method: str) -> dict:
    resource_name = resource.split("/")[-1]
    file_prefix = f"{resource_name}_{method.lower()}"
    return {
        "request_template": f"{service_name}/{resource}/{file_prefix}_request.jinja",
        "mapping_file": f"{service_name}/{resource}/{file_prefix}_request_mapping.py",
        "response_template": f"{service_name}/{resource}/{file_prefix}_response.jinja",
        "response_mapping_file": f"{service_name}/{resource}/{file_prefix}_response_mapping.py",
    }


@lambda_middleware(
    event_bus_name=os.environ.get("EVENT_BUS_NAME", "default-event-bus"),
)
@logger.inject_lambda_context
@tracer.capture_lambda_handler
def lambda_handler(event, context):
    logger.info("Received event", extra={"event": event})
    api_template_bucket = os.environ.get("API_TEMPLATE_BUCKET", "medialake-assets")

    s3_templates = build_s3_templates_path(
        service_name="transcribe", resource="transcribe", method="post"
    )

    # Create request body
    job_settings = create_request_body(s3_templates, api_template_bucket, event)
    logger.info("Created job settings", extra={"job_settings": job_settings})

    # Debugging key fields
    logger.info(
        "Critical job fields",
        extra={
            "TranscriptionJobName": job_settings.get("TranscriptionJobName", ""),
            "MediaFileUri": job_settings.get("Media", {}).get("MediaFileUri", ""),
            "MediaFormat": job_settings.get("MediaFormat", ""),
            "OutputBucketName": job_settings.get("OutputBucketName", ""),
            "OutputKey": job_settings.get("OutputKey", ""),
            "DataAccessRoleArn": job_settings.get("JobExecutionSettings", {}).get(
                "DataAccessRoleArn", ""
            ),
        },
    )

    # Start transcription job
    try:
        job = transcribe_client.start_transcription_job(**job_settings)
    except Exception as e:
        logger.error("Failed to start transcription job", exc_info=True)
        raise RuntimeError("Transcription job submission failed") from e

    # Process and return response
    result = create_response_output(s3_templates, api_template_bucket, job, event)
    return result
