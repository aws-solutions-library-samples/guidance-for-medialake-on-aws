import boto3
import base64
from PIL import Image
import io
import os
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext
from boto3.dynamodb.conditions import Key

# Initialize Powertools
logger = Logger()
tracer = Tracer()


def create_thumbnail(img, width, height, crop=False):
    """Create a thumbnail, optionally center-cropped"""
    if crop:
        # Existing center-crop logic
        target_ratio = width / height
        img_ratio = img.width / img.height

        if img_ratio > target_ratio:
            # Image is wider than needed
            new_width = int(height * img_ratio)
            new_height = height
            img = img.resize((new_width, new_height))
            left = (new_width - width) // 2
            img = img.crop((left, 0, left + width, height))
        else:
            # Image is taller than needed
            new_width = width
            new_height = int(width / img_ratio)
            img = img.resize((new_width, new_height))
            top = (new_height - height) // 2
            img = img.crop((0, top, width, top + height))
    else:
        # Resize without cropping
        img.thumbnail((width, height))

    return img



def create_proxy(img):
    """Create a proxy image with same dimensions"""
    return img


def strip_after_last_colon(input_string: str) -> str:
    """
    Strips everything after the last colon in a string.
    """
    return input_string.rsplit(":", 1)[0]


def clean_asset_id(input_string: str) -> str:
    """
    Ensures the asset ID has the correct format without duplicates.
    Extracts just the UUID part and adds the proper prefix.
    """
    # Extract the UUID part (assuming it's the last part after any prefixes)
    parts = input_string.split(":")
    uuid = parts[-1]
    # If the last part is 'master', take the part before it
    if uuid == "master":
        uuid = parts[-2]
    return f"asset:uuid:{uuid}"


@logger.inject_lambda_context
@tracer.capture_lambda_handler
def lambda_handler(event, context: LambdaContext):
    # Get DynamoDB table name from environment variable
    table_name = os.environ["MEDIALAKE_ASSET_TABLE"]
    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(table_name)

    # Get the s3_uri and mode from query parameters
    input = event.get("input", {})
    input_data = input.get("DigitalSourceAsset", {})
    inventory_id = input.get("InventoryID")
    clean_inventory_id = clean_asset_id(inventory_id)
    main_representation = input_data.get("MainRepresentation", {})
    master_asset_id = input_data.get("ID")
    asset_id = clean_asset_id(master_asset_id)
    storage_info = main_representation.get("StorageInfo", {})
    PrimaryLocation = storage_info.get("PrimaryLocation", {})
    object_info = PrimaryLocation.get("ObjectKey", {})
    bucket = PrimaryLocation.get("Bucket")
    key = object_info.get("FullPath")

    # Get the output bucket from event
    output_bucket = event.get("output_bucket")

    mode = event.get("mode", "proxy")  # default to proxy mode

    if not key:
        return {"statusCode": 400, "body": "Missing key parameter"}
    if not bucket:
        return {"statusCode": 400, "body": "Missing bucket parameter"}

    if not output_bucket:
        return {"statusCode": 400, "body": "Missing output_bucket parameter"}

    # Initialize S3 client
    s3 = boto3.client("s3")

    try:
        # Fetch the image from S3
        s3_response = s3.get_object(Bucket=bucket, Key=key)
        image_data = s3_response["Body"].read()
        img = Image.open(io.BytesIO(image_data))

    
        if mode == "thumbnail":
            # Get thumbnail parameters
            params = event.get("thumbnail")
            width = event.get("width")
            height = event.get("height")
            crop = event.get("crop", False) 

            # Check if both width and height are None
            if width is None and height is None:
                return {"statusCode": 400, "body": "Both width and height cannot be None for thumbnail creation"}

            # If one dimension is None, calculate it based on the aspect ratio
            if width is None:
                width = int(height * (img.width / img.height))
            elif height is None:
                height = int(width * (img.height / img.width))

            # Ensure width and height are integers
            width = int(width)
            height = int(height)
            
            # Process image
            processed_img = create_thumbnail(img, width, height, crop)

            # Generate output key
            output_key = (
                f"{bucket}/{key.rsplit('.', 1)[0]}_thumbnails_{width}x{height}.webp"
            )

        elif mode == "proxy":
            # Process image
            processed_img = create_proxy(img)
            width, height = img.size
            # Generate output key
            output_key = f"{bucket}/{key.rsplit('.', 1)[0]}_proxy.webp"

        else:
            return {"statusCode": 400, "body": "Invalid mode parameter"}

        # Save the processed image
        output_buffer = io.BytesIO()

        # Save as WebP with appropriate quality
        if mode == "thumbnail":
            processed_img.save(output_buffer, format="WEBP", quality=85)
            asset_id = f"{asset_id}:thumbnail"
            output_data = output_buffer.getvalue()
            new_representation = {
                "ID": asset_id,
                "Type": "Image",
                "Format": "WEBP",
                "Purpose": mode,
                "StorageInfo": {
                    "PrimaryLocation": {
                        "StorageType": "s3",
                        "Provider": "aws",
                        "Bucket": output_bucket,
                        "ObjectKey": {
                            "FullPath": output_key,
                        },
                        "Status": "active",
                        "FileInfo": {
                            "Size": len(output_data),
                        },
                    }
                },
                "ImageSpec": {
                    "Resolution": {"Width": width, "Height": height},
                },
            }
        else:  # proxy mode
            processed_img.save(output_buffer, format="WEBP", quality=90)
            output_data = output_buffer.getvalue()
            asset_id = f"{asset_id}:proxy"
            new_representation = {
                "ID": asset_id,
                "Type": "Image",
                "Format": "WEBP",
                "Purpose": mode,
                "StorageInfo": {
                    "PrimaryLocation": {
                        "StorageType": "s3",
                        "Provider": "aws",
                        "Bucket": output_bucket,
                        "ObjectKey": {
                            "FullPath": output_key,
                        },
                        "Status": "active",
                        "FileInfo": {
                            "Size": len(output_data),
                        },
                    }
                },
            }

        # Upload to output bucket
        s3.put_object(
            Bucket=output_bucket,
            Key=output_key,
            Body=output_data,
            ContentType="image/webp",
        )

        try:
            # Add logging before the update
            logger.info(
                "Attempting DynamoDB update",
                extra={
                    "inventory_id": clean_inventory_id,
                    "new_representation": new_representation,
                },
            )

            # Update DynamoDB
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

            # Add more detailed success logging
            logger.info(
                "DynamoDB update response",
                extra={"response": response, "inventory_id": clean_inventory_id},
            )

        except Exception as e:
            # Enhance error logging
            logger.exception(
                "Error updating DynamoDB",
                extra={
                    "inventory_id": clean_inventory_id,
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
            )
            raise  # Re-raise to ensure we catch all errors

        # Return the processed image information
        return {
            "statusCode": 200,
            "body": {
                "ID": asset_id,
                "type": "image",
                "format": "WEBP",
                "Purpose": mode,
                "StorageInfo": {
                    "PrimaryLocation": {
                        "StorageType": "s3",
                        "Bucket": output_bucket,
                        "path": output_key,
                        "status": "active",
                        "ObjectKey": {
                            "FullPath": output_key,
                        },
                    }
                },
                "location": {
                    "bucket": output_bucket,
                    "key": output_key,
                },
                "mode": mode,
            },
        }

    except Exception as e:
        return {"statusCode": 500, "body": f"Error processing image: {str(e)}"}
