#!/usr/bin/env python3
"""
Smoke test for the image-processing Lambda layer (OpenEXR + pyvips).

Purpose
-------
Catch, in CI, the class of regressions that previously reached production and
broke image proxy/thumbnail generation:

  * "cannot import name 'aws_s3vectors'"-style import failures
  * pyvips resolving to an ancient wheel -> "undefined type name VipsCallbackFn"
  * an auto-formatter (isort) reordering the vendored pyvips/__init__.py so that
    `.vconnection` imports before `.vobject` ->
    "partially initialized module 'pyvips' has no attribute 'VipsObject'"

None of the above are caught by linting or unit tests -- they only surface when
`import pyvips` runs at Lambda cold start. This script exercises exactly that
path plus the core proxy/thumbnail image operations, so a broken layer fails the
pipeline instead of shipping.

Usage
-----
    python3 smoke_test_image_layer.py

If the environment variable IMAGE_LAYER_PYTHON is set, that directory is
prepended to sys.path first (point it at the built layer's `python/` dir to test
the real artifact). Otherwise it tests whatever pyvips is importable.

Exit code 0 = pass, non-zero = fail.
"""
import os
import sys

layer_python = os.environ.get("IMAGE_LAYER_PYTHON")
if layer_python:
    sys.path.insert(0, layer_python)
    print(f"[smoke] using layer python dir: {layer_python}")

# --- 1. import + attribute sanity (the exact failure modes we hit) -----------
import pyvips  # noqa: E402

print(
    f"[smoke] pyvips={pyvips.__version__} "
    f"libvips={pyvips.version(0)}.{pyvips.version(1)}.{pyvips.version(2)} "
    f"API_mode={pyvips.API_mode}"
)

# VipsObject must exist (guards against the isort __init__.py reordering bug).
assert hasattr(
    pyvips, "VipsObject"
), "pyvips.VipsObject missing (corrupt import order?)"
# pyvips must be 3.x (guards against the 2.1.0 wheel fallback / VipsCallbackFn bug).
major = int(pyvips.__version__.split(".")[0])
assert major >= 3, f"pyvips must be >=3, got {pyvips.__version__}"


# --- 2. core proxy/thumbnail operations (copied from the node index.py) ------
def _load(body, key):
    opts = {"access": "random"}
    if key.lower().endswith((".tif", ".tiff")):
        opts["unlimited"] = True
    img = pyvips.Image.new_from_buffer(body, "", **opts)
    img = img.autorot()
    if img.bands > 4:
        img = img.extract_band(0, n=3).copy(interpretation="srgb")
    return img.colourspace("srgb")


def _resize(img, w, h, crop):
    if crop:
        scale = max(w / img.width, h / img.height)
        s = img.resize(scale)
        left = max(0, (s.width - w) // 2)
        top = max(0, (s.height - h) // 2)
        return s.crop(left, top, min(w, s.width), min(h, s.height))
    scale = min(w / img.width, h / img.height, 1.0)
    return img if scale >= 1.0 else img.resize(scale)


def _encode(img, q):
    if img.hasalpha():
        if img.bands == 3:
            img = img.bandjoin(255)
        return img.write_to_buffer(".png[compression=9,strip]"), "PNG"
    if img.bands > 3:
        img = img.extract_band(0, n=3)
    return img.write_to_buffer(f".jpg[Q={q},strip]"), "JPEG"


def _make(fmt, w=1200, h=800, alpha=False):
    grad = (pyvips.Image.xyz(w, h)[0] * (255.0 / w)).cast("uchar")
    rgb = grad.bandjoin([grad, grad]).copy(interpretation="srgb")
    if alpha:
        rgb = rgb.bandjoin(128)
    return (rgb.flatten() if fmt == "jpg" else rgb).write_to_buffer(f".{fmt}")


failures = 0

# proxy: full-size, encode as-is
for fmt, alpha in [("jpg", False), ("png", True)]:
    try:
        img = _load(_make(fmt, alpha=alpha), f"a.{fmt}")
        data, label = _encode(img, 85)
        out = pyvips.Image.new_from_buffer(data, "")
        print(
            f"[smoke] proxy src={fmt} alpha={alpha} -> {label} {out.width}x{out.height} OK"
        )
    except Exception as e:  # noqa: BLE001
        print(f"[smoke] FAIL proxy src={fmt} alpha={alpha}: {e}")
        failures += 1

# thumbnail: resize to 300w, always PNG
for crop in (False, True):
    for fmt, alpha in [("jpg", False), ("png", True)]:
        try:
            img = _load(_make(fmt, alpha=alpha), f"a.{fmt}")
            h = max(1, int(300 * img.height / img.width))
            thumb = _resize(img, 300, h, crop)
            if thumb.hasalpha():
                thumb = thumb.flatten(background=[255, 255, 255])
            if thumb.bands > 3:
                thumb = thumb.extract_band(0, n=3)
            data = thumb.write_to_buffer(".png[compression=9,strip]")
            out = pyvips.Image.new_from_buffer(data, "")
            assert out.width <= 301, f"thumb too wide: {out.width}"
            print(
                f"[smoke] thumb crop={crop} src={fmt} alpha={alpha} -> PNG {out.width}x{out.height} OK"
            )
        except Exception as e:  # noqa: BLE001
            print(f"[smoke] FAIL thumb crop={crop} src={fmt} alpha={alpha}: {e}")
            failures += 1

print("[smoke] RESULT:", "PASS" if failures == 0 else "FAIL")
sys.exit(1 if failures else 0)
