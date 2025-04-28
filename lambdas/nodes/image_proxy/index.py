import boto3, io, os, json
from PIL import Image, ExifTags
import cairosvg
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext
from lambda_middleware import lambda_middleware

logger  = Logger()
tracer  = Tracer()

s3      = boto3.client("s3")
dynamo  = boto3.resource("dynamodb").Table(os.environ["MEDIALAKE_ASSET_TABLE"])

# ── helpers ─────────────────────────────────────────────────────────────────────
def get_image_rotation(image):
    try:
        exif = image._getexif() or {}
        key  = next((k for k, v in ExifTags.TAGS.items() if v == "Orientation"), None)
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
        if img_ratio > tgt_ratio:           # crop width
            new_w = int(h * img_ratio)
            img   = img.resize((new_w, h))
            left  = (new_w - w) // 2
            img   = img.crop((left, 0, left + w, h))
        else:                               # crop height
            new_h = int(w / img_ratio)
            img   = img.resize((w, new_h))
            top   = (new_h - h) // 2
            img   = img.crop((0, top, w, top + h))
    else:
        img.thumbnail((w, h))

    return img


def create_proxy(img):
    rot = get_image_rotation(img)
    return img.rotate(rot, expand=True) if rot else img


def clean_asset_id(input_string: str) -> str:
    parts = input_string.split(":")
    uuid  = parts[-1] if parts[-1] != "master" else parts[-2]
    return f"asset:uuid:{uuid}"


def _raise(msg):  # tiny helper
    raise ValueError(msg)


def _resolve_dims(w, h, iw, ih):
    if w is None:
        w = int(h * (iw / ih))
    elif h is None:
        h = int(w * (ih / iw))
    return int(w), int(h)


def _extract_from_event(event: dict):
    """
    Returns a tuple:
      (asset_dict, mode, width, height, crop_flag)
    Works with both the “old” and “new” event formats.
    """
    payload = event.get("payload", {})
    assets  = payload.get("assets") or _raise("Missing payload.assets")
    asset   = assets[0]                      # single-asset assumption

    # ── OLD shape ────────────────────────────────────────────────────────────
    if "input" in asset:                    # → asset["input"]["detail"]
        raw_input   = asset["input"]
        detail      = raw_input["detail"]
        mode        = raw_input.get("mode", "proxy")
        width       = raw_input.get("width")
        height      = raw_input.get("height")
        crop        = bool(raw_input.get("crop", False))
    # ── NEW shape (your sample) ──────────────────────────────────────────────
    else:                                   # asset itself is the detail
        detail      = asset
        mode        = payload.get("mode", "proxy")
        width       = payload.get("width")
        height      = payload.get("height")
        crop        = bool(payload.get("crop", False))

    return detail, mode, width, height, crop


# ── Lambda ──────────────────────────────────────────────────────────────────────
@lambda_middleware(
    event_bus_name=os.environ.get("EVENT_BUS_NAME", "default-event-bus"),
)
@logger.inject_lambda_context
@tracer.capture_lambda_handler
def lambda_handler(event, context: LambdaContext):
    """
    Accepts either of these shapes:

    • OLD:
      event["payload"]["assets"][0] = { "input": { "detail": {...}, "mode": … } }

    • NEW (example you posted):
      event["payload"]["assets"][0] = { "InventoryID": …, "DigitalSourceAsset": … }
      Thumbnail / crop settings (if any) are expected at payload-root level.

    """
    # ── pull out the interesting pieces ──────────────────────────────────────
    detail, mode, width, height, crop = _extract_from_event(event)

    dsa      = detail["DigitalSourceAsset"]
    location = dsa["MainRepresentation"]["StorageInfo"]["PrimaryLocation"]

    bucket   = location.get("Bucket") \
               or _raise("DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.Bucket missing")
    key      = location.get("ObjectKey", {}).get("FullPath") \
               or _raise("DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.ObjectKey.FullPath missing")
    inv_id   = detail.get("InventoryID") or _raise("InventoryID missing")

    out_bucket = os.environ.get("MEDIA_ASSETS_BUCKET_NAME") or _raise("MEDIA_ASSETS_BUCKET_NAME env-var missing")

    # ── fetch source ─────────────────────────────────────────────────────────
    body = s3.get_object(Bucket=bucket, Key=key)["Body"].read()
    if key.lower().endswith(".svg"):
        body = cairosvg.svg2png(bytestring=body)

    img = Image.open(io.BytesIO(body))

    # ── process image ────────────────────────────────────────────────────────
    if mode == "thumbnail":
        if width is None and height is None:
            _raise("Both width and height cannot be None for thumbnail")
        width, height = _resolve_dims(width, height, img.width, img.height)
        proc = create_thumbnail(img, width, height, crop=crop)
    elif mode == "proxy":
        proc   = create_proxy(img)
        width, height = proc.size
    else:
        _raise(f"Invalid mode: {mode}")

    # always output PNG
    ext, fmt = "png", "PNG"
    if proc.mode not in ("RGB", "RGBA"):
        proc = proc.convert("RGB")
    buf = io.BytesIO()
    proc.save(buf, format=fmt)
    data = buf.getvalue()

    new_key = f"{bucket}/{key.rsplit('.', 1)[0]}_{mode}.{ext}"
    s3.put_object(Bucket=out_bucket, Key=new_key, Body=data, ContentType=f"image/{ext}")

    # ── update DynamoDB ──────────────────────────────────────────────────────
    try:
        asset_id = clean_asset_id(inv_id)
        resp     = dynamo.get_item(Key={"InventoryID": asset_id})
        cur_reps = resp.get("Item", {}).get("DerivedRepresentations", [])
        if mode == "proxy":
            cur_reps = [r for r in cur_reps if r.get("Purpose") != "proxy"]

        new_rep = {
            "ID": f"{asset_id}:{mode}",
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

        dynamo.update_item(
            Key={"InventoryID": asset_id},
            UpdateExpression="SET DerivedRepresentations = :dr",
            ExpressionAttributeValues={":dr": cur_reps + [new_rep]},
        )
    except Exception:
        logger.exception("Error updating DynamoDB")
        raise

    return {
        "statusCode": 200,
        "body": json.dumps({
            "bucket": out_bucket,
            "key": new_key,
            "mode": mode,
            "format": fmt,
        }),
    }
