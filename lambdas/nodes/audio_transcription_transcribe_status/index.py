import datetime
import importlib.util
import json
import os
import re
from decimal import Decimal

import boto3
from aws_lambda_powertools import Logger, Tracer
from botocore.exceptions import ClientError
from jinja2 import Environment, FileSystemLoader
from lambda_middleware import lambda_middleware

# Initialize Powertools
logger = Logger()
tracer = Tracer()

# Initialize AWS clients
s3 = boto3.resource("s3")
s3_client = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")
transcribe_client = boto3.client("transcribe")


def _strip_decimals(obj):
    if isinstance(obj, list):
        return [_strip_decimals(v) for v in obj]
    if isinstance(obj, dict):
        return {k: _strip_decimals(v) for k, v in obj.items()}
    if isinstance(obj, Decimal):
        return int(obj) if obj % 1 == 0 else float(obj)
    return obj


class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal) or isinstance(obj, datetime.datetime):
            return str(obj)
        return super().default(obj)


def http_to_s3_comps(url: str):
    regex = (
        r"^https:\/\/s3\.(?:[a-z0-9-]{4,})\.amazonaws\.com\/([a-z0-9-\.]{1,})\/(.*)$"
    )
    matches = re.finditer(regex, url, re.MULTILINE)
    for match in matches:
        return match.group(1), match.group(2)
    raise ValueError(f"Invalid S3 URL format: {url}")


def read_json_from_s3(bucket, key):
    obj = s3.Object(bucket, key)
    return json.loads(obj.get()["Body"].read().decode("utf-8"))


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
                f"Function '{function_name}' not found in the downloaded file."
            )
        return getattr(module, function_name)(event)
    except ClientError as e:
        logger.error(f"S3 error occurred: {e}", exc_info=True)
        raise
    except Exception as e:
        logger.error(f"Unexpected error during function execution: {e}", exc_info=True)
        raise


def download_s3_object(bucket: str, key: str) -> str:
    try:
        response = s3_client.get_object(Bucket=bucket, Key=key)
        return response["Body"].read().decode("utf-8")
    except ClientError as e:
        logger.error(f"Error downloading S3 object: {e}", exc_info=True)
        raise


def create_request_body(s3_templates, api_template_bucket, event):
    logger.info("Building a request body")
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
    request_body = query_template.render(variables=mapping)
    return json.loads(request_body), mapping


def create_response_output(
    s3_templates, api_template_bucket, response_body, event, mapping=None
):
    function_name = "translate_event_to_request"
    response_template_path = f"api_templates/{s3_templates['response_template']}"
    response_mapping_path = s3_templates["response_mapping_file"]
    response_template = download_s3_object(api_template_bucket, response_template_path)

    event_data = {"response_body": response_body, "event": event}
    if mapping:
        event_data["mapping"] = mapping

    response_mapping = load_and_execute_function_from_s3(
        api_template_bucket, response_mapping_path, function_name, event_data
    )
    env = Environment(loader=FileSystemLoader("/tmp/"))
    env.filters["jsonify"] = json.dumps
    query_template = env.from_string(response_template)
    response_output = query_template.render(variables=response_mapping)
    return json.loads(response_output)


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
        service_name="transcribe", resource="transcribe_status", method="get"
    )

    request_params, mapping = create_request_body(
        s3_templates, api_template_bucket, event
    )
    logger.info(
        "Successfully created request params", extra={"request_params": request_params}
    )

    job_name = request_params.get("TranscriptionJobName")
    if not job_name:
        raise ValueError("TranscriptionJobName is missing in request parameters")

    logger.info(f"Getting transcription job status for job: {job_name}")
    status = transcribe_client.get_transcription_job(TranscriptionJobName=job_name)
    logger.info(
        "Retrieved transcription job status",
        extra={"job_status": status["TranscriptionJob"]["TranscriptionJobStatus"]},
    )

    status_value = status["TranscriptionJob"]["TranscriptionJobStatus"]
    updated_item = {}

    if status_value == "COMPLETED":
        data_block = event.get("payload", {}).get("data", {})
        body = data_block.get("body", {})
        if isinstance(body, str):
            body = json.loads(body)
        inventory_id = body.get("inventory_id")
        if not inventory_id:
            raise ValueError("Missing inventory_id in event payload")

        transcript_uri = status["TranscriptionJob"]["Transcript"]["TranscriptFileUri"]
        bucket, s3_key = http_to_s3_comps(transcript_uri)

        table = dynamodb.Table(os.getenv("MEDIALAKE_ASSET_TABLE"))
        table.update_item(
            Key={"InventoryID": inventory_id},
            UpdateExpression="SET TranscriptionS3Uri = :val",
            ExpressionAttributeValues={":val": f"s3://{bucket}/{s3_key}"},
        )

        json_content = read_json_from_s3(bucket, s3_key)
        status["transcript_content"] = json_content["results"]["transcripts"][0][
            "transcript"
        ]

        updated_item = table.get_item(Key={"InventoryID": inventory_id}).get("Item", {})

    logger.info("Creating response output")
    result = create_response_output(
        s3_templates, api_template_bucket, status, event, mapping
    )

    if updated_item:
        result["updatedAsset"] = _strip_decimals(updated_item)

    logger.info("Successfully created response output")
    return result
