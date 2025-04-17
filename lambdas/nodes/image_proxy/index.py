import boto3
from PIL import Image, ExifTags
import io
import os
import cairosvg
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext

logger = Logger()
tracer = Tracer()

def get_image_rotation(image):
    try:
        exif = image._getexif()
        if not exif:
            return 0
        orientation_key = next(
            (k for k, v in ExifTags.TAGS.items() if v == "Orientation"),
            None
        )
        orientation = exif.get(orientation_key, 1)
        return {1: 0, 3: 180, 6: 270, 8: 90}.get(orientation, 0)
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
            new_w = int(height * img_ratio)
            img = img.resize((new_w, height))
            left = (new_w - width) // 2
            img = img.crop((left, 0, left + width, height))
        else:
            new_h = int(width / img_ratio)
            img = img.resize((width, new_h))
            top = (new_h - height) // 2
            img = img.crop((0, top, width, top + height))
    else:
        img.thumbnail((width, height))
    return img

def create_proxy(img):
    rotation = get_image_rotation(img)
    return img.rotate(rotation, expand=True) if rotation else img

def clean_asset_id(input_string: str) -> str:
    parts = input_string.split(":")
    uuid = parts[-1] if parts[-1] != "master" else parts[-2]
    return f"asset:uuid:{uuid}"

@logger.inject_lambda_context
@tracer.capture_lambda_handler
def lambda_handler(event, context: LambdaContext):
    # DynamoDB table and S3 client
    table = boto3.resource("dynamodb").Table(os.environ["MEDIALAKE_ASSET_TABLE"])
    s3 = boto3.client("s3")

    # extract parameters
    inv = event.get("input", {}).get("InventoryID") or _raise("Missing InventoryID")
    key = (
        event.get("input", {})
             .get("DigitalSourceAsset", {})
             .get("MainRepresentation", {})
             .get("StorageInfo", {})
             .get("PrimaryLocation", {})
             .get("ObjectKey", {})
             .get("FullPath")
    ) or _raise("Missing key parameter")
    bucket = (
        event.get("input", {})
             .get("DigitalSourceAsset", {})
             .get("MainRepresentation", {})
             .get("StorageInfo", {})
             .get("PrimaryLocation", {})
             .get("Bucket")
    ) or _raise("Missing bucket parameter")
    out_bucket = event.get("output_bucket") or _raise("Missing output_bucket parameter")
    mode = event.get("mode", "proxy")

    # fetch image bytes
    body = s3.get_object(Bucket=bucket, Key=key)["Body"].read()

    # open image (convert SVG→PNG if needed)
    if key.lower().endswith(".svg"):
        png_bytes = cairosvg.svg2png(bytestring=body)
        img = Image.open(io.BytesIO(png_bytes))
    else:
        img = Image.open(io.BytesIO(body))

    # process image
    if mode == "thumbnail":
        w = event.get("width")
        h = event.get("height")
        if w is None and h is None:
            _raise("Both width and height cannot be None for thumbnail")
        w, h = _resolve_dims(w, h, img.width, img.height)
        proc = create_thumbnail(img, w, h, crop=bool(event.get("crop", False)))
        ext, fmt = "png", "PNG"
    elif mode == "proxy":
        proc = create_proxy(img)
        w, h = proc.size
        ext, fmt = "png", "PNG"
    else:
        _raise(f"Invalid mode parameter: {mode}")

    # save & upload
    new_key = f"{bucket}/{key.rsplit('.', 1)[0]}_{mode}.{ext}"
    buf = io.BytesIO()

    # ** CONVERSION FIX: ensure PNG‑compatible mode **
    if proc.mode not in ("RGB", "RGBA"):
        proc = proc.convert("RGB")

    proc.save(buf, format=fmt)
    data = buf.getvalue()
    s3.put_object(
        Bucket=out_bucket,
        Key=new_key,
        Body=data,
        ContentType=f"image/{ext}"
    )

    # update DynamoDB with new representation
    try:
        table.update_item(
            Key={"InventoryID": clean_asset_id(inv)},
            UpdateExpression=(
                "SET DerivedRepresentations = list_append("
                "if_not_exists(DerivedRepresentations, :empty), :r)"
            ),
            ExpressionAttributeValues={
                ":r": [{
                    "ID": f"{clean_asset_id(inv)}:{mode}",
                    "Type": "Image",
                    "Format": fmt,
                    "Purpose": mode,
                    "StorageInfo": {
                        "PrimaryLocation": {
                            "StorageType": "s3",
                            "Provider": "aws",
                            "Bucket": out_bucket,
                            "ObjectKey": {"FullPath": new_key},
                            "Status": "active",
                            "FileInfo": {"Size": len(data)}
                        }
                    },
                    **(
                        {"ImageSpec": {"Resolution": {"Width": w, "Height": h}}}
                        if mode == "thumbnail"
                        else {}
                    )
                }],
                ":empty": []
            }
        )
    except Exception:
        logger.exception("Error updating DynamoDB")
        raise

    return {
        "statusCode": 200,
        "body": {
            "bucket": out_bucket,
            "key": new_key,
            "mode": mode,
            "format": fmt
        }
    }

def _raise(msg: str):
    raise ValueError(msg)

def _resolve_dims(w, h, iw, ih):
    if w is None:
        w = int(h * (iw / ih))
    elif h is None:
        h = int(w * (ih / iw))
    return int(w), int(h)
