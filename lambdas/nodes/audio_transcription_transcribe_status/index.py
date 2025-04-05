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

# Initialize Powertools
logger = Logger()
tracer = Tracer()

# Initialize AWS clients
s3 = boto3.resource('s3')
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

        job_name = payload.get('transcription', {}).get('job_name', {})

        status = transcribe_client.get_transcription_job(TranscriptionJobName=job_name)
        status_value = status['TranscriptionJob']['TranscriptionJobStatus']
        if status_value in ['FAILED']:
            error_msg = f"Transcription failed: {str(e)}"
            logger.error(error_msg)
            return {
                "statusCode": 500,
                "body": json.dumps({"error": error_msg})
            }
        elif status_value in ['COMPLETED']:
            detected_language = status['TranscriptionJob']['LanguageCode']
            bucket, s3_key = http_to_s3_comps(status['TranscriptionJob']['Transcript']['TranscriptFileUri'])

            # download result from Amazon S3
            json_content = read_json_from_s3(bucket, s3_key)
            transcript = json_content['results']['transcripts'][0]['transcript']

            # Store a reference to the transcription file in the DynamoDB asset table
            table = dynamodb.Table(os.getenv("MEDIALAKE_ASSET_TABLE"))
            table.update_item(
                Key={"InventoryID": payload.get("asset_id")},
                UpdateExpression="SET TranscriptionS3Uri = :val",
                ExpressionAttributeValues={":val": f"s3://{bucket}/{s3_key}"}
            )

        # Return success response with status and metadata
        body_obj = {
            "status": status_value,
            "asset_id": payload.get("asset_id"),
            "transcription": {
                "job_name": job_name
            }
        }
        
        payload_external_status = "not_ready"
        if status_value in ['COMPLETED']:
            body_obj["transcription"]["transcript"] = transcript
            body_obj["transcription"]["detected_language"] = detected_language
            body_obj["transcription"]["object"] = {
                "bucket": bucket,
                "key": s3_key
            }
            payload_external_status = "ready"
        
        return {
            "statusCode": 200,
            "body": json.dumps(body_obj, cls=CustomJSONEncoder),
            "externalTaskStatus": payload_external_status
        }
        
    except Exception as e:
        error_message = f"Error processing transcription status: {str(e)}"
        logger.exception(error_message)
        return {
            "statusCode": 500,
            "body": json.dumps({"error": error_message})
        }
