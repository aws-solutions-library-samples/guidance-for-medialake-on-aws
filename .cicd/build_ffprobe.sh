#!/bin/bash

# Build ffprobe from official FFmpeg source release
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

echo "Configuring build (ffprobe only)..."
cd ffmpeg-src
./configure --disable-doc --disable-ffmpeg --disable-ffplay --enable-static --disable-shared

echo "Building ffprobe..."
make -j$(nproc) ffprobe

echo "Packaging layer..."
mkdir -p $BASE_DIR/dist/lambdas/layers/ffprobe/bin
cp ffprobe $BASE_DIR/dist/lambdas/layers/ffprobe/bin/
chmod +x $BASE_DIR/dist/lambdas/layers/ffprobe/bin/ffprobe

cd $BASE_DIR
rm -rf $TEMP_DIR

echo "ffprobe layer built successfully at dist/lambdas/layers/ffprobe/"
