#!/bin/bash

# Pin to a specific FFmpeg build version to avoid Lambda layer size limit issues.
# Version: autobuild-2025-11-30-12-53 (131MB compressed)
FFMPEG_VERSION="autobuild-2025-11-30-12-53"
FFMPEG_FILENAME="ffmpeg-N-121938-g2456a39581-linux64-gpl.tar.xz"
FFMPEG_SHA256="fec46f7984352b988bda79be0521964a5148fecf7aa13db4e18a4383aa88e87f"  # pragma: allowlist secret

BASE_DIR=$(pwd)
TEMP_DIR=$(mktemp -d)
cd $TEMP_DIR
curl -L "https://github.com/BtbN/FFmpeg-Builds/releases/download/${FFMPEG_VERSION}/${FFMPEG_FILENAME}" -o "${FFMPEG_FILENAME}"
echo "${FFMPEG_SHA256}  ${FFMPEG_FILENAME}" | sha256sum -c
mkdir ffmpeg-extracted
tar xvf "${FFMPEG_FILENAME}" -C ffmpeg-extracted
mkdir -p $BASE_DIR/dist/lambdas/layers/ffmpeg/bin
cp ffmpeg-extracted/*/bin/ffmpeg $BASE_DIR/dist/lambdas/layers/ffmpeg/bin
cd $BASE_DIR
rm -rf $TEMP_DIR
