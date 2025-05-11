#!/bin/bash

BASE_DIR=$(pwd)
TEMP_DIR=$(mktemp -d)
LAYER_DIR=$BASE_DIR/dist/lambdas/layers/cairosvg

# Create the directory structure
mkdir -p $LAYER_DIR/python
mkdir -p $LAYER_DIR/lib

# Use Docker to build the layer with all dependencies
docker run --rm \
  -v $LAYER_DIR:/asset-output \
  public.ecr.aws/amazonlinux/amazonlinux:2.0.20250305.0-amd64 \
  /bin/bash -c "
    set -e
    # Update packages and install required dependencies using yum
    yum update -y && yum install -y cairo-devel pango-devel gdk-pixbuf2-devel libffi-devel pkg-config python3-pip
    # Upgrade pip (optional, but often helpful)
    python3 -m pip install --upgrade pip
    # Install cairosvg and its dependencies into the python folder
    python3 -m pip install cairosvg -t /asset-output/python
    # Copy native libraries required by CairoSVG and its dependencies
    cp -v /usr/lib64/libcairo.so* /asset-output/lib/ || echo \"Cairo libraries not found in /usr/lib64\"
    cp -v /usr/lib64/libpango-1.0.so* /asset-output/lib/ || echo \"Pango libraries not found in /usr/lib64\"
    cp -v /usr/lib64/libgdk_pixbuf-2.0.so* /asset-output/lib/ || echo \"gdk-pixbuf libraries not found in /usr/lib64\"
    cp -v /usr/lib64/libffi.so* /asset-output/lib/ || echo \"libffi libraries not found in /usr/lib64\"

    # Additional dependencies as determined by ldd
    cp -v /usr/lib64/libpthread.so* /asset-output/lib/ || echo \"libpthread not found in /usr/lib64\"
    cp -v /usr/lib64/libpixman-1.so* /asset-output/lib/ || echo \"libpixman not found in /usr/lib64\"
    cp -v /usr/lib64/libfontconfig.so* /asset-output/lib/ || echo \"libfontconfig not found in /usr/lib64\"
    cp -v /usr/lib64/libfreetype.so* /asset-output/lib/ || echo \"libfreetype not found in /usr/lib64\"
    cp -v /usr/lib64/libEGL.so* /asset-output/lib/ || echo \"libEGL not found in /usr/lib64\"
    cp -v /usr/lib64/libdl.so* /asset-output/lib/ || echo \"libdl not found in /usr/lib64\"
    cp -v /usr/lib64/libpng15.so* /asset-output/lib/ || echo \"libpng15 not found in /usr/lib64\"
    cp -v /usr/lib64/libxcb-shm.so* /asset-output/lib/ || echo \"libxcb-shm not found in /usr/lib64\"
    cp -v /usr/lib64/libxcb.so* /asset-output/lib/ || echo \"libxcb not found in /usr/lib64\"
    cp -v /usr/lib64/libxcb-render.so* /asset-output/lib/ || echo \"libxcb-render not found in /usr/lib64\"
    cp -v /usr/lib64/libXrender.so* /asset-output/lib/ || echo \"libXrender not found in /usr/lib64\"
    cp -v /usr/lib64/libX11.so* /asset-output/lib/ || echo \"libX11 not found in /usr/lib64\"
    cp -v /usr/lib64/libXext.so* /asset-output/lib/ || echo \"libXext not found in /usr/lib64\"
    cp -v /usr/lib64/libz.so* /asset-output/lib/ || echo \"libz not found in /usr/lib64\"
    cp -v /usr/lib64/libGL.so* /asset-output/lib/ || echo \"libGL not found in /usr/lib64\"
    cp -v /usr/lib64/librt.so* /asset-output/lib/ || echo \"librt not found in /usr/lib64\"
    cp -v /usr/lib64/libm.so* /asset-output/lib/ || echo \"libm not found in /usr/lib64\"
    cp -v /usr/lib64/libc.so* /asset-output/lib/ || echo \"libc not found in /usr/lib64\"
    cp -v /usr/lib64/libexpat.so* /asset-output/lib/ || echo \"libexpat not found in /usr/lib64\"
    cp -v /usr/lib64/libuuid.so* /asset-output/lib/ || echo \"libuuid not found in /usr/lib64\"
    cp -v /usr/lib64/libbz2.so* /asset-output/lib/ || echo \"libbz2 not found in /usr/lib64\"
    cp -v /usr/lib64/libGLdispatch.so* /asset-output/lib/ || echo \"libGLdispatch not found in /usr/lib64\"
    cp -v /usr/lib64/libXau.so* /asset-output/lib/ || echo \"libXau not found in /usr/lib64\"
    cp -v /usr/lib64/libGLX.so* /asset-output/lib/ || echo \"libGLX not found in /usr/lib64\"
  "

echo "CairoSVG layer built successfully at $LAYER_DIR"