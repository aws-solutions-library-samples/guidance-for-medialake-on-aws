import boto3
import os
import json
import time
import random
import ast
import importlib.util
from datetime import datetime, timedelta
from botocore.exceptions import ClientError
from typing import Dict, Any, Optional
from jinja2 import Environment, FileSystemLoader
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext
from lambda_middleware import lambda_middleware

logger = Logger()
tracer = Tracer()
s3_client = boto3.client("s3")

DYNAMODB_TABLE_NAME = "MediaConvertEndpointsCache"
CACHE_KEY = "mediaconvert-endpoints"
CACHE_TTL_SECONDS = 3600  # 1 hour


def clean_asset_id(input_string: str) -> str:
    parts = input_string.split(":")
    uuid = parts[-1]
    if uuid == "master":
        uuid = parts[-2]
    return f"asset:uuid:{uuid}"


def load_and_execute_function_from_s3(bucket: str, key: str, function_name: str, event: dict):
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
    try:
        response = s3_client.get_object(Bucket=bucket, Key=key)
        return response["Body"].read().decode("utf-8")
    except ClientError as e:
        logger.error(f"Error downloading S3 object: {e}")
        raise


def create_request_body(s3_templates, api_template_bucket, event):
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
    """Build paths to the S3 templates for the given service, resource, and method."""
    resource_name = resource.split("/")[-1]
    file_prefix = f"{resource_name}_{method.lower()}"
    
    return {
        "request_template": f"{service_name}/{resource}/{file_prefix}_request.jinja",
        "mapping_file": f"{service_name}/{resource}/{file_prefix}_request_mapping.py",
        "response_template": f"{service_name}/{resource}/{file_prefix}_response.jinja",
        "response_mapping_file": f"{service_name}/{resource}/{file_prefix}_response_mapping.py",
    }


def get_cached_endpoint():
    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(DYNAMODB_TABLE_NAME)
    try:
        response = table.get_item(Key={"CacheKey": CACHE_KEY})
        if "Item" in response:
            item = response["Item"]
            if datetime.now() < datetime.fromisoformat(item["ExpirationTime"]):
                return item["Endpoints"]
    except Exception as e:
        logger.exception("Error retrieving cached endpoint", extra={"error": str(e)})
    return None


def update_cached_endpoint(endpoints):
    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(DYNAMODB_TABLE_NAME)
    expiration_time = datetime.now() + timedelta(seconds=CACHE_TTL_SECONDS)
    try:
        table.put_item(
            Item={
                "CacheKey": CACHE_KEY,
                "Endpoints": endpoints,
                "ExpirationTime": expiration_time.isoformat(),
            }
        )
    except Exception as e:
        logger.exception("Error updating cached endpoint", extra={"error": str(e)})


def get_mediaconvert_endpoint():
    cached_endpoints = get_cached_endpoint()
    if cached_endpoints:
        logger.info("Using cached MediaConvert endpoint")
        return cached_endpoints
    mediaconvert = boto3.client("mediaconvert", region_name="us-east-1")
    max_retries = 60
    base_delay = 1  # Start with a 1-second delay
    for attempt in range(max_retries):
        try:
            endpoints = mediaconvert.describe_endpoints()
            update_cached_endpoint(endpoints["Endpoints"][0]["Url"])
            return endpoints["Endpoints"][0]["Url"]
        except ClientError as e:
            if e.response["Error"]["Code"] == "TooManyRequestsException":
                if attempt == max_retries - 1:
                    logger.exception(
                        "Max retries reached when describing MediaConvert endpoints",
                        extra={"error": str(e)},
                    )
                    raise
                else:
                    delay = (2**attempt * base_delay) + (random.randint(0, 1000) / 1000)
                    logger.warning(f"TooManyRequests, retrying in {delay:.2f} seconds")
                    time.sleep(delay)
            else:
                logger.exception(
                    "Error describing MediaConvert endpoints", extra={"error": str(e)}
                )
                raise
    raise Exception("Failed to get MediaConvert endpoint after multiple retries")


@lambda_middleware(
    event_bus_name=os.environ.get("EVENT_BUS_NAME", "default-event-bus"),
)
@logger.inject_lambda_context
@tracer.capture_lambda_handler
def lambda_handler(event, context: LambdaContext):
    try:
        mediaconvert_queue = os.environ["MEDIACONVERT_QUEUE"]
        table_name = os.environ["MEDIALAKE_ASSET_TABLE"]
        dynamodb = boto3.resource("dynamodb")
        table = dynamodb.Table(table_name)
        api_template_bucket = os.environ.get("API_TEMPLATE_BUCKET", "medialake-assets")

        input_data = event.get("input", {}).get("DigitalSourceAsset", {})
        inventory_id = event.get("input", {}).get("InventoryID")
        clean_inventory_id = clean_asset_id(inventory_id)
        main_representation = input_data.get("MainRepresentation", {})
        master_asset_id = input_data.get("ID")
        asset_id = clean_asset_id(master_asset_id)
        storage_info = main_representation.get("StorageInfo", {})
        primary_location = storage_info.get("PrimaryLocation", {})
        bucket = primary_location.get("Bucket")
        key = primary_location.get("ObjectKey", {}).get("FullPath")

        output_bucket = event.get("output_bucket")

        if not all([key, bucket, output_bucket]):
            return {
                "externalJobResult": "Failed",
                "externalJobStatus": "Started",
                "error": "Missing required parameters"
            }

        # Build the S3 template paths
        s3_templates = build_s3_templates_path(
            service_name="mediaconvert",
            resource="audio_proxy",
            method="post"
        )

        # Add MediaConvert role ARN and queue to the event
        event["mediaconvert_role_arn"] = os.environ["MEDIACONVERT_ROLE_ARN"]
        event["mediaconvert_queue"] = mediaconvert_queue

        # Create the request body using the template
        try:
            job_settings = create_request_body(s3_templates, api_template_bucket, event)
        except Exception as e:
            logger.error(f"Error creating request body: {str(e)}")
            return {
                "externalJobResult": "Failed",
                "externalJobStatus": "Started",
                "error": f"Error creating request body: {str(e)}"
            }

        # Get MediaConvert endpoint
        mediaconvert_endpoint = get_mediaconvert_endpoint()
        mediaconvert = boto3.client("mediaconvert", endpoint_url=mediaconvert_endpoint)

        # Create the MediaConvert job
        response = mediaconvert.create_job(**job_settings)
        
        # Process the response using the template
        try:
            result = create_response_output(s3_templates, api_template_bucket, response, event)
            return result
        except Exception as e:
            logger.error(f"Error processing response: {str(e)}")
            job_id = response.get("Job", {}).get("Id", "")
            return {
                "externalJobId": job_id,
                "externalJobStatus": "Started",
                "externalJobResult": "Success" if job_id else "Failed",
                "error": f"Error processing response: {str(e)}"
            }

    except Exception as e:
        logger.exception(
            "Error processing audio",
            extra={
                "inventory_id": clean_inventory_id if 'clean_inventory_id' in locals() else None,
                "error": str(e),
                "error_type": type(e).__name__,
            },
        )
        return {
            "externalJobResult": "Failed",
            "externalJobStatus": "Started",
            "error": f"Error processing audio: {str(e)}"
        }
