import boto3
import os
import json
import requests
import time
import datetime
from aws_lambda_powertools import Logger, Tracer
from lambda_middleware import lambda_middleware
from nodes_utils import format_duration
from decimal import Decimal
import re

# Initialize Powertools
logger = Logger()
tracer = Tracer()

# Initialize AWS clients
s3 = boto3.resource('s3')
s3_client = boto3.client('s3')
bedrock_runtime_client = boto3.client("bedrock-runtime")

class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal) or isinstance(obj, datetime.datetime):
            return str(obj)
        return super().default(obj)

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

        bedrock_model_id = os.environ.get("BEDROCK_MODEL_ID", "anthropic.claude-3-5-sonnet-20240620-v1:0") # TODO should be a parameter so customer can choose the model
        summary_instructions = os.environ.get("SUMMARY_INSTRUCTIONS", "Summarize the following transcript in 100 words or less.")

        payload = json.loads(event['payload']['body'])

        # Get the transcript from S3
        transcript_s3_key = payload.get('transcription', {}).get('object', {}).get('key', {})
        transcript_s3_bucket = payload.get('transcription', {}).get('object', {}).get('bucket', {})
        transcript_file = s3.Object(transcript_s3_bucket, transcript_s3_key)
        transcript_json = json.loads(transcript_file.get()['Body'].read().decode('utf-8'))

        transcript = json.dumps(transcript_json['results']['transcripts'][0]['transcript'])

        # Create the payload to provide to the Anthropic model.
        messages = [{ "role":"user", "content":[{"type":"text","text": summary_instructions + " " + transcript}]}]

        body=json.dumps(
            {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 4096,
                "messages": messages,
                "temperature": 0,
                "top_p": 1.
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
