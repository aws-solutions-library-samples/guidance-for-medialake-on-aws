import decimal
import io
import json
import os
import shutil
import subprocess
import tempfile

import boto3
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext
from lambda_middleware import lambda_middleware
from PIL import ExifTags, Image

logger = Logger()
tracer = Tracer()

s3 = boto3.client("s3")
dynamo = boto3.resource("dynamodb").Table(os.environ["MEDIALAKE_ASSET_TABLE"])

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def convert_svg_to_png(svg_data: bytes) -> bytes:
    """Convert SVG → PNG using the resvg CLI shipped in a Lambda layer."""
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
            except Exception:
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
            return f.read()
    finally:
        for p in (svg_path, png_path):
            try:
                os.unlink(p)
            except Exception:
                pass


def get_image_rotation(image: Image.Image) -> int:
    """Read EXIF orientation tag and return the rotation angle."""
    try:
        exif = image._getexif() or {}
        key = next(k for k, v in ExifTags.TAGS.items() if v == "Orientation")
        return {1: 0, 3: 180, 6: 270, 8: 90}.get(exif.get(key, 1), 0)
    except Exception as e:
        logger.warning(f"Error reading EXIF orientation: {e}")
        return 0


def create_thumbnail(
    img: Image.Image, w: int, h: int, crop: bool = False
) -> Image.Image:
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


def create_proxy(img: Image.Image) -> Image.Image:
    rot = get_image_rotation(img)
    return img.rotate(rot, expand=True) if rot else img


def clean_asset_id(input_string: str) -> str:
    parts = input_string.split(":")
    uuid = parts[-1] if parts[-1] != "master" else parts[-2]
    return f"asset:uuid:{uuid}"


def _raise(msg: str):
    raise ValueError(msg)


def _resolve_dims(w, h, iw, ih):
    if w is None:
        w = int(h * (iw / ih))
    elif h is None:
        h = int(w * (ih / iw))
    return int(w), int(h)


def _extract_from_event(event: dict):
    payload = event.get("payload", {})
    assets = payload.get("assets") or _raise("Missing payload.assets")
    asset = assets[0]
    mode = payload.get("mode", "proxy")
    width = payload.get("width")
    height = payload.get("height")
    crop = bool(payload.get("crop", False))
    return asset, mode, width, height, crop


def _strip_decimals(obj):
    if isinstance(obj, list):
        return [_strip_decimals(v) for v in obj]
    if isinstance(obj, dict):
        return {k: _strip_decimals(v) for k, v in obj.items()}
    if isinstance(obj, decimal.Decimal):
        return int(obj) if obj % 1 == 0 else float(obj)
    return obj


# ---------------------------------------------------------------------------
# Lambda handler
# ---------------------------------------------------------------------------

JPEG_QUALITY = int(os.getenv("JPEG_QUALITY", "85"))


