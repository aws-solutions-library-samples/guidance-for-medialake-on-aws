# thumbnail_step.py
import io
import json
import os
import shutil
import subprocess
import tempfile
from decimal import Decimal

import boto3
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext
from botocore.exceptions import ClientError
from lambda_middleware import lambda_middleware
from PIL import ExifTags, Image

logger = Logger()
tracer = Tracer()

s3 = boto3.client("s3")
dynamo = boto3.resource("dynamodb").Table(os.environ["MEDIALAKE_ASSET_TABLE"])


def convert_svg_to_png(svg_data: bytes) -> bytes:
    """
    Convert SVG → PNG using only the resvg CLI.
    Expects /opt/bin/resvg in your Lambda layer.
    """
    # dump SVG to a temp file
    with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as svg_file:
        svg_file.write(svg_data)
        svg_path = svg_file.name

    # prepare a temp file for the PNG output
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as png_file:
        png_path = png_file.name

    # ensure our layer bins come first
    env = os.environ.copy()
    env["PATH"] = "/opt/bin:" + env.get("PATH", "")

    # verify resvg is present
    if shutil.which("resvg", path=env["PATH"]) is None:
        for p in (svg_path, png_path):
            try:
                os.unlink(p)
            except:
                pass
        raise RuntimeError("resvg CLI not found in /opt/bin")

    cmd = ["resvg", svg_path, png_path]
    logger.info(f"Running: {' '.join(cmd)}")

    try:
        proc = subprocess.run(cmd, env=env, capture_output=True, timeout=30)
        if proc.returncode != 0:
            stderr = proc.stderr.decode().strip()
            raise RuntimeError(f"resvg failed (rc={proc.returncode}): {stderr}")

        if not os.path.exists(png_path) or os.path.getsize(png_path) == 0:
            raise RuntimeError("resvg did not produce any output")

        with open(png_path, "rb") as f:
            data = f.read()
        return data

    finally:
        # always clean up temp files
        for p in (svg_path, png_path):
            try:
                os.unlink(p)
            except:
                pass


def get_image_rotation(image):
    try:
        exif = image._getexif() or {}
        key = next((k for k, v in ExifTags.TAGS.items() if v == "Orientation"), None)
        return {1: 0, 3: 180, 6: 270, 8: 90}.get(exif.get(key, 1), 0)
    except Exception as e:
        logger.warning(f"Error getting image rotation: {e}")
        return 0


def create_thumbnail(img, w, h, crop=False):
    if w < 1 or h < 1:
        raise ValueError(f"Invalid thumbnail size {w}×{h}")
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


def clean_asset_id(raw: str) -> str:
    parts = raw.split(":")
    uuid_part = parts[-1] if parts[-1] != "master" else parts[-2]
    return f"asset:uuid:{uuid_part}"


def _raise(msg: str):
    raise ValueError(msg)


def _resolve_dims(w, h, iw, ih):
    if w is None or w <= 0:
        w = None
    if h is None or h <= 0:
        h = None
    if w is None and h is None:
        return iw, ih
    if w is None:
        w = int(h * (iw / ih))
    elif h is None:
        h = int(w * (ih / iw))
    return max(1, int(w)), max(1, int(h))


def _extract_from_event(event):
    payload = event.get("payload") or _raise("Missing payload")
    assets = payload.get("assets") or _raise("Missing payload.assets")
    asset = assets[0]

    detail = asset
    width = payload.get("width")
    height = payload.get("height")
    crop = bool(payload.get("crop", False))

    return detail, width, height, crop


def _convert_decimals(obj):
    """
    Recursively walk through the returned Dynamo item and convert any
    Decimal to int (if whole) or float.
    """
    if isinstance(obj, list):
        return [_convert_decimals(i) for i in obj]
    if isinstance(obj, dict):
        return {k: _convert_decimals(v) for k, v in obj.items()}
    if isinstance(obj, Decimal):
        # choose int if no fractional part
        if obj % 1 == 0:
            return int(obj)
        return float(obj)
    return obj


@lambda_middleware(
    event_bus_name=os.environ.get("EVENT_BUS_NAME", "default-event-bus"),
)
@logger.inject_lambda_context
@tracer.capture_lambda_handler
def lambda_handler(event, context: LambdaContext):
    detail, width, height, crop = _extract_from_event(event)

    if width is None and height is None:
        width = 300
        height = None

    inv_id = detail.get("InventoryID") or _raise("Missing InventoryID")
    asset_id = clean_asset_id(inv_id)

    loc = detail["DigitalSourceAsset"]["MainRepresentation"]["StorageInfo"][
        "PrimaryLocation"
    ]
    bucket = loc.get("Bucket") or _raise("Missing bucket")
    key = loc.get("ObjectKey", {}).get("FullPath") or _raise("Missing key")

    body = s3.get_object(Bucket=bucket, Key=key)["Body"].read()
    if key.lower().endswith(".svg"):
        body = convert_svg_to_png(body)
    img = Image.open(io.BytesIO(body))

    width, height = _resolve_dims(width, height, img.width, img.height)
    thumb = create_thumbnail(img, width, height, crop=crop)

    fmt, ext = "PNG", "png"
    if thumb.mode not in ("RGB", "RGBA"):
        thumb = thumb.convert("RGB")
    buf = io.BytesIO()
    thumb.save(buf, format=fmt)
    data = buf.getvalue()

    out_bucket = os.environ.get("MEDIA_ASSETS_BUCKET_NAME") or _raise(
        "MEDIA_ASSETS_BUCKET_NAME env-var missing"
    )
    out_key = f"{bucket}/{key.rsplit('.', 1)[0]}_thumbnail.{ext}"

    try:
        s3.delete_object(Bucket=out_bucket, Key=out_key)
        logger.info(
            "Deleted existing thumbnail", extra={"bucket": out_bucket, "key": out_key}
        )
    except ClientError as err:
        logger.warning(
            "No existing thumbnail to delete or delete failed",
            extra={"error": str(err)},
        )

    s3.put_object(Bucket=out_bucket, Key=out_key, Body=data, ContentType=f"image/{ext}")

    # update DynamoDB record
    try:
        resp = dynamo.get_item(Key={"InventoryID": asset_id})
        cur_reps = resp.get("Item", {}).get("DerivedRepresentations", [])
        cur_reps = [r for r in cur_reps if r.get("Purpose") != "thumbnail"]

        new_rep = {
            "ID": f"{asset_id}:thumbnail",
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
            Key={"InventoryID": asset_id},
            UpdateExpression="SET DerivedRepresentations = :dr",
            ExpressionAttributeValues={":dr": cur_reps + [new_rep]},
        )
    except Exception:
        logger.exception("Error updating DynamoDB")
        raise

    # fetch back the updated record and return as updatedAsset
    updated_item = dynamo.get_item(Key={"InventoryID": asset_id})["Item"]
    # Convert any Decimal instances so JSON serialization will work
    updated_item = _convert_decimals(updated_item)

    return {
        "statusCode": 200,
        "body": json.dumps(
            {
                "bucket": out_bucket,
                "key": out_key,
                "mode": "thumbnail",
                "format": fmt,
            }
        ),
        "updatedAsset": updated_item,
    }
