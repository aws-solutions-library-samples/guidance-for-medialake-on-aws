#!/bin/bash

BASE_DIR=$(pwd)
TEMP_DIR=$(mktemp -d)
LAYER_DIR=$BASE_DIR/dist/lambdas/layers/resvg

# Create the directory structure
mkdir -p $LAYER_DIR/bin

# Use Docker to build the layer with resvg CLI
docker run --rm \
  -v $LAYER_DIR:/asset-output \
  public.ecr.aws/amazonlinux/amazonlinux:2.0.20250305.0-amd64 \
  /bin/bash -c "
    set -euo pipefail

    # 1) Install build tools & deps
    yum -y update
    yum -y groupinstall \"Development Tools\"
    yum -y install rust cargo cairo-devel fontconfig fontconfig-devel git

    # 2) Clone & build resvg
    TMP=\$(mktemp -d)
    git clone https://github.com/linebender/resvg.git \"\$TMP/resvg\"
    cd \"\$TMP/resvg\"
    cargo build --release --bin resvg

    # 3) Package the binary into a layer structure
    mkdir -p /asset-output/bin
    cp target/release/resvg /asset-output/bin/
    chmod +x /asset-output/bin/resvg

    # 4) Copy any required native libraries (if needed)
    # Note: resvg is statically linked, so this may not be necessary
    # but we'll include some common dependencies just in case
    cp -v /usr/lib64/libfontconfig.so* /asset-output/bin/ || echo \"libfontconfig not found in /usr/lib64\"
    cp -v /usr/lib64/libfreetype.so* /asset-output/bin/ || echo \"libfreetype not found in /usr/lib64\"
    cp -v /usr/lib64/libexpat.so* /asset-output/bin/ || echo \"libexpat not found in /usr/lib64\"
    cp -v /usr/lib64/libuuid.so* /asset-output/bin/ || echo \"libuuid not found in /usr/lib64\"
    cp -v /usr/lib64/libz.so* /asset-output/bin/ || echo \"libz not found in /usr/lib64\"
  "

echo "Resvg layer built successfully at $LAYER_DIR"