@lambda_middleware(event_bus_name=os.environ.get("EVENT_BUS_NAME", "default-event-bus"))
@logger.inject_lambda_context
@tracer.capture_lambda_handler
def lambda_handler(event, context: LambdaContext):
    # ── parse event --------------------------------------------------------
    asset, mode, width, height, crop = _extract_from_event(event)

    dsa = asset["DigitalSourceAsset"]
    loc = dsa["MainRepresentation"]["StorageInfo"]["PrimaryLocation"]
    bucket = loc.get("Bucket") or _raise("PrimaryLocation.Bucket missing")
    key = loc.get("ObjectKey", {}).get("FullPath") or _raise(
        "PrimaryLocation.ObjectKey.FullPath missing"
    )
    inv_id = asset.get("InventoryID") or _raise("InventoryID missing")

    out_bucket = os.environ.get("MEDIA_ASSETS_BUCKET_NAME") or _raise(
        "MEDIA_ASSETS_BUCKET_NAME missing"
    )

    # ── fetch source -------------------------------------------------------
    body = s3.get_object(Bucket=bucket, Key=key)["Body"].read()
    if key.lower().endswith(".svg"):
        body = convert_svg_to_png(body)

    img = Image.open(io.BytesIO(body))

    # ── process image ------------------------------------------------------
    if mode == "thumbnail":
        if width is None and height is None:
            _raise("Both width and height cannot be None for thumbnail")
        width, height = _resolve_dims(width, height, img.width, img.height)
        proc = create_thumbnail(img, width, height, crop=crop)
    elif mode == "proxy":
        proc = create_proxy(img)
        width, height = proc.size
    else:
        _raise(f"Invalid mode: {mode}")

    # -------------------------------------------------------------------
    # Choose an efficient output encoding to avoid huge files
    # -------------------------------------------------------------------
    has_alpha = proc.mode in ("RGBA", "LA") or ("transparency" in proc.info)

    if has_alpha:
        ext, fmt = "png", "PNG"
        save_kwargs = dict(optimize=True, compress_level=9)
        if proc.mode not in ("RGBA", "LA"):
            proc = proc.convert("RGBA")
    else:
        ext, fmt = "jpg", "JPEG"
        save_kwargs = dict(quality=JPEG_QUALITY, optimize=True, progressive=True)
        if proc.mode != "RGB":
            proc = proc.convert("RGB")

    # ── encode ------------------------------------------------------------
    buf = io.BytesIO()
    proc.save(buf, format=fmt, **save_kwargs)
    data = buf.getvalue()

    # build a new key alongside the source asset
    stem = key.rsplit(".", 1)[0]
    new_key = f"{stem}_{mode}.{ext}"

    # ── fetch existing representations -----------------------------------
    resp = dynamo.get_item(Key={"InventoryID": clean_asset_id(inv_id)})
    existing = resp.get("Item", {}).get("DerivedRepresentations", [])
    to_delete = [r for r in existing if r.get("Purpose") == mode]
    cur_reps = [r for r in existing if r.get("Purpose") != mode]

    # ── upload new image ---------------------------------------------------
    content_type = f"image/{'jpeg' if fmt == 'JPEG' else 'png'}"
    s3.put_object(
        Bucket=out_bucket,
        Key=new_key,
        Body=data,
        ContentType=content_type,
    )

    # ── delete superseded reps -------------------------------------------
    for old in to_delete:
        ob = old["StorageInfo"]["PrimaryLocation"]["Bucket"]
        ok = old["StorageInfo"]["PrimaryLocation"]["ObjectKey"]["FullPath"]
        try:
            s3.delete_object(Bucket=ob, Key=ok)
            logger.info(
                "Deleted old representation",
                extra={"mode": mode, "bucket": ob, "key": ok},
            )
        except Exception as err:
            logger.warning(
                "Failed to delete old representation",
                extra={"error": str(err), "bucket": ob, "key": ok},
            )

    # ── update DynamoDB ----------------------------------------------------
    new_rep = {
        "ID": f"{clean_asset_id(inv_id)}:{mode}",
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
                "FileInfo": {"Size": len(data)},
            }
        },
        **(
            {"ImageSpec": {"Resolution": {"Width": width, "Height": height}}}
            if mode == "thumbnail"
            else {}
        ),
    }

    try:
        dynamo.update_item(
            Key={"InventoryID": clean_asset_id(inv_id)},
            UpdateExpression="SET DerivedRepresentations = :dr",
            ExpressionAttributeValues={":dr": cur_reps + [new_rep]},
        )
        updated_item = dynamo.get_item(Key={"InventoryID": clean_asset_id(inv_id)})[
            "Item"
        ]
    except Exception:
        logger.exception("Error updating DynamoDB")
        raise

    # ── response ----------------------------------------------------------
    return {
        "statusCode": 200,
        "body": json.dumps(
            {
                "bucket": out_bucket,
                "key": new_key,
                "mode": mode,
                "format": fmt,
                "updatedAsset": _strip_decimals(updated_item),
            }
        ),
    }
