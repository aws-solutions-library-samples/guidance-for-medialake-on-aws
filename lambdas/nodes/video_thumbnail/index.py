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


def create_thumbnail_job_settings(
    input_bucket, input_key, output_bucket, output_key, timecode=None, percentage=None
):
    input_settings = {
        "FileInput": f"s3://{input_bucket}/{input_key}",
        "AudioSelectors": {"Audio Selector 1": {"DefaultSelection": "DEFAULT"}},
        "VideoSelector": {},
    }

    if timecode:
        input_settings["InputClippings"] = [{"StartTimecode": timecode}]
    elif percentage is not None:
        input_settings["InputClippings"] = [
            {"StartTimecode": f"00:00:{percentage:.2f}"}
        ]

    return {
        "Inputs": [input_settings],
        "OutputGroups": [
            {
                "Name": "Thumbnail",
                "OutputGroupSettings": {
                    "Type": "FILE_GROUP_SETTINGS",
                    "FileGroupSettings": {
                        "Destination": f"s3://{output_bucket}/{output_key}/thumbnail/",
                        "DestinationSettings": {
                            "S3Settings": {
                                "AccessControl": {
                                    "CannedAcl": "BUCKET_OWNER_FULL_CONTROL"
                                }
                            }
                        },
                    },
                },
                "Outputs": [
                    {
                        "VideoDescription": {
                            "CodecSettings": {"Codec": "JPG"},
                            "Width": 640,
                            "Height": 360,
                        },
                        "ContainerSettings": {"Container": "RAW"},
                    }
                ],
            }
        ],
    }


@logger.inject_lambda_context
@tracer.capture_lambda_handler
def lambda_handler(event, context: LambdaContext):
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
    timecode = event.get("timecode")
    percentage = event.get("percentage")

    if not all([key, bucket, output_bucket]):
        return {"statusCode": 400, "body": "Missing required parameters"}

    # Use percentage if timecode is not provided
    if timecode is None and percentage is None:
        logger.info("No percentage or timecode provided. Use default 25 percent.")
        percentage = 25  # Default to 25% if neither is provided

    if timecode is None and percentage is None:
        return {
            "statusCode": 400,
            "body": "Either timecode or percentage must be provided",
        }

    mediaconvert = boto3.client("mediaconvert", region_name="us-east-1")
    endpoints = mediaconvert.describe_endpoints()
    mediaconvert_endpoint = endpoints["Endpoints"][0]["Url"]
    mediaconvert = boto3.client("mediaconvert", endpoint_url=mediaconvert_endpoint)

    try:
        output_key = f"{bucket}/{key.rsplit('.', 1)[0]}"
        job_settings = create_thumbnail_job_settings(
            bucket, key, output_bucket, output_key, timecode, percentage
        )

        response = mediaconvert.create_job(
            Role=os.environ["MEDIACONVERT_ROLE_ARN"],
            Settings=job_settings,
            Queue=mediaconvert_queue,
        )

        job_id = response["Job"]["Id"]
        logger.info(f"MediaConvert job created with ID: {job_id}")

        thumbnail_representation = {
            "ID": f"{asset_id}:thumbnail",
            "Type": "Image",
            "Format": "JPG",
            "Purpose": "thumbnail",
            "StorageInfo": {
                "PrimaryLocation": {
                    "StorageType": "s3",
                    "Provider": "aws",
                    "Bucket": output_bucket,
                    "ObjectKey": {
                        "FullPath": f"{output_key}/thumbnail/output.0000001.jpg",
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
                ":new_rep": [thumbnail_representation],
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
                "Thumbnail": {
                    "ID": f"{asset_id}:thumbnail",
                    "type": "image",
                    "format": "JPG",
                    "Purpose": "thumbnail",
                    "StorageInfo": thumbnail_representation["StorageInfo"],
                },
            },
        }

    except Exception as e:
        logger.exception(
            "Error processing video for thumbnail",
            extra={
                "inventory_id": clean_inventory_id,
                "error": str(e),
                "error_type": type(e).__name__,
            },
        )
        return {
            "statusCode": 500,
            "body": f"Error processing video for thumbnail: {str(e)}",
        }
