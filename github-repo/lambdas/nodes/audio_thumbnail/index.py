import json
import os
import subprocess
import tempfile

import boto3
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


def generate_waveform_thumbnail(
    mp3_file_path, thumbnail_output_path, width=800, height=100
):
    """
    Use the waveform tool (from https://github.com/andrewrk/waveform) to generate a waveform image.
    This is just a stub—adjust the command line options as needed.
    """
    command = [
        "waveform",
        mp3_file_path,
        "--png",
        thumbnail_output_path,
        "--png-width",
        str(width),
        "--png-height",
        str(height),
    ]
    subprocess.run(command, check=True)
    logger.info(f"Generated waveform thumbnail: {thumbnail_output_path}")


@logger.inject_lambda_context
@tracer.capture_lambda_handler
def lambda_handler(event, context: LambdaContext):
    try:
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
        width = event.get("width", 800)
        height = event.get("height", 100)

        if not all([key, bucket, output_bucket]):
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "Missing required parameters"}),
            }

        s3 = boto3.client("s3")

        # Create temporary files for processing
        with tempfile.NamedTemporaryFile(
            suffix=".mp3"
        ) as temp_input_file, tempfile.NamedTemporaryFile(
            suffix=".png"
        ) as temp_output_file:

            # Download the audio file
            logger.info(f"Downloading audio file from s3://{bucket}/{key}")
            s3.download_file(bucket, key, temp_input_file.name)

            # Generate the waveform thumbnail
            logger.info(
                f"Generating waveform thumbnail with dimensions {width}x{height}"
            )
            generate_waveform_thumbnail(
                temp_input_file.name, temp_output_file.name, width=width, height=height
            )

            # Upload the thumbnail to S3
            output_key = f"{bucket}/{key.rsplit('.', 1)[0]}_waveform.png"
            logger.info(f"Uploading thumbnail to s3://{output_bucket}/{output_key}")
            s3.upload_file(
                temp_output_file.name,
                output_bucket,
                output_key,
                ExtraArgs={"ContentType": "image/png"},
            )

        # Create a new representation for the thumbnail
        thumbnail_asset_id = f"{asset_id}:waveform"
        new_representation = {
            "ID": thumbnail_asset_id,
            "Type": "Image",
            "Format": "PNG",
            "Purpose": "waveform",
            "StorageInfo": {
                "PrimaryLocation": {
                    "StorageType": "s3",
                    "Provider": "aws",
                    "Bucket": output_bucket,
                    "ObjectKey": {"FullPath": output_key},
                    "Status": "active",
                }
            },
            "ImageSpec": {"Resolution": {"Width": width, "Height": height}},
        }

        # Update DynamoDB with the new representation
        try:
            logger.info(
                "Attempting DynamoDB update",
                extra={
                    "inventory_id": clean_inventory_id,
                    "new_representation": new_representation,
                },
            )
            response = table.update_item(
                Key={"InventoryID": clean_inventory_id},
                UpdateExpression="SET #dr = list_append(if_not_exists(#dr, :empty_list), :new_rep)",
                ExpressionAttributeNames={"#dr": "DerivedRepresentations"},
                ExpressionAttributeValues={
                    ":new_rep": [new_representation],
                    ":empty_list": [],
                },
                ReturnValues="UPDATED_NEW",
            )
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
            "statusCode": 200,
            "body": json.dumps(
                {
                    "ID": thumbnail_asset_id,
                    "type": "image",
                    "format": "PNG",
                    "Purpose": "waveform",
                    "StorageInfo": {
                        "PrimaryLocation": {
                            "StorageType": "s3",
                            "Bucket": output_bucket,
                            "path": output_key,
                            "status": "active",
                            "ObjectKey": {"FullPath": output_key},
                        }
                    },
                    "location": {"bucket": output_bucket, "key": output_key},
                }
            ),
        }

    except Exception as e:
        logger.exception(
            "Error generating audio waveform",
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
                    "error": "Error generating audio waveform",
                    "details": str(e),
                    "error_type": type(e).__name__,
                }
            ),
        }
