#!/bin/bash
set -euo pipefail

BASE_DIR=$(pwd)
LAYER_DIR=$BASE_DIR/dist/lambdas/layers/openexr

echo "Building OpenEXR layer..."
echo "Working directory: $BASE_DIR"
echo "Layer directory: $LAYER_DIR"

# Create the directory structure
mkdir -p $LAYER_DIR/python
mkdir -p $LAYER_DIR/lib
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

echo "Running Docker container to build OpenEXR layer..."
docker run --rm \
  -v $LAYER_DIR:/asset-output \
  public.ecr.aws/amazonlinux/amazonlinux:2023 \
  /bin/bash -c "
    set -euo pipefail

    echo 'Inside Docker container, installing dependencies...'
    yum -y update
    yum -y install python3.12 python3.12-pip findutils

    echo 'Installing OpenEXR for Lambda Python 3.12 with platform-specific wheels...'
    mkdir -p /asset-output/python

    # Try to install with exact platform specification for Lambda Python 3.12
    # Use Python 3.12's pip to install packages for Lambda Python 3.12
    if python3.12 -m pip install \
      --platform manylinux_2_28_x86_64 \
      --target /asset-output/python \
      --implementation cp \
      --python-version 3.12 \
      --only-binary=:all: \
      OpenEXR==3.4.4 2>/dev/null; then
        echo 'Successfully installed OpenEXR from pre-built wheel'
    else
        echo 'Pre-built wheel not available for manylinux_2_28, trying manylinux2014...'
        if python3.12 -m pip install \
          --platform manylinux2014_x86_64 \
          --target /asset-output/python \
          --implementation cp \
          --python-version 3.12 \
          --only-binary=:all: \
          OpenEXR==3.4.4 2>/dev/null; then
            echo 'Successfully installed OpenEXR from manylinux2014 wheel'
        else
            echo 'No compatible wheel found, building OpenEXR from source...'
            yum -y install python3.12-devel gcc-c++ cmake make \
                zlib-devel openexr-devel openexr-libs imath-devel \
                git tar gzip wget

            python3.12 -m pip install OpenEXR==3.4.4 --no-binary OpenEXR -t /asset-output/python

            echo 'Copying required shared libraries...'
            mkdir -p /asset-output/lib
            cp -P /usr/lib64/libOpenEXR*.so* /asset-output/lib/ || echo 'No OpenEXR libs found'
            cp -P /usr/lib64/libImath*.so* /asset-output/lib/ || echo 'No Imath libs found'
            cp -P /usr/lib64/libIex*.so* /asset-output/lib/ || echo 'No Iex libs found'
            cp -P /usr/lib64/libIlmThread*.so* /asset-output/lib/ || echo 'No IlmThread libs found'
        fi
    fi

    echo 'Cleanup to reduce size...'
    cd /asset-output

    # Remove only clearly unnecessary files from Python packages
    find python -type d -name \"__pycache__\" -exec rm -rf {} + || true
    find python -name \"*.pyc\" -delete || true
    find python -name \"*.pyo\" -delete || true

    # Remove tests, docs, examples
    find python -type d -name \"tests\" -exec rm -rf {} + || true
    find python -type d -name \"test\" -exec rm -rf {} + || true
    find python -type d -name \"doc\" -exec rm -rf {} + || true
    find python -type d -name \"docs\" -exec rm -rf {} + || true
    find python -type d -name \"examples\" -exec rm -rf {} + || true
    find python -type d -name \"benchmarks\" -exec rm -rf {} + || true

    # Remove setup/build artifacts that might confuse imports
    find python -name \"setup.py\" -delete || true
    find python -name \"setup.cfg\" -delete || true
    find python -name \"pyproject.toml\" -delete || true
    find python -name \"MANIFEST.in\" -delete || true

    # Remove cmake build artifacts
    find python -type d -name \"CMakeFiles\" -exec rm -rf {} + || true
    find python -name \"CMakeCache.txt\" -delete || true
    find python -name \"cmake_install.cmake\" -delete || true
    find python -name \"Makefile\" -delete || true

    # Remove static libraries (we only need .so files)
    find . -name \"*.a\" -delete || true

    # Strip debug symbols from ALL .so files (this is safe and effective)
    find . -name \"*.so*\" -type f -exec strip --strip-debug {} \\; 2>/dev/null || true

    echo 'Listing copied libraries:'
    ls -la /asset-output/lib/ || echo 'No lib directory'

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

echo "OpenEXR layer built successfully at $LAYER_DIR"
echo "Layer size:"
du -sh $LAYER_DIR
echo "Python directory size:"
du -sh $LAYER_DIR/python
echo "Lib directory size:"
du -sh $LAYER_DIR/lib || echo "No lib directory"
echo "Python packages:"
ls -la $LAYER_DIR/python | head -20
echo "Shared libraries:"
ls -la $LAYER_DIR/lib || echo "No lib directory"
