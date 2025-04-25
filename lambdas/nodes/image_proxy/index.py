import boto3, io, os
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

# ── Lambda ──────────────────────────────────────────────────────────────────────
@lambda_middleware(
    event_bus_name=os.environ.get("EVENT_BUS_NAME", "default-event-bus"),
,
)
@logger.inject_lambda_context
@tracer.capture_lambda_handler
def lambda_handler(event, context: LambdaContext):
    """
    Expected event shape (new-only):

    event["payload"]["assets"] = [ { "input": { "detail": {...}, ... } } ]
    """

    asset           = event["payload"]["assets"][0]          # single-asset assumption
    raw_input       = asset["input"]
    detail          = raw_input["detail"]
    dsa             = detail["DigitalSourceAsset"]
    location        = dsa["MainRepresentation"]["StorageInfo"]["PrimaryLocation"]

    bucket          = location.get("Bucket")            or _raise("Missing bucket")
    key             = location.get("ObjectKey", {}).get("FullPath") or _raise("Missing key")
    inv_id          = detail.get("InventoryID")               or _raise("Missing InventoryID")
    mode            = raw_input.get("mode", "proxy")

    out_bucket      = os.environ.get("MEDIA_ASSETS_BUCKET_NAME") or _raise("Missing MEDIA_ASSETS_BUCKET_NAME")

    # ── fetch source ────────────────────────────────────────────────────────────
    body = s3.get_object(Bucket=bucket, Key=key)["Body"].read()
    if key.lower().endswith(".svg"):
        body = cairosvg.svg2png(bytestring=body)

    img = Image.open(io.BytesIO(body))

    # ── process image ───────────────────────────────────────────────────────────
    if mode == "thumbnail":
        w = raw_input.get("width")
        h = raw_input.get("height")
        if w is None and h is None:
            _raise("Both width and height cannot be None for thumbnail")
        w, h = _resolve_dims(w, h, img.width, img.height)
        proc = create_thumbnail(img, w, h, crop=bool(raw_input.get("crop", False)))
    elif mode == "proxy":
        proc = create_proxy(img)
        w, h = proc.size
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

    # ── update DynamoDB ─────────────────────────────────────────────────────────
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
                {"ImageSpec": {"Resolution": {"Width": w, "Height": h}}}
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
        "body": {
            "bucket": out_bucket,
            "key": new_key,
            "mode": mode,
            "format": fmt,
        },
    }
