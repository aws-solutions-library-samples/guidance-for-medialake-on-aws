import boto3
import os
import json
import time
from aws_lambda_powertools import Logger, Tracer
from lambda_middleware import lambda_middleware

# Initialize Powertools
logger = Logger()
tracer = Tracer()

# Initialize AWS clients
transcribe_client = boto3.client('transcribe')

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

@lambda_middleware(
    event_bus_name=os.environ.get("EVENT_BUS_NAME", "default-event-bus"),
    large_payload_bucket=os.environ.get("LARGE_PAYLOAD_BUCKET")
)
@logger.inject_lambda_context
@tracer.capture_lambda_handler
def lambda_handler(event, context):
    try:
        logger.info("Received event", extra={"event": event})

        # Retrieve storage from the input section if needed
        input_data = event.get("detail", {}).get("outputs", {}).get("input", {})
        storage_data = input_data.get("DigitalSourceAsset", {}).get("MainRepresentation", {}).get("StorageInfo", {}).get("PrimaryLocation", {})

        # Initialize variables for S3 bucket, key
        s3_bucket = storage_data.get("Bucket", {})
        s3_key = storage_data.get("ObjectKey", {}).get("FullPath", {})
        s3_path = storage_data.get("ObjectKey", {}).get("Path", {})
        
        clean_inventory_id = input_data.get("InventoryID", {})
        
        # Extract the base name from the source key (without extension)
        base_name = os.path.splitext(os.path.basename(s3_key))[0]

        out_bucket = os.environ['MEDIA_ASSETS_BUCKET_NAME']
        
        job_name = f"{base_name}-{int(time.time())}"

        print(s3_bucket)

        job = transcribe_client.start_transcription_job(
            TranscriptionJobName=job_name,
            Media={'MediaFileUri': f's3://{s3_bucket}/{s3_key}'},
            MediaFormat=os.path.splitext(s3_key)[1][1:],
            IdentifyLanguage=True,
            OutputBucketName=out_bucket,
            OutputKey=f"{s3_bucket}/{s3_path}/transcription",
            Subtitles={'Formats': ['vtt']},
            JobExecutionSettings={
                'AllowDeferredExecution': True,
                'DataAccessRoleArn': os.environ.get("TRANSCRIBE_ROLE_ARN")
            }
        )

        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": f"Successfully started transcription job for {s3_key}",
                "asset_id": clean_inventory_id,
                "transcription": {
                    "engine": "AMAZON_TRANSCRIBE",
                    "id": job['TranscriptionJob']['TranscriptionJobName'],
                    "status": job['TranscriptionJob']['TranscriptionJobStatus'],
                    "job_name": job_name
                }
            })
        }
        
    except Exception as e:
        error_message = f"Error creating transcription job: {str(e)}"
        logger.exception(error_message)
        return {
            "statusCode": 500,
            "body": json.dumps({"error": error_message})
        }
