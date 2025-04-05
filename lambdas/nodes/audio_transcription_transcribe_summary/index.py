import boto3
import os
import json
import time
import datetime
from aws_lambda_powertools import Logger, Tracer
from lambda_middleware import lambda_middleware
from nodes_utils import format_duration
from decimal import Decimal
import re
from typing import Dict, Any, Optional
from botocore.exceptions import ClientError

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
        
@lambda_middleware(
    event_bus_name=os.environ.get("EVENT_BUS_NAME", "default-event-bus"),
    large_payload_bucket=os.environ.get("LARGE_PAYLOAD_BUCKET")
)
@logger.inject_lambda_context
@tracer.capture_lambda_handler
def lambda_handler(event, context):
    try:
        logger.info("Received event", extra={"event": event})
        print(event)

        payload = json.loads(event['payload']['body'])

        # Extract asset ID
        asset_id = payload.get("asset_id")

        # Get the asset details from DDB
        asset_details = get_asset_details(asset_id)

        # Check if the asset has a transcript
        if "TranscriptionS3Uri" not in asset_details:
            return {
                "statusCode": 404,
                "body": json.dumps({"message": "Asset transcript not found"})
            }
        
        # Add transcript
        transcript_full = get_asset_transcript(asset_details["TranscriptionS3Uri"])
        print(transcript)

        bedrock_model_id = os.environ.get("BEDROCK_MODEL_ID", "anthropic.claude-3-5-sonnet-20240620-v1:0") # TODO should be a parameter so customer can choose the model
        summary_instructions = os.environ.get("SUMMARY_INSTRUCTIONS", "Summarize the following audio transcript in 100 words or less.")

        transcript = json.dumps(transcript_full['results']['transcripts'][0]['transcript'])

        # Create the payload to provide to the Anthropic model.
        messages = [{ "role":"user", "content":[{"text": summary_instructions + "\n\ntranscript: " + transcript}]}]

        body=json.dumps(
            {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 2000,
                "messages": messages,
                "system": "You are an expert in summazing audio transcription",
                "temperature": 1,
                "top_p": 0.999
            }
        )

        print(f'Invoking model: {bedrock_model_id}')

        response = bedrock_runtime_client.invoke_model(body=body, modelId=bedrock_model_id)

        print(f'response: {response}')

        # Save the response value.
        assistant_response = json.loads(response.get('body').read())
        print(f'assistant_response: {assistant_response}')

        summary_base_path = os.path.splitext(transcript_s3_key)[0]

        summary_file_name = "{summary_base_path}-summary.txt",
        print(f'summary_file_name: {summary_file_name}')

        # Save the response value in S3.
        s3_client.put_object(
            Bucket=transcript_s3_bucket,
            Key=summary_file_name,
            Body=assistant_response['content'][0]['text'],
            ContentType='text/plain'
        )

        result = {
            "bucket_name": transcript_s3_bucket,
            "summary_key_name": summary_file_name,
            "status": "SUCCEEDED"
        }
        
        return {
            "statusCode": 200,
            "body": json.dumps(result, cls=CustomJSONEncoder)
        }
        
    except Exception as e:
        error_message = f"Error processing transcription summary: {str(e)}"
        logger.exception(error_message)
        return {
            "statusCode": 500,
            "body": json.dumps({"error": error_message})
        }
