import decimal
import json
import os
import shutil
import subprocess
import tempfile

import boto3
import numpy as np
import OpenEXR
import pyvips
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext
from lambda_middleware import lambda_middleware
from nodes_utils import generate_derived_filename

MAX_SOURCE_BYTES = int(os.getenv("MAX_SOURCE_BYTES", str(200 * 1024 * 1024)))

logger = Logger()
tracer = Tracer()

s3 = boto3.client("s3")
dynamo = boto3.resource("dynamodb").Table(os.environ["MEDIALAKE_ASSET_TABLE"])


# ---------------------------------------------------------------------------
# Format-specific pre-conversion helpers (unchanged)
# ---------------------------------------------------------------------------


def convert_svg_to_png(svg_data: bytes) -> bytes:
    """Convert SVG → PNG using the resvg CLI shipped in a Lambda layer."""
    with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as svg_file:
        svg_file.write(svg_data)
        svg_path = svg_file.name

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as png_file:
        png_path = png_file.name

    env = os.environ.copy()
    env["PATH"] = "/opt/bin:" + env.get("PATH", "")

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
            raise RuntimeError(
                f"resvg failed (rc={proc.returncode}): {proc.stderr.decode().strip()}"
            )
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


def _ndarray_to_png_bytes(arr: np.ndarray) -> bytes:
    """Encode a uint8 H×W (grayscale) or H×W×C numpy array to PNG bytes via libvips."""
    arr = np.ascontiguousarray(arr)
    if arr.ndim == 2:
        height, width = arr.shape
        bands = 1
    else:
        height, width, bands = arr.shape
    vimg = pyvips.Image.new_from_memory(arr.tobytes(), width, height, bands, "uchar")
    return vimg.write_to_buffer(".png")


def convert_exr_to_png(exr_data: bytes) -> bytes:
    """Convert EXR → PNG using OpenEXR + numpy + pyvips (no Pillow dependency)."""
    with tempfile.NamedTemporaryFile(suffix=".exr", delete=False) as exr_file:
        exr_file.write(exr_data)
        exr_path = exr_file.name

    try:
        with OpenEXR.File(exr_path) as exr:
            channels_dict = exr.channels()

            if "RGB" in channels_dict:
                arr = channels_dict["RGB"].pixels
            elif "RGBA" in channels_dict:
                arr = channels_dict["RGBA"].pixels
            elif "Y" in channels_dict:
                arr = channels_dict["Y"].pixels
            elif all(k in channels_dict for k in ("R", "G", "B")):
                arr = np.dstack(
                    (
                        channels_dict["R"].pixels,
                        channels_dict["G"].pixels,
                        channels_dict["B"].pixels,
                    )
                )
            else:
                raise ValueError(
                    f"Unsupported EXR channel configuration: {list(channels_dict.keys())}"
                )

        arr = np.clip(arr * 255.0, 0, 255).astype(np.uint8)
        return _ndarray_to_png_bytes(arr)
    finally:
        try:
            os.unlink(exr_path)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# pyvips-based image processing
# ---------------------------------------------------------------------------


def _load_with_pyvips(body: bytes, key: str) -> pyvips.Image:
    """
    Decode image bytes via libvips and normalise to a usable RGB(A) sRGB image.

    Handles:
      * EXIF orientation (autorot)
      * Multi-channel TIFFs (>4 bands) by keeping the first 3 bands as RGB
      * ICC profile transform to sRGB when applicable
    """
    load_options = {"access": "random"}

    if key.lower().endswith((".tif", ".tiff")):
        load_options["unlimited"] = True

    img = pyvips.Image.new_from_buffer(body, "", **load_options)
    img = img.autorot()

    if img.bands > 4:
        # Multi-channel TIFF (e.g., 15-band Photoshop spot/layered TIFF).
        # libtiff loads all bands; we keep the first 3 as RGB and re-tag
        # interpretation so subsequent operations behave.
        logger.warning("Image has %d bands; trimming to first 3 (RGB)", img.bands)
        img = img.extract_band(0, n=3).copy(interpretation="srgb")
    elif img.get_typeof("icc-profile-data") != 0:
        # Standard 1–4 band image with embedded ICC profile.
        try:
            img = img.icc_transform("srgb")
        except (pyvips.Error, AttributeError) as e:
            # AttributeError = libvips built without LCMS support (icc_transform not registered)
            logger.warning("ICC transform to sRGB unavailable; continuing: %s", e)

    # Make sure final pixels live in sRGB space (handles grayscale → RGB,
    # noop for already-sRGB images).
    img = img.colourspace("srgb")
    return img


