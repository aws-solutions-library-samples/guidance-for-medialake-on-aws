import os
import boto3
import json
import re
import shlex
import os.path
import subprocess
from decimal import Decimal
from aws_lambda_powertools import Logger
from iptcinfo3 import IPTCInfo, IPTCData
import tempfile
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
        
        # Create a temporary file
        with tempfile.NamedTemporaryFile(delete=False, mode='wb') as temp_file:
            temp_file.write(image_content)
            temp_file.flush()  # Ensure the content is written to disk
            temp_file_path = temp_file.name

        # Use the temporary file path to create IPTCInfo object
        with open(temp_file_path, 'rb') as file:
            iptc_info = IPTCInfo(file)

            if bool(iptc_info):
                iptc_data = {IPTCData._key_as_str(k): v for k, v in iptc_info._data.items()}
        
        # Remove the temporary file
        os.unlink(temp_file_path)
        
        logger.info(f"Extracted IPTC data: {iptc_data}")
    except Exception as iptc_error:
        logger.error(f"IPTC extraction error: {str(iptc_error)}")
        logger.error(f"IPTC error type: {type(iptc_error)}")
    return iptc_data


def is_safe_file_path(file_path):
    """
    Custom validation function for file paths.
    """
    # Check if the file exists and is a file (not a directory)
    if not os.path.isfile(file_path):
        return False
    
    # Check if the file is within the allowed directory (e.g., /tmp)
    allowed_dir = "/tmp"
    if not os.path.abspath(file_path).startswith(allowed_dir):
        return False
    
    # Check for allowed characters
    allowed_chars = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_/.-")
    if not all(char in allowed_chars for char in file_path):
        return False
    
    return True

def extract_exif_data(temp_file_path):
    try:
        logger.info(f"Starting EXIF extraction from {temp_file_path}")

        if not is_safe_file_path(temp_file_path):
            logger.error(f"Invalid or unsafe file path: {temp_file_path}")
            return {}

        # Use the exiftool binary from the Lambda layer
        exiftool_path = "/opt/bin/exiftool"

        # Construct the command as a list of arguments
        command = [exiftool_path, "-json", "-fast", temp_file_path]

        # Run the command
        # The use of subprocess.run here is safe because:
        # - temp_file_path is generated internally and validated.
        # - We are using shell=False and passing the command as a list.
        # - There is no user-controlled input that could lead to command injection.
        # nosemgrep: python.lang.security.dangerous-subprocess-use.dangerous-subprocess-use-audit
        
        # semgrep-disable
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True,
            shell=False
        )
        # semgrep-enable

        if result.stderr:
            logger.warning(f"ExifTool stderr: {result.stderr}")

        if result.stdout:
            exif_data = json.loads(result.stdout)[0]
            logger.info(f"Extracted EXIF data: {exif_data}")
            return exif_data
        else:
            logger.warning("No EXIF data extracted")
            return {}

    except subprocess.CalledProcessError as e:
        logger.error(f"ExifTool process error: {e}")
        return {}
    except json.JSONDecodeError as e:
        logger.error(f"JSON parsing error: {e}")
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
        with tempfile.NamedTemporaryFile(mode='wb', delete=True, dir=tempfile.gettempdir()) as temp_file:
            logger.info(f"Creating temporary file: {temp_file.name}")
            temp_file.write(image_content)
            temp_file.flush()

            logger.info(f"Temporary file created, size: {os.path.getsize(temp_file.name)}")

            # Extract EXIF data using ExifTool binary
            exif_data = extract_exif_data(temp_file.name)

            # Extract IPTC data
            iptc_data = extract_iptc_data(image_content)

        logger.info("Temporary file automatically removed")

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

        # complete_metadata = {
          
        #     "CustomMetadata": extracted_metadata,
        # }
        # converted_metadata = convert_floats_to_decimals(complete_metadata)
        # marshalled_custom_metadata = {"M": marshall_json_item(converted_metadata)}

        # Initialize DynamoDB client
        dynamodb = boto3.client("dynamodb")

        # Get the existing item from DynamoDB
        try:
            response = dynamodb.get_item(
                TableName=os.environ["MEDIALAKE_ASSET_TABLE"],
                Key={"InventoryID": {"S": inventory_id}}
            )
            existing_item = response.get('Item', {})
            existing_metadata = existing_item.get('Metadata', {'M': {}})['M']
        except Exception as db_error:
            logger.error(f"Failed to get item from DynamoDB: {str(db_error)}")
            raise


        # Prepare the new CustomMetadata
        new_custom_metadata = {"CustomMetadata": extracted_metadata}
        converted_new_metadata = convert_floats_to_decimals(new_custom_metadata)
        marshalled_new_metadata = marshall_json_item(converted_new_metadata)
       

        # Combine existing metadata with new CustomMetadata
        existing_metadata.update(marshalled_new_metadata)

        # Update DynamoDB
        try:
            response = dynamodb.update_item(
                TableName=os.environ["MEDIALAKE_ASSET_TABLE"],
                Key={"InventoryID": {"S": inventory_id}},
                UpdateExpression="SET Metadata = :Metadata",
                ExpressionAttributeValues={":Metadata": {"M": existing_metadata}},
                ReturnValues="UPDATED_NEW",
            )
            logger.info(f"Successfully updated DynamoDB item: {response}")
        except Exception as db_error:
            logger.error(f"Failed to update DynamoDB: {str(db_error)}")
            raise

        return {
            "statusCode": 200,
            "body": { "inventoryId": inventory_id},
        }

    except Exception as e:
        logger.error(f"Lambda handler error: {str(e)}")
        logger.error(f"Error type: {type(e)}")
        return {"statusCode": 500, "body": f"Error extracting image metadata: {str(e)}"}
