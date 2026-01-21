#!/bin/bash
set -euo pipefail

BASE_DIR=$(pwd)
LAYER_DIR=$BASE_DIR/dist/lambdas/layers/numpy

echo "Building NumPy layer..."
echo "Working directory: $BASE_DIR"
echo "Layer directory: $LAYER_DIR"

# Create the directory structure
mkdir -p $LAYER_DIR/python
echo "Created layer directory structure"

# Check if Docker is available
if ! command -v docker &> /dev/null; then
    echo "ERROR: Docker command not found"
    exit 1
fi

echo "Docker is available, pulling image..."
docker pull public.ecr.aws/amazonlinux/amazonlinux:2023 || {
    echo "ERROR: Failed to pull Docker image"
    exit 1
}

echo "Running Docker container to build NumPy layer..."
docker run --rm \
  -v $LAYER_DIR:/asset-output \
  public.ecr.aws/amazonlinux/amazonlinux:2023 \
  /bin/bash -c "
    set -euo pipefail

    echo 'Inside Docker container, installing dependencies...'
    yum -y update
    yum -y install python3.12 python3.12-pip findutils

    echo 'Installing NumPy for Lambda Python 3.12 with platform-specific wheels...'
    mkdir -p /asset-output/python

    # Use Python 3.12's pip to install packages for Lambda Python 3.12
    # Lambda Python 3.12 requires manylinux_2_28_x86_64 wheels
    python3.12 -m pip install \
      --platform manylinux_2_28_x86_64 \
      --target /asset-output/python \
      --implementation cp \
      --python-version 3.12 \
      --only-binary=:all: \
      --upgrade \
      numpy

    echo 'Cleanup to reduce size...'
    cd /asset-output/python

    # Remove only clearly unnecessary files
    find . -type d -name \"__pycache__\" -exec rm -rf {} + || true
    find . -name \"*.pyc\" -delete || true
    find . -name \"*.pyo\" -delete || true

    # Remove tests and docs
    find . -type d -name \"tests\" -exec rm -rf {} + || true
    find . -type d -name \"test\" -exec rm -rf {} + || true
    find . -type d -name \"doc\" -exec rm -rf {} + || true
    find . -type d -name \"docs\" -exec rm -rf {} + || true
    find . -type d -name \"examples\" -exec rm -rf {} + || true

    # Remove setup/build artifacts that might confuse imports
    find . -name \"setup.py\" -delete || true
    find . -name \"setup.cfg\" -delete || true
    find . -name \"pyproject.toml\" -delete || true
    find . -name \"MANIFEST.in\" -delete || true

    # Strip debug symbols from .so files (this is safe and effective)
    find . -name \"*.so*\" -type f -exec strip --strip-debug {} \\; 2>/dev/null || true

    echo 'Docker container work complete'
  " || {
    echo "ERROR: Docker container failed"
    exit 1
}

# Verify the layer was built
if [ ! -d "$LAYER_DIR/python" ]; then
    echo "ERROR: Layer directory not created: $LAYER_DIR/python"
    exit 1
fi

if [ ! "$(ls -A $LAYER_DIR/python)" ]; then
    echo "ERROR: Layer directory is empty: $LAYER_DIR/python"
    exit 1
fi

echo "NumPy layer built successfully at $LAYER_DIR"
echo "Layer size:"
du -sh $LAYER_DIR
echo "Layer contents:"
ls -la $LAYER_DIR/python | head -20
