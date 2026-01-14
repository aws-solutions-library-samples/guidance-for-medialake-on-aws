#!/bin/bash

# Build ffmpeg from official FFmpeg source release
# Matches version specified in lambda_layers.py
FFMPEG_VERSION="8.0.1"
FFMPEG_FILENAME="ffmpeg-${FFMPEG_VERSION}.tar.xz"
FFMPEG_URL="https://ffmpeg.org/releases/${FFMPEG_FILENAME}"

set -e

BASE_DIR=$(pwd)
TEMP_DIR=$(mktemp -d)
cd $TEMP_DIR

echo "Downloading FFmpeg ${FFMPEG_VERSION} source..."
curl -L "${FFMPEG_URL}" -o "${FFMPEG_FILENAME}"

echo "Extracting source..."
mkdir ffmpeg-src
tar xvf "${FFMPEG_FILENAME}" -C ffmpeg-src --strip-components=1

echo "Configuring build (ffmpeg only)..."
cd ffmpeg-src
./configure --disable-doc --disable-ffprobe --disable-ffplay --enable-static --disable-shared

echo "Building ffmpeg..."
make -j$(nproc) ffmpeg

echo "Packaging layer..."
mkdir -p $BASE_DIR/dist/lambdas/layers/ffmpeg/bin
cp ffmpeg $BASE_DIR/dist/lambdas/layers/ffmpeg/bin/
chmod +x $BASE_DIR/dist/lambdas/layers/ffmpeg/bin/ffmpeg

cd $BASE_DIR
rm -rf $TEMP_DIR

echo "ffmpeg layer built successfully at dist/lambdas/layers/ffmpeg/"
