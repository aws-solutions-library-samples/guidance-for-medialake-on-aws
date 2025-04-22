import boto3
import os
import json
import time
import random
from datetime import datetime, timedelta
from botocore.exceptions import ClientError
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext

logger = Logger()
tracer = Tracer()

DYNAMODB_TABLE_NAME = "MediaConvertEndpointsCache"
CACHE_KEY = "mediaconvert-endpoints"
CACHE_TTL_SECONDS = 3600  # 1 hour


def clean_asset_id(input_string: str) -> str:
    parts = input_string.split(":")
    uuid = parts[-1]
    if uuid == "master":
        uuid = parts[-2]
    return f"asset:uuid:{uuid}"


def create_audio_conversion_job_settings(
    input_bucket, input_key, output_bucket, output_key
):
    """
    Build a job settings JSON for audio-only conversion to MP3.
    This removes video settings and thumbnail outputs.
    """
    job_settings = {
        "Inputs": [
            {
                "FileInput": f"s3://{input_bucket}/{input_key}",
                "AudioSelectors": {"Audio Selector 1": {"DefaultSelection": "DEFAULT"}},
            }
        ],
        "OutputGroups": [
            {
                "Name": "Audio Conversion",
                "OutputGroupSettings": {
                    "Type": "FILE_GROUP_SETTINGS",
                    "FileGroupSettings": {
                        "Destination": f"s3://{output_bucket}/{output_key}_audio"
                    },
                },
                "Outputs": [
                    {
                        "AudioDescriptions": [
                            {
                                "CodecSettings": {
                                    "Codec": "MP3",
                                    "Mp3Settings": {
                                        "Bitrate": 128000,
                                        "SampleRate": 44100,
                                        "RateControlMode": "CBR",  # This property is now provided
                                    },
                                }
                            }
                        ],
                        "ContainerSettings": {"Container": "RAW"},
                    }
                ],
            }
        ],
    }
    return job_settings


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


@logger.inject_lambda_context
@tracer.capture_lambda_handler
def lambda_handler(event, context: LambdaContext):
    try:
        mediaconvert_queue = os.environ["MEDIACONVERT_QUEUE"]
        table_name = os.environ["MEDIALAKE_ASSET_TABLE"]
        dynamodb = boto3.resource("dynamodb")
        table = dynamodb.Table(table_name)

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
                "statusCode": 400,
                "body": json.dumps({"error": "Missing required parameters"}),
            }

        mediaconvert_endpoint = get_mediaconvert_endpoint()
        mediaconvert = boto3.client("mediaconvert", endpoint_url=mediaconvert_endpoint)

        output_key = f"{bucket}/{key.rsplit('.', 1)[0]}"
        # Use the new job settings for audio-only conversion.
        job_settings = create_audio_conversion_job_settings(
            bucket, key, output_bucket, output_key
        )

        response = mediaconvert.create_job(
            Role=os.environ["MEDIACONVERT_ROLE_ARN"],
            Settings=job_settings,
            Queue=mediaconvert_queue,
        )

        job_id = response["Job"]["Id"]
        logger.info(f"MediaConvert job created with ID: {job_id}")

        return {"statusCode": 200, "body": json.dumps({"JobId": job_id})}

    except Exception as e:
        logger.exception(
            "Error processing audio",
            extra={
                "inventory_id": clean_inventory_id,
                "error": str(e),
                "error_type": type(e).__name__,
            },
        )
        return {
            "statusCode": 500,
            "body": json.dumps(
                {
                    "error": "Error processing audio",
                    "details": str(e),
                    "error_type": type(e).__name__,
                }
            ),
        }
