#!/bin/bash
# Build the resvg CLI Lambda layer.
#
# Kept in step with the Docker-bundling fallback in
# medialake_constructs/shared_constructs/lambda_layers.py (ResvgCliLayer): both
# produce the same layer, and a fix applied to only one of them leaves the other
# broken depending on whether the CI asset path exists.
#
# Two things this deliberately does NOT do any more:
#
#   * Use Amazon Linux 2's packaged rust/cargo. It is too old to compile current
#     resvg, so the build failed on a toolchain error. A stable toolchain is
#     installed through rustup instead.
#   * Clone resvg from git HEAD. That made the build non-reproducible and meant
#     it broke on its own every time upstream raised its minimum supported Rust
#     version. `cargo install resvg --locked` takes the published crate and its
#     own lockfile.

set -euo pipefail

BASE_DIR=$(pwd)
LAYER_DIR=$BASE_DIR/dist/lambdas/layers/resvg

# Create the directory structure
mkdir -p "$LAYER_DIR/bin"

# Use Docker to build the layer with resvg CLI
docker run --rm \
  -v "$LAYER_DIR":/asset-output \
  public.ecr.aws/amazonlinux/amazonlinux:2.0.20250305.0-amd64 \
  /bin/bash -c "
    set -euo pipefail

    # 1) Install build tools & deps
    yum -y update
    yum -y groupinstall \"Development Tools\"
    yum -y install gcc cairo-devel fontconfig fontconfig-devel tar gzip

    # 2) Install a current stable Rust toolchain via rustup
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs \
        | sh -s -- -y --default-toolchain stable --profile minimal
    source \"\$HOME/.cargo/env\"

    # 3) Build resvg from the published crate, using its own lockfile
    cargo install resvg --locked

    # 4) Package the binary into a layer structure
    mkdir -p /asset-output/bin
    cp \"\$HOME/.cargo/bin/resvg\" /asset-output/bin/
    chmod 755 /asset-output/bin/resvg

    # 5) Copy any required native libraries (if needed)
    # Note: resvg is statically linked, so this may not be necessary
    # but we'll include some common dependencies just in case
    cp -v /usr/lib64/libfontconfig.so* /asset-output/bin/ || echo \"libfontconfig not found in /usr/lib64\"
    cp -v /usr/lib64/libfreetype.so* /asset-output/bin/ || echo \"libfreetype not found in /usr/lib64\"
    cp -v /usr/lib64/libexpat.so* /asset-output/bin/ || echo \"libexpat not found in /usr/lib64\"
    cp -v /usr/lib64/libuuid.so* /asset-output/bin/ || echo \"libuuid not found in /usr/lib64\"
    cp -v /usr/lib64/libz.so* /asset-output/bin/ || echo \"libz not found in /usr/lib64\"
  "

# Only reached when docker exits 0, because of set -e above. Previously this
# printed success unconditionally and a failed build looked like a passing one.
echo "Resvg layer built successfully at $LAYER_DIR"
