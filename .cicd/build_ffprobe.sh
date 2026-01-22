#!/bin/bash

# Pin to a specific FFmpeg build version to avoid Lambda layer size limit issues.
# Version: autobuild-2025-12-30-12-55 (131MB compressed)
FFMPEG_VERSION="autobuild-2025-12-30-12-55"
FFMPEG_FILENAME="ffmpeg-N-122292-gee2eb6ced8-linux64-gpl.tar.xz"
FFMPEG_SHA256="743350f5b5fc489c727e7fbf0654d2c787841e743fef8d012b505e02ba4fd548"  # pragma: allowlist secret

BASE_DIR=$(pwd)
TEMP_DIR=$(mktemp -d)
cd $TEMP_DIR
curl -L "https://github.com/BtbN/FFmpeg-Builds/releases/download/${FFMPEG_VERSION}/${FFMPEG_FILENAME}" -o "${FFMPEG_FILENAME}"
echo "${FFMPEG_SHA256}  ${FFMPEG_FILENAME}" | sha256sum -c
mkdir ffmpeg-extracted
tar xvf "${FFMPEG_FILENAME}" -C ffmpeg-extracted
mkdir -p $BASE_DIR/dist/lambdas/layers/ffprobe/bin
cp ffmpeg-extracted/*/bin/ffprobe $BASE_DIR/dist/lambdas/layers/ffprobe/bin
cd $BASE_DIR
rm -rf $TEMP_DIR