def _resize_image(img: pyvips.Image, w: int, h: int, crop: bool) -> pyvips.Image:
    """
    Resize for thumbnail.
      * crop=False : contain-fit within (w,h) preserving aspect ratio (no upscale).
      * crop=True  : cover-fit and centre-crop to exactly (w,h) (may upscale).
    """
    if w < 1 or h < 1:
        raise ValueError(f"Invalid thumbnail size {w}x{h}")

    if crop:
        scale = max(w / img.width, h / img.height)
        scaled = img.resize(scale)
        left = max(0, (scaled.width - w) // 2)
        top = max(0, (scaled.height - h) // 2)
        return scaled.crop(left, top, min(w, scaled.width), min(h, scaled.height))

    # contain-fit, never upscale
    scale = min(w / img.width, h / img.height, 1.0)
    if scale >= 1.0:
        return img
    return img.resize(scale)


def _encode(img: pyvips.Image, jpeg_quality: int):
    """Encode RGBA → PNG, RGB → JPEG. Returns (bytes, ext, fmt_label)."""
    if img.hasalpha():
        # Ensure we have RGBA (4 bands) for PNG with alpha
        if img.bands == 2:  # gray + alpha → RGBA
            img = img.colourspace("srgb")
        elif img.bands == 3:
            img = img.bandjoin(255)
        buf = img.write_to_buffer(".png[compression=9,strip]")
        return buf, "png", "PNG"

    # No alpha → JPEG
    if img.bands == 1:
        img = img.colourspace("srgb")
    elif img.bands > 3:
        img = img.extract_band(0, n=3)

    buf = img.write_to_buffer(f".jpg[Q={jpeg_quality},strip]")
    return buf, "jpg", "JPEG"


# ---------------------------------------------------------------------------
# Existing helpers (unchanged)
# ---------------------------------------------------------------------------


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
    # Handle both event structures:
    # 1. New structure: event.assets (from Step Functions)
    # 2. Old structure: event.payload.assets (from direct invocation)
    if "assets" in event:
        assets = event.get("assets") or _raise("Missing assets")
        asset = assets[0]
        mode = event.get("mode", "proxy")
        width = event.get("width")
        height = event.get("height")
        crop = bool(event.get("crop", False))
    else:
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
        try:
            if obj == obj.to_integral_value():
                return int(obj)
            return float(obj)
        except Exception:
            return str(obj)
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
    head = s3.head_object(Bucket=bucket, Key=key)

    if head["ContentLength"] > MAX_SOURCE_BYTES:
        raise ValueError(
            f"Asset too large for proxy processing: "
            f"{head['ContentLength']} bytes > {MAX_SOURCE_BYTES} bytes"
        )

    body = s3.get_object(Bucket=bucket, Key=key)["Body"].read()
    if key.lower().endswith(".svg"):
        body = convert_svg_to_png(body)
    elif key.lower().endswith(".exr"):
        body = convert_exr_to_png(body)

    img = _load_with_pyvips(body, key)

    # ── process image ------------------------------------------------------
    if mode == "thumbnail":
        if width is None and height is None:
            _raise("Both width and height cannot be None for thumbnail")
        width, height = _resolve_dims(width, height, img.width, img.height)
        proc = _resize_image(img, width, height, crop=crop)
    elif mode == "proxy":
        proc = img
        width, height = proc.width, proc.height
    else:
        _raise(f"Invalid mode: {mode}")

    # ── encode -------------------------------------------------------------
    data, ext, fmt = _encode(proc, JPEG_QUALITY)
    content_type = f"image/{'jpeg' if fmt == 'JPEG' else 'png'}"

    # build a new key alongside the source asset (include source bucket as prefix)
    new_key = f"{bucket}/{generate_derived_filename(key, mode, ext)}"

    # ── fetch existing representations ------------------------------------
    resp = dynamo.get_item(Key={"InventoryID": clean_asset_id(inv_id)})
    existing = resp.get("Item", {}).get("DerivedRepresentations", [])
    to_delete = [r for r in existing if r.get("Purpose") == mode]
    cur_reps = [r for r in existing if r.get("Purpose") != mode]

    # ── upload new image --------------------------------------------------
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

    # ── update DynamoDB ---------------------------------------------------
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
