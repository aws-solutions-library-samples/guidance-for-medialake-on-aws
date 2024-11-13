import os
import boto3
import json
import subprocess
from decimal import Decimal
from aws_lambda_powertools import Logger
from iptcinfo3 import IPTCInfo
from io import BytesIO
from boto3.dynamodb.types import TypeSerializer
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.utilities.data_classes import event_source
from boto3.dynamodb.types import TypeDeserializer


# Initialize the logger
logger = Logger(service="imageMetadataExtractor")

# Initialize the S3 client
s3 = boto3.client("s3")


def convert_floats_to_decimals(obj):
    """Recursively converts float values to Decimal"""
    if isinstance(obj, dict):
        return {key: convert_floats_to_decimals(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [convert_floats_to_decimals(element) for element in obj]
    elif isinstance(obj, float):
        return Decimal(str(obj))
    return obj


def marshall_json_item(item):
    """Marshalls a JSON item into DynamoDB format"""
    serializer = TypeSerializer()
    return {k: serializer.serialize(v) for k, v in item.items()}


def extract_iptc_data(image_content):
    iptc_data = {}
    try:
        logger.info("Starting IPTC extraction")
        iptc_info = IPTCInfo(BytesIO(image_content))
        if hasattr(iptc_info, "data"):
            iptc_data = {
                key: str(value) for key, value in iptc_info.data.items() if value
            }
        logger.info(f"Extracted IPTC data: {iptc_data}")
    except Exception as iptc_error:
        logger.error(f"IPTC extraction error: {str(iptc_error)}")
        logger.error(f"IPTC error type: {type(iptc_error)}")
    return iptc_data


def extract_exif_data(temp_file_path):
    try:
        logger.info(f"Starting EXIF extraction from {temp_file_path}")

        # Use the exiftool binary from the Lambda layer
        exiftool_path = "/opt/bin/exiftool"  # Path to exiftool in Lambda layer
        command = [exiftool_path, "-json", "-fast", temp_file_path]

        process = subprocess.Popen(
            command, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )

        stdout, stderr = process.communicate()

        if stderr:
            logger.warning(f"ExifTool stderr: {stderr.decode()}")

        if stdout:
            exif_data = json.loads(stdout.decode())[0]
            logger.info(f"Extracted EXIF data: {exif_data}")
            return exif_data
        else:
            logger.warning("No EXIF data extracted")
            return {}

    except Exception as exif_error:
        logger.error(f"EXIF extraction error: {str(exif_error)}")
        logger.error(f"EXIF error type: {type(exif_error)}")
        return {}


def process_image_file(bucket, key):
    try:
        # Retrieve the image from S3
        logger.info(f"Retrieving image from S3: bucket={bucket}, key={key}")
        response = s3.get_object(Bucket=bucket, Key=key)
        image_content = response["Body"].read()
        logger.info(f"Retrieved image size: {len(image_content)} bytes")

        # Create a temporary file
        temp_file_path = f"/tmp/{key.split('/')[-1]}"
        logger.info(f"Creating temporary file: {temp_file_path}")

        with open(temp_file_path, "wb") as temp_file:
            temp_file.write(image_content)

        logger.info(f"Temporary file created, size: {os.path.getsize(temp_file_path)}")

        # Extract EXIF data using ExifTool binary
        exif_data = extract_exif_data(temp_file_path)

        # Extract IPTC data
        iptc_data = extract_iptc_data(image_content)

        # Clean up temporary file
        os.remove(temp_file_path)
        logger.info("Temporary file removed")

        # Combine EXIF and IPTC data
        metadata = {"EXIF": exif_data, "IPTC": iptc_data}
        logger.info("Extracted metadata: %s", metadata)

        return metadata

    except Exception as e:
        logger.error("Error processing image file: %s", str(e))
        logger.error(f"Error type: {type(e)}")
        return None


def lambda_handler(event, context):
    logger.info("Received event: %s", event)
    input = event.get("input", {})
    inventory_id = input.get("InventoryID", None)
    digital_source_asset = input.get("DigitalSourceAsset", None)
    bucket = digital_source_asset['MainRepresentation']['StorageInfo']['PrimaryLocation']['Bucket']
    key = digital_source_asset['MainRepresentation']['StorageInfo']['PrimaryLocation']['ObjectKey']['FullPath']
  
    if not inventory_id:
        logger.error("Invalid event format: missing InventoryID")
        return {"statusCode": 400, "body": "Missing InventoryID"}

    try:
        extracted_metadata = process_image_file(bucket, key)
        if extracted_metadata is None:
            return {"statusCode": 500, "body": "Failed to extract metadata"}

        complete_metadata = {
          
            "CustomMetadata": extracted_metadata,
        }
        converted_metadata = convert_floats_to_decimals(complete_metadata)
        marshalled_metadata = {"M": marshall_json_item(converted_metadata)}

        # Initialize DynamoDB client
        dynamodb = boto3.client("dynamodb")

        # Update DynamoDB
        try:
            response = dynamodb.update_item(
                TableName=os.environ["MEDIALAKE_ASSET_TABLE"],
                Key={"InventoryID": {"S": inventory_id}},
                UpdateExpression="SET Metadata = :Metadata",
                ExpressionAttributeValues={":Metadata": marshalled_metadata},
                ReturnValues="UPDATED_NEW",
            )
            logger.info(f"Successfully updated DynamoDB item: {response}")
        except Exception as db_error:
            logger.error(f"Failed to update DynamoDB: {str(db_error)}")
            raise

        return {
            "statusCode": 200,
            "body": {"metadata": marshalled_metadata, "inventoryId": inventory_id},
        }

    except Exception as e:
        logger.error(f"Lambda handler error: {str(e)}")
        logger.error(f"Error type: {type(e)}")
        return {"statusCode": 500, "body": f"Error extracting image metadata: {str(e)}"}
