import boto3
import json
import os
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext
import botocore


# Initialize Powertools
logger = Logger()
tracer = Tracer()


def clean_asset_id(input_string: str) -> str:
    parts = input_string.split(":")
    uuid = parts[-1]
    if uuid == "master":
        uuid = parts[-2]
    return f"asset:uuid:{uuid}"


@logger.inject_lambda_context
@tracer.capture_lambda_handler
def lambda_handler(event, context):
    # Get DynamoDB table name from environment variable
    table_name = os.environ["MEDIALAKE_ASSET_TABLE"]
    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(table_name)

    video_proxy_and_thumbnail_result = event["previous_task_output"][
        "VideoProxyandThumbnailResult"
    ]
    job_id = video_proxy_and_thumbnail_result["Payload"]["body"]["JobId"]
    inventory_id = event["input"]["InventoryID"]
    clean_inventory_id = clean_asset_id(inventory_id)
    asset_id = clean_asset_id(event["input"]["DigitalSourceAsset"]["ID"])

    mediaconvert = boto3.client("mediaconvert", region_name="us-east-1")

    response = mediaconvert.get_job(Id=job_id)
    status = response["Job"]["Status"]

    if status == "COMPLETE":
        # Get the output bucket and base path
        output_group_settings = response["Job"]["Settings"]["OutputGroups"][0][
            "OutputGroupSettings"
        ]["FileGroupSettings"]
        output_bucket = (
            output_group_settings["Destination"].split("s3://")[1].split("/")[0]
        )
        base_path = output_group_settings["Destination"].split(
            f"s3://{output_bucket}/"
        )[1]

        # Construct proxy and thumbnail paths
        proxy_path = f"{base_path}.mp4"
        thumbnail_path = f"{base_path}_thumbnail.0000000.jpg"

        # Get file sizes (mocked here, replace with actual S3 metadata retrieval if needed)
        proxy_size = 5000000  # Replace with actual size in bytes from S3
        thumbnail_size = 12670  # Replace with actual size in bytes from S3

        try:
            # Create proxy representation
            proxy_representation = {
                "ID": f"{asset_id}:proxy",
                "Type": "Video",
                "Format": "MP4",
                "Purpose": "proxy",
                "StorageInfo": {
                    "PrimaryLocation": {
                        "Bucket": output_bucket,
                        "ObjectKey": {
                            "FullPath": proxy_path,
                        },
                        "FileInfo": {
                            "Size": proxy_size,
                        },
                        "Provider": "aws",
                        "Status": "active",
                        "StorageType": "s3",
                    }
                },
            }

            # Create thumbnail representation
            thumbnail_representation = {
                "ID": f"{asset_id}:thumbnail",
                "Type": "Image",
                "Format": "JPEG",
                "Purpose": "thumbnail",
                "ImageSpec": {
                    "Resolution": {
                        "Height": 400,
                        "Width": 300,
                    }
                },
                "StorageInfo": {
                    "PrimaryLocation": {
                        "Bucket": output_bucket,
                        "ObjectKey": {
                            "FullPath": thumbnail_path,
                        },
                        "FileInfo": {
                            "Size": thumbnail_size,
                        },
                        "Provider": "aws",
                        "Status": "active",
                        "StorageType": "s3",
                    }
                },
            }

            # Update DynamoDB
            try:
                response = table.update_item(
                    Key={"InventoryID": clean_inventory_id},
                    UpdateExpression="SET DerivedRepresentations = list_append(if_not_exists(DerivedRepresentations, :empty_list), :new_reps)",
                    ConditionExpression="attribute_not_exists(DerivedRepresentations) OR NOT contains(DerivedRepresentations, :proxy_id)",
                    ExpressionAttributeValues={
                        ":new_reps": [
                            proxy_representation,
                            thumbnail_representation,
                        ],
                        ":empty_list": [],
                        ":proxy_id": proxy_representation["ID"],
                    },
                    ReturnValues="UPDATED_NEW",
                )
            except botocore.exceptions.ClientError as e:
                if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                    logger.info("Proxy representation already exists, skipping update")
                else:
                    raise

            logger.info(
                "DynamoDB update response",
                extra={"response": response, "inventory_id": clean_inventory_id},
            )

        except Exception as e:
            logger.exception(
                "Error updating DynamoDB",
                extra={
                    "inventory_id": clean_inventory_id,
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
            )
            raise

        return {
            "status": status,
            "proxy": {
                "StorageInfo": {
                    "PrimaryLocation": {
                        "StorageType": "s3",
                        "Bucket": output_bucket,
                        "path": proxy_path,
                        "status": "active",
                        "ObjectKey": {"FullPath": proxy_path},
                    }
                }
            },
            "thumbnail": {
                "StorageInfo": {
                    "PrimaryLocation": {
                        "StorageType": "s3",
                        "Bucket": output_bucket,
                        "path": thumbnail_path,
                        "status": "active",
                        "ObjectKey": {"FullPath": thumbnail_path},
                    }
                }
            },
        }

    return {"status": status}
