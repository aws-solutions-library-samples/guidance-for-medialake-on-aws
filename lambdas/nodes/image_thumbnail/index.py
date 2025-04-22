import boto3
from PIL import Image, ExifTags
import io
import os
import sys
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext
from boto3.dynamodb.conditions import Key
import cairosvg
# Initialize Powertools
logger = Logger()
tracer = Tracer()



def get_image_rotation(image):
    try:
        exif = image._getexif()
        if not exif:
            return 0
        orientation_key = next(
            (key for key, value in ExifTags.TAGS.items() if value == "Orientation"),
            None,
        )
        if not orientation_key or orientation_key not in exif:
            return 0
        orientation = exif[orientation_key]
        rotation_map = {
            1: 0,
            3: 180,
            6: 270,
            8: 90,
        }
        return rotation_map.get(orientation, 0)
    except Exception as e:
        logger.warning(f"Error getting image rotation: {e}")
        return 0

def create_thumbnail(img, width, height, crop=False):
    rotation = get_image_rotation(img)
    if rotation:
        img = img.rotate(rotation, expand=True)

    if crop:
        target_ratio = width / height
        img_ratio = img.width / img.height
        if img_ratio > target_ratio:
            new_width = int(height * img_ratio)
            img = img.resize((new_width, height))
            left = (new_width - width) // 2
            img = img.crop((left, 0, left + width, height))
        else:
            new_height = int(width / img_ratio)
            img = img.resize((width, new_height))
            top = (new_height - height) // 2
            img = img.crop((0, top, width, top + height))
    else:
        img.thumbnail((width, height))

    return img

def strip_after_last_colon(input_string: str) -> str:
    return input_string.rsplit(":", 1)[0]

def clean_asset_id(input_string: str) -> str:
    parts = input_string.split(":")
    uuid = parts[-1]
    if uuid == "master":
        uuid = parts[-2]
    return f"asset:uuid:{uuid}"

@logger.inject_lambda_context
@tracer.capture_lambda_handler
def lambda_handler(event, context: LambdaContext):
    table_name = os.environ["MEDIALAKE_ASSET_TABLE"]
    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(table_name)

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

    output_bucket = event.get("output_bucket")
    mode = "thumbnail"  # Always thumbnail mode for this lambda
    width = event.get("width")
    height = event.get("height")
    crop = event.get("crop", False)

    if not key:
        return {"statusCode": 400, "body": "Missing key parameter"}
    if not bucket:
        return {"statusCode": 400, "body": "Missing bucket parameter"}
    if not output_bucket:
        return {"statusCode": 400, "body": "Missing output_bucket parameter"}
    if width is None and height is None:
        return {
            "statusCode": 400,
            "body": "Both width and height cannot be None for thumbnail creation",
        }

    s3 = boto3.client("s3")

    try:
        s3_response = s3.get_object(Bucket=bucket, Key=key)
        image_data = s3_response["Body"].read()

        # Check if the file is an SVG by its extension
        if key.lower().endswith(".svg"):
            # Convert SVG to PNG
            png_data = cairosvg.svg2png(bytestring=image_data)
            img = Image.open(io.BytesIO(png_data))
        else:
            img = Image.open(io.BytesIO(image_data))

        if width is None:
            width = int(height * (img.width / img.height))
        elif height is None:
            height = int(width * (img.height / img.width))
        width = int(width)
        height = int(height)
        
        processed_img = create_thumbnail(img, width, height, crop)
        output_format = "PNG"
        output_extension = "png"

        output_key = f"{bucket}/{key.rsplit('.', 1)[0]}_{mode}.{output_extension}"
        output_buffer = io.BytesIO()
        processed_img.save(output_buffer, format=output_format, lossless=True)
        output_data = output_buffer.getvalue()

        content_type = "image/png"
        asset_id = f"{asset_id}:thumbnail"
        new_representation = {
            "ID": asset_id,
            "Type": "Image",
            "Format": "PNG",
            "Purpose": mode,
            "StorageInfo": {
                "PrimaryLocation": {
                    "StorageType": "s3",
                    "Provider": "aws",
                    "Bucket": output_bucket,
                    "ObjectKey": {"FullPath": output_key},
                    "Status": "active",
                    "FileInfo": {"Size": len(output_data)},
                }
            },
            "ImageSpec": {"Resolution": {"Width": width, "Height": height}},
        }

        s3.put_object(
            Bucket=output_bucket,
            Key=output_key,
            Body=output_data,
            ContentType=content_type,
        )

        try:
            logger.info(
                "Attempting DynamoDB update",
                extra={"inventory_id": clean_inventory_id, "new_representation": new_representation},
            )
            response = table.update_item(
                Key={"InventoryID": clean_inventory_id},
                UpdateExpression="SET #dr = list_append(if_not_exists(#dr, :empty_list), :new_rep)",
                ExpressionAttributeNames={"#dr": "DerivedRepresentations"},
                ExpressionAttributeValues={":new_rep": [new_representation], ":empty_list": []},
                ReturnValues="UPDATED_NEW",
            )
            logger.info("DynamoDB update response", extra={"response": response, "inventory_id": clean_inventory_id})
        except Exception as e:
            logger.exception("Error updating DynamoDB", extra={"inventory_id": clean_inventory_id, "error": str(e), "error_type": type(e).__name__})
            raise

        return {
            "statusCode": 200,
            "body": {
                "ID": asset_id,
                "type": "image",
                "format": "PNG",
                "Purpose": mode,
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
                "mode": mode,
            },
        }

    except Exception as e:
        logger.exception("Error in lambda_handler")
        return {"statusCode": 500, "body": {"error": str(e), "error_type": type(e).__name__}}