import boto3
import os
import json
import time
import ast
import importlib.util
from botocore.exceptions import ClientError
from typing import Dict, Any, Optional
from jinja2 import Environment, FileSystemLoader
from aws_lambda_powertools import Logger, Tracer
from lambda_middleware import lambda_middleware

# Initialize Powertools
logger = Logger()
tracer = Tracer()

# Initialize AWS clients
transcribe_client = boto3.client('transcribe')
s3_client = boto3.client("s3")

def clean_asset_id(input_string: str) -> str:
    """
    Ensures the asset ID has the correct format without duplicates.
    Extracts just the UUID part and adds the proper prefix.
    """
    parts = input_string.split(":")
    uuid_part = parts[-1]
    if uuid_part == "master":
        uuid_part = parts[-2]
    return f"asset:uuid:{uuid_part}"


def load_and_execute_function_from_s3(bucket: str, key: str, function_name: str, event: dict):
    """
    Load and execute a function from an S3 object.
    """
    try:
        response = s3_client.get_object(Bucket=bucket, Key=f"api_templates/{key}")
        file_content = response["Body"].read().decode("utf-8")
        spec = importlib.util.spec_from_loader("dynamic_module", loader=None)
        module = importlib.util.module_from_spec(spec)
        exec(file_content, module.__dict__)
        if not hasattr(module, function_name):
            raise AttributeError(f"Function '{function_name}' not found in the downloaded file.")
        dynamic_function = getattr(module, function_name)
        result = dynamic_function(event)
        return result
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code == "NoSuchKey":
            logger.error(f"The object {key} does not exist in bucket {bucket}.")
        elif error_code == "NoSuchBucket":
            logger.error(f"The bucket {bucket} does not exist.")
        else:
            logger.error(f"An S3 error occurred: {e}")
        raise
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        raise


def download_s3_object(bucket: str, key: str) -> str:
    """
    Download an S3 object and return its content as a string.
    """
    try:
        response = s3_client.get_object(Bucket=bucket, Key=key)
        return response["Body"].read().decode("utf-8")
    except ClientError as e:
        logger.error(f"Error downloading S3 object: {e}")
        raise


def create_request_body(s3_templates, api_template_bucket, event):
    """
    Create a request body using a Jinja template and mapping function.
    """
    logger.info("Building a request body")
    function_name = "translate_event_to_request"
    request_template_path = f"api_templates/{s3_templates['request_template']}"
    mapping_path = s3_templates["mapping_file"]
    logger.info(f"{api_template_bucket} {request_template_path}")
    request_template = download_s3_object(api_template_bucket, request_template_path)
    mapping = load_and_execute_function_from_s3(api_template_bucket, mapping_path, function_name, event)
    env = Environment(loader=FileSystemLoader("/tmp/"))
    env.filters["jsonify"] = json.dumps
    query_template = env.from_string(request_template)
    request_body = query_template.render(variables=mapping)
    request_body = json.loads(request_body)
    return request_body


def create_response_output(s3_templates, api_template_bucket, response_body, event):
    """
    Create a response output using a Jinja template and mapping function.
    """
    function_name = "translate_event_to_request"
    response_template_path = f"api_templates/{s3_templates['response_template']}"
    response_mapping_path = s3_templates["response_mapping_file"]
    response_template = download_s3_object(api_template_bucket, response_template_path)
    response_mapping = load_and_execute_function_from_s3(
        api_template_bucket,
        response_mapping_path,
        function_name,
        {"response_body": response_body, "event": event}
    )
    env = Environment(loader=FileSystemLoader("/tmp/"))
    env.filters["jsonify"] = json.dumps
    query_template = env.from_string(response_template)
    response_output = query_template.render(variables=response_mapping)
    dict_output = json.loads(response_output)
    return dict_output


def build_s3_templates_path(service_name: str, resource: str, method: str) -> dict:
    """
    Build paths to the S3 templates for the given service, resource, and method.
    """
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
    try:
        logger.info("Received event", extra={"event": event})
        api_template_bucket = os.environ.get("API_TEMPLATE_BUCKET", "medialake-assets")

        # Build the S3 template paths
        s3_templates = build_s3_templates_path(
            service_name="transcribe",
            resource="transcribe",
            method="post"
        )

        # Create the request body using the template
        try:
            job_settings = create_request_body(s3_templates, api_template_bucket, event)
        except Exception as e:
            logger.error(f"Error creating request body: {str(e)}")
            return {
                "statusCode": 500,
                "body": json.dumps({"error": f"Error creating request body: {str(e)}"})
            }

        # Start the transcription job
        job = transcribe_client.start_transcription_job(**job_settings)
        
        # Process the response using the template
        try:
            result = create_response_output(s3_templates, api_template_bucket, job, event)
            return result
        except Exception as e:
            logger.error(f"Error processing response: {str(e)}")
            return {
                "statusCode": 500,
                "body": json.dumps({"error": f"Error processing response: {str(e)}"})
            }
        
    except Exception as e:
        error_message = f"Error creating transcription job: {str(e)}"
        logger.exception(error_message)
        return {
            "statusCode": 500,
            "body": json.dumps({"error": error_message})
        }
