#!/bin/bash
# Smoke test for the image-processing layer's pyvips install.
#
# Installs pyvips using the SAME two-step recipe as build_openexr.sh
# (binary deps via platform wheels, then pure-python pyvips 3.x sdist), into a
# throwaway dir, and runs smoke_test_image_layer.py against it. This validates
# the install recipe itself resolves a working pyvips 3.x on Lambda's platform.
#
# Runs on Amazon Linux 2023 / Python 3.12 (the Lambda runtime). Exits non-zero
# on any failure so CI fails fast instead of shipping a broken layer.
set -euo pipefail

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="$(mktemp -d)"
trap 'rm -rf "${OUT_DIR}"' EXIT

echo "Installing python3.12 toolchain..."
yum -y install python3.12 python3.12-pip findutils >/dev/null 2>&1 || true

echo "Installing pyvips (two-step recipe, matching build_openexr.sh)..."
# 1) binary deps as x86_64 wheels (two --platform tags: pyvips-binary ships
#    manylinux_2_28, cffi only manylinux2014)
python3.12 -m pip install \
  --platform manylinux_2_28_x86_64 \
  --platform manylinux2014_x86_64 \
  --target "${OUT_DIR}" \
  --implementation cp \
  --python-version 3.12 \
  --only-binary=:all: \
  cffi pyvips-binary
# 2) pure-python pyvips 3.x from sdist (--only-binary would fall back to the
#    broken 2.1.0 wheel); --no-deps keeps the x86_64 cffi above
python3.12 -m pip install \
  --target "${OUT_DIR}" \
  --no-deps \
  'pyvips>=3,<4'

echo "Running image layer smoke test..."
IMAGE_LAYER_PYTHON="${OUT_DIR}" python3.12 "${BASE_DIR}/.cicd/smoke_test_image_layer.py"

echo "Image layer smoke test passed."
