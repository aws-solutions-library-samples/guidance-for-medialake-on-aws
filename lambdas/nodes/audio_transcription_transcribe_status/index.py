import boto3
import os
import json
import time
import datetime
import ast
import importlib.util
import re
from botocore.exceptions import ClientError
from typing import Dict, Any, Optional
from jinja2 import Environment, FileSystemLoader
from aws_lambda_powertools import Logger, Tracer
from lambda_middleware import lambda_middleware
from nodes_utils import format_duration
from decimal import Decimal

# Initialize Powertools
logger = Logger()
tracer = Tracer()

# Initialize AWS clients
s3 = boto3.resource('s3')
s3_client = boto3.client("s3")
dynamodb = boto3.resource('dynamodb')
transcribe_client = boto3.client('transcribe')

class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal) or isinstance(obj, datetime.datetime):
            return str(obj)
        return super().default(obj)


def http_to_s3_comps(url: str):
    regex = r"^https:\/\/s3\.(?:[a-z0-9-]{4,})\.amazonaws\.com\/([a-z0-9-\.]{1,})\/(.*)$"

    matches = re.finditer(regex, url, re.MULTILINE)

    for matchNum, match in enumerate(matches, start=1):
        
        groups = match.groups()

        bucket = match.group(1)
        s3_key = match.group(2)
        
        return bucket, s3_key


def read_json_from_s3(bucket, key):
    obj = s3.Object(bucket, key)
    return json.loads(obj.get()['Body'].read().decode('utf-8'))


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
    return request_body, mapping


def create_response_output(s3_templates, api_template_bucket, response_body, event, mapping=None):
    """
    Create a response output using a Jinja template and mapping function.
    """
    function_name = "translate_event_to_request"
    response_template_path = f"api_templates/{s3_templates['response_template']}"
    response_mapping_path = s3_templates["response_mapping_file"]
    response_template = download_s3_object(api_template_bucket, response_template_path)
    
    # Include the mapping from the request in the event data for the response mapping
    event_data = {"response_body": response_body, "event": event}
    if mapping:
        event_data["mapping"] = mapping
        
    response_mapping = load_and_execute_function_from_s3(
        api_template_bucket,
        response_mapping_path,
        function_name,
        event_data
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
            resource="transcribe_status",
            method="get"
        )

        # Create the request body using the template
        try:
            logger.info("Creating request body with event structure", extra={"event_keys": list(event.keys())})
            if "payload" in event:
                logger.info("Payload structure", extra={"payload_keys": list(event["payload"].keys())})
            if "metadata" in event:
                logger.info("Metadata structure", extra={"metadata_keys": list(event["metadata"].keys())})
            
            request_params, mapping = create_request_body(s3_templates, api_template_bucket, event)
            logger.info("Successfully created request params", extra={"request_params": request_params})
        except Exception as e:
            error_msg = f"Error creating request body: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                "statusCode": 500,
                "body": json.dumps({"error": error_msg})
            }

        # Get the transcription job status
        job_name = request_params.get("TranscriptionJobName")
        if not job_name:
            error_msg = "TranscriptionJobName is missing in request parameters"
            logger.error(error_msg)
            return {
                "statusCode": 500,
                "body": json.dumps({"error": error_msg})
            }
            
        logger.info(f"Getting transcription job status for job: {job_name}")
        try:
            status = transcribe_client.get_transcription_job(TranscriptionJobName=job_name)
            logger.info("Successfully retrieved transcription job status",
                        extra={"job_status": status['TranscriptionJob']['TranscriptionJobStatus']})
        except Exception as e:
            error_msg = f"Error getting transcription job status: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                "statusCode": 500,
                "body": json.dumps({"error": error_msg})
            }
        
        # If job is completed, update DynamoDB
        status_value = status['TranscriptionJob']['TranscriptionJobStatus']

        if status_value == 'COMPLETED':
             # Extract inventory_id from the original pipeline input
            data_block = event.get("payload", {}).get("data", {})
            body = data_block.get("body", {})
            # sometimes body is a JSON string
            if isinstance(body, str):
                body = json.loads(body)
            inventory_id = body.get("inventory_id")  
            # Extract transcript URI
            transcript_uri = status['TranscriptionJob']['Transcript']['TranscriptFileUri']
            bucket, s3_key = http_to_s3_comps(transcript_uri)
            
            # Store a reference to the transcription file in the DynamoDB asset table
            table = dynamodb.Table(os.getenv("MEDIALAKE_ASSET_TABLE"))
            table.update_item(
                Key={"InventoryID": inventory_id},
                UpdateExpression="SET TranscriptionS3Uri = :val",
                ExpressionAttributeValues={":val": f"s3://{bucket}/{s3_key}"}
            )
            
            # Read the transcript content
            json_content = read_json_from_s3(bucket, s3_key)
            # Add transcript content to the status response for the template
            status['transcript_content'] = json_content['results']['transcripts'][0]['transcript']
        
        # Process the response using the template
        try:
            logger.info("Creating response output")
            result = create_response_output(s3_templates, api_template_bucket, status, event, mapping)
            logger.info("Successfully created response output")
            return result
        except Exception as e:
            error_msg = f"Error processing response: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                "statusCode": 500,
                "body": json.dumps({"error": error_msg})
            }
        
    except Exception as e:
        error_message = f"Error processing transcription status: {str(e)}"
        logger.exception(error_message)
        return {
            "statusCode": 500,
            "body": json.dumps({"error": error_message})
        }
