import boto3, io, os
from PIL import Image, ExifTags
import cairosvg
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext
from lambda_middleware import lambda_middleware

logger = Logger()
tracer = Tracer()
s3 = boto3.client("s3")
dynamo = boto3.resource("dynamodb").Table(os.environ["MEDIALAKE_ASSET_TABLE"])

# ── helpers ─────────────────────────────────────────────────────────────────────
def get_image_rotation(image):
    try:
        exif = image._getexif() or {}
        key = next((k for k, v in ExifTags.TAGS.items() if v == "Orientation"), None)
        return {1: 0, 3: 180, 6: 270, 8: 90}.get(exif.get(key, 1), 0)
    except Exception as e:
        logger.warning(f"Error getting image rotation: {e}")
        return 0

def create_thumbnail(img, w, h, crop=False):
    rot = get_image_rotation(img)
    if rot:
        img = img.rotate(rot, expand=True)

    if crop:
        tgt_ratio, img_ratio = w / h, img.width / img.height
        if img_ratio > tgt_ratio:
            new_w = int(h * img_ratio)
            img = img.resize((new_w, h))
            left = (new_w - w) // 2
            img = img.crop((left, 0, left + w, h))
        else:
            new_h = int(w / img_ratio)
            img = img.resize((w, new_h))
            top = (new_h - h) // 2
            img = img.crop((0, top, w, top + h))
    else:
        img.thumbnail((w, h))

    return img

def clean_asset_id(input_string: str) -> str:
    parts = input_string.split(":")
    uuid = parts[-1] if parts[-1] != "master" else parts[-2]
    return f"asset:uuid:{uuid}"

def _raise(msg: str):
    raise ValueError(msg)

# ── Lambda ──────────────────────────────────────────────────────────────────────
@lambda_middleware(
    event_bus_name=os.environ.get("EVENT_BUS_NAME", "default-event-bus"),

)
@logger.inject_lambda_context
@tracer.capture_lambda_handler
def lambda_handler(event, context: LambdaContext):
    asset = event["payload"]["assets"][0]
    raw_input = asset["input"]
    detail = raw_input.get("detail", {})

    inv_id = detail.get("InventoryID") or _raise("Missing InventoryID")
    clean_inv = clean_asset_id(inv_id)

    location = detail["DigitalSourceAsset"]["MainRepresentation"]["StorageInfo"]["PrimaryLocation"]
    bucket = location.get("Bucket") or _raise("Missing bucket")
    key = location.get("ObjectKey", {}).get("FullPath") or _raise("Missing key")

    width = raw_input.get("width")
    height = raw_input.get("height")
    crop = bool(raw_input.get("crop", False))

    if width is None and height is None:
        return {
            "statusCode": 400,
            "body": "Both width and height cannot be None for thumbnail creation"
        }

    body = s3.get_object(Bucket=bucket, Key=key)["Body"].read()
    if key.lower().endswith(".svg"):
        body = cairosvg.svg2png(bytestring=body)
    img = Image.open(io.BytesIO(body))

    if width is None:
        width = int(height * (img.width / img.height))
    elif height is None:
        height = int(width * (img.height / img.width))
    width, height = int(width), int(height)

    proc = create_thumbnail(img, width, height, crop)
    fmt, ext = "PNG", "png"
    out_bucket = os.environ.get("MEDIA_ASSETS_BUCKET_NAME") or _raise("Missing MEDIA_ASSETS_BUCKET_NAME")
    out_key = f"{bucket}/{key.rsplit('.', 1)[0]}_thumbnail.{ext}"

    buf = io.BytesIO()
    proc = proc.convert("RGB") if proc.mode not in ("RGB", "RGBA") else proc
    proc.save(buf, format=fmt)
    data = buf.getvalue()
    s3.put_object(Bucket=out_bucket, Key=out_key, Body=data, ContentType=f"image/{ext}")

    try:
        resp = dynamo.get_item(Key={"InventoryID": clean_inv})
        current = resp.get("Item", {}).get("DerivedRepresentations", [])
        filtered = [r for r in current if r.get("Purpose") != "thumbnail"]

        new_rep = {
            "ID": f"{clean_inv}:thumbnail",
            "Type": "Image",
            "Format": fmt,
            "Purpose": "thumbnail",
            "StorageInfo": {
                "PrimaryLocation": {
                    "StorageType": "s3",
                    "Provider": "aws",
                    "Bucket": out_bucket,
                    "ObjectKey": {"FullPath": out_key},
                    "Status": "active",
                    "FileInfo": {"Size": len(data)},
                }
            },
            "ImageSpec": {"Resolution": {"Width": width, "Height": height}},
        }

        dynamo.update_item(
            Key={"InventoryID": clean_inv},
            UpdateExpression="SET DerivedRepresentations = :dr",
            ExpressionAttributeValues={":dr": filtered + [new_rep]},
        )
    except Exception:
        logger.exception("Error updating DynamoDB")
        raise

    return {
        "statusCode": 200,
        "body": {
            "bucket": out_bucket,
            "key": out_key,
            "mode": "thumbnail",
            "format": fmt,
        },
    }
