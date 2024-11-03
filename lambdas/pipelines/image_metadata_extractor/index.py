import os
import boto3
import hashlib
import time
import uuid
from PIL import Image
from PIL.ExifTags import TAGS
from iptcinfo3 import IPTCInfo
from io import BytesIO
from pymediainfo import MediaInfo
import json
from aws_lambda_powertools import Logger

# Initialize the logger
logger = Logger(service="imageMetadataExtractor")

# Initialize the event bus client
s3 = boto3.client("s3")


def extract_iptc_data(image_content):
    iptc_data = {}
    try:
        iptc_info = IPTCInfo(BytesIO(image_content))
        if hasattr(iptc_info, "data"):
            iptc_data = {key: value for key, value in iptc_info.data.items() if value}
    except Exception as iptc_error:
        print(f"IPTC extraction error: {str(iptc_error)}")
    return iptc_data

def extract_exif_data(img):
    exif_data = {}
    if hasattr(img, "_getexif") and callable(img._getexif):
        exif = img._getexif()
        if exif:
            exif_data = {
                TAGS.get(tag, tag): value for tag, value in exif.items() if tag in TAGS
            }
    return exif_data


def process_image_file(bucket, key):
    try:
        # Retrieve the image from S3
        response = s3.get_object(Bucket=bucket, Key=key)
        image_content = response["Body"].read()

        # Open the image using PIL
        img = Image.open(BytesIO(image_content))

        # Extract EXIF data
        exif_data = extract_exif_data(img)

        # Extract IPTC data
        iptc_data = extract_iptc_data(image_content)

        # Combine EXIF and IPTC data
        metadata = {"EXIF": exif_data, "IPTC": iptc_data}
        logger.info("Extracted metadata: %s", metadata)  # {{ edit_5 }}

        return metadata

    except Exception as e:
        logger.error("Error processing image file: %s", str(e))  # {{ edit_6 }}
        return None


def lambda_handler(event, context):
    logger.info("Received event: %s", event)
    
    # Extract information from the input section of the event
    input_data = event.get('input', {})
    source_location = input_data.get('sourceLocation', {})
    
    bucket = source_location.get('bucket')
    key = source_location.get('path')
    pipeline_id = event.get('pipeline_id')


    if not bucket or not key:
        logger.error(
            "Invalid event format: missing bucket or key information"
        )  # {{ edit_4 }}
        return

    try:


        if metadata:
            return process_image_file(bucket, key)
    
              # Return the processed image information
        return {
            'statusCode': 200,
            'body': {
                'metadata': metadata
            }
        }

    except Exception as e:
        return {
            'statusCode': 500,
            'body': f'Error extracting image metadata: {str(e)}'
        }












