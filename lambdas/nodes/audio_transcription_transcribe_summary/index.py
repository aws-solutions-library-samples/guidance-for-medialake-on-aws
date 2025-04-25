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


@tracer.capture_method
def get_asset_details(inventory_id: str) -> Dict[str, Any]:
    """
    Retrieves asset details from DynamoDB.

    Args:
        inventory_id: The inventory ID of the asset

    Returns:
        Dict containing the asset details

    Raises:
        AssetDetailsError: If the retrieval fails or asset not found
    """
    try:
        response = table.get_item(
            Key={"InventoryID": inventory_id},
            ConsistentRead=True,  # Ensure we get the latest data
        )
        print(response)

        if "Item" not in response:
            raise ValueError(
                f"Asset with ID {inventory_id} not found"
            )

        asset_data = response["Item"]

        # Log successful retrieval (excluding sensitive data)
        logger.info(
            "Asset details retrieved successfully",
            extra={
                "inventory_id": inventory_id,
                "asset_type": asset_data.get("assetType"),
                # "retrieval_timestamp": tracer.get_timestamp(),
            },
        )

        return asset_data

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        error_message = e.response["Error"]["Message"]

        logger.error(
            f"DynamoDB error: {error_message}",
            extra={"error_code": error_code, "inventory_id": inventory_id},
        )

        raise ValueError(f"Failed to retrieve asset details: {error_message}")


@tracer.capture_method
def get_asset_transcript(s3_uri: str) -> Dict[str, Any]:
    """Read asset transcript from S3."""
    try:
        # Get the content of the S3 object
        bucket, key = parse_s3_uri(s3_uri)

        # Get the transcript from S3
        s3_data = s3.Object(bucket, key)
        transcript_data = s3_data.get()['Body'].read().decode('utf-8')
        transcript = json.loads(transcript_data)
        
        return transcript
    except Exception as e:
        logger.error(f"Error getting asset transcript data: {str(e)}")
        return None


@tracer.capture_method
def parse_s3_uri(s3_uri):
    # Handle both s3://bucket/key format and direct bucket/key format
    if s3_uri.startswith("s3://"):
        parsed = urlparse(s3_uri)
        bucket = parsed.netloc
        # Remove the leading '/' from the path
        key = parsed.path.lstrip("/")
        return bucket, key
    else:
        # If it's not a proper S3 URI, try to extract bucket and key directly
        parts = s3_uri.split("/", 1)
        if len(parts) == 2:
            return parts[0], parts[1]
        else:
            raise ValueError(f"Invalid S3 URI format: {s3_uri}")


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
            resource="transcribe_summary",
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

        # Extract asset ID from the request parameters
        asset_id = request_params.get("asset_id")
        bedrock_model_id = request_params.get("bedrock_model_id")
        summary_instructions = request_params.get("summary_instructions")

        # Get the asset details from DDB
        asset_details = get_asset_details(asset_id)

        # Check if the asset has a transcript
        if "TranscriptionS3Uri" not in asset_details:
            error_response = {
                "statusCode": 404,
                "body": {"message": "Asset transcript not found"},
                "status": "FAILED"
            }
            return create_response_output(s3_templates, api_template_bucket, error_response, event, mapping)
        
        # Get transcript
        transcript_full = get_asset_transcript(asset_details["TranscriptionS3Uri"])
        transcript = json.dumps(transcript_full['results']['transcripts'][0]['transcript'])

        # Create the payload to provide to the Anthropic model
        messages = [{"role": "user", "content": [{"text": summary_instructions + "\n\ntranscript: " + transcript}]}]

        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 2000,
            "messages": messages,
            "system": "You are an expert in summazing audio transcription",
            "temperature": 1,
            "top_p": 0.999
        })

        logger.info(f'Invoking model: {bedrock_model_id}')

        # Invoke Bedrock model
        response = bedrock_runtime_client.invoke_model(body=body, modelId=bedrock_model_id)
        assistant_response = json.loads(response.get('body').read())
        
        # Parse S3 URI and create summary file path
        _bucket, _key = parse_s3_uri(asset_details["TranscriptionS3Uri"])
        summary_base_path = os.path.splitext(_key)[0]
        summary_file_name = f"{summary_base_path}-summary.txt"
        
        # Save the summary to S3
        s3_client.put_object(
            Bucket=_bucket,
            Key=summary_file_name,
            Body=assistant_response['content'][0]['text'],
            ContentType='text/plain'
        )

        # Update DynamoDB with the summary S3 URI
        table.update_item(
            Key={"InventoryID": asset_id},
            UpdateExpression="SET TranscriptionSummaryS3Uri = :val",
            ExpressionAttributeValues={":val": f"s3://{_bucket}/{summary_file_name}"}
        )

        # Create the response
        result = {
            "summary_s3_uri": f"s3://{_bucket}/{summary_file_name}",
            "status": "SUCCEEDED"
        }
        
        # Process the response using the template
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
