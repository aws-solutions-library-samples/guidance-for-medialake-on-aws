import boto3
import os
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext

logger = Logger()
tracer = Tracer()


def clean_asset_id(input_string: str) -> str:
    parts = input_string.split(":")
    uuid = parts[-1]
    if uuid == "master":
        uuid = parts[-2]
    return f"asset:uuid:{uuid}"


def create_proxy_job_settings(input_bucket, input_key, output_bucket, output_key):
    return {
        "Inputs": [
            {
                "FileInput": f"s3://{input_bucket}/{input_key}",
                "AudioSelectors": {"Audio Selector 1": {"DefaultSelection": "DEFAULT"}},
                "VideoSelector": {},
            }
        ],
        "OutputGroups": [
            {
                "Name": "Proxy Video",
                "OutputGroupSettings": {
                    "Type": "FILE_GROUP_SETTINGS",
                    "FileGroupSettings": {
                        "Destination": f"s3://{output_bucket}/{output_key}/proxy/"
                    },
                },
                "Outputs": [
                    {
                        "VideoDescription": {
                            "CodecSettings": {
                                "Codec": "H_264",
                                "H264Settings": {
                                    "RateControlMode": "QVBR",
                                    "SceneChangeDetect": "TRANSITION_DETECTION",
                                },
                            },
                            "Width": 640,
                            "Height": 360,
                        },
                        "AudioDescriptions": [
                            {
                                "CodecSettings": {
                                    "Codec": "AAC",
                                    "AacSettings": {
                                        "Bitrate": 96000,
                                        "CodingMode": "CODING_MODE_2_0",
                                        "SampleRate": 48000,
                                    },
                                }
                            }
                        ],
                        "ContainerSettings": {"Container": "MP4", "Mp4Settings": {}},
                    }
                ],
            }
        ],
    }


@logger.inject_lambda_context
@tracer.capture_lambda_handler
def lambda_handler(event, context: LambdaContext):
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
        return {"statusCode": 400, "body": "Missing required parameters"}

    mediaconvert = boto3.client("mediaconvert", region_name="us-east-1")
    endpoints = mediaconvert.describe_endpoints()
    mediaconvert_endpoint = endpoints["Endpoints"][0]["Url"]
    mediaconvert = boto3.client("mediaconvert", endpoint_url=mediaconvert_endpoint)

    try:
        output_key = f"{bucket}/{key.rsplit('.', 1)[0]}"
        job_settings = create_proxy_job_settings(bucket, key, output_bucket, output_key)

        response = mediaconvert.create_job(
            Role=os.environ["MEDIACONVERT_ROLE_ARN"], Settings=job_settings
        )

        job_id = response["Job"]["Id"]
        logger.info(f"MediaConvert job created with ID: {job_id}")

        proxy_representation = {
            "ID": f"{asset_id}:proxy",
            "Type": "Video",
            "Format": "MP4",
            "Purpose": "proxy",
            "StorageInfo": {
                "PrimaryLocation": {
                    "StorageType": "s3",
                    "Provider": "aws",
                    "Bucket": output_bucket,
                    "ObjectKey": {
                        "FullPath": f"{output_key}/proxy/output.mp4",
                    },
                    "Status": "processing",
                }
            },
        }

        # Update DynamoDB
        response = table.update_item(
            Key={"InventoryID": clean_inventory_id},
            UpdateExpression="SET #dr = list_append(if_not_exists(#dr, :empty_list), :new_rep)",
            ExpressionAttributeNames={"#dr": "DerivedRepresentations"},
            ExpressionAttributeValues={
                ":new_rep": [proxy_representation],
                ":empty_list": [],
            },
            ReturnValues="UPDATED_NEW",
        )

        logger.info(
            "DynamoDB update response",
            extra={"response": response, "inventory_id": clean_inventory_id},
        )

        return {
            "statusCode": 200,
            "body": {
                "JobId": job_id,
                "Proxy": {
                    "ID": f"{asset_id}:proxy",
                    "type": "video",
                    "format": "MP4",
                    "Purpose": "proxy",
                    "StorageInfo": proxy_representation["StorageInfo"],
                },
            },
        }

    except Exception as e:
        logger.exception(
            "Error processing video",
            extra={
                "inventory_id": clean_inventory_id,
                "error": str(e),
                "error_type": type(e).__name__,
            },
        )
        return {"statusCode": 500, "body": f"Error processing video: {str(e)}"}
