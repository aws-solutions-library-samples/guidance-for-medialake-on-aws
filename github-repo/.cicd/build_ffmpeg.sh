#!/bin/bash

BASE_DIR=$(pwd)
TEMP_DIR=$(mktemp -d)
cd $TEMP_DIR
curl -L https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-linux64-gpl.tar.xz -o ffmpeg-master-latest-linux64-gpl.tar.xz
curl -L https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/checksums.sha256 -o checksums.sha256
grep ffmpeg-master-latest-linux64-gpl.tar.xz checksums.sha256 | sha256sum -c
mkdir ffmpeg-master-latest-linux64-gpl
tar xvf ffmpeg-master-latest-linux64-gpl.tar.xz -C ffmpeg-master-latest-linux64-gpl
mkdir -p $BASE_DIR/dist/lambdas/layers/ffmpeg/bin
cp ffmpeg-master-latest-linux64-gpl/*/bin/ffmpeg $BASE_DIR/dist/lambdas/layers/ffmpeg/bin
cd $BASE_DIR
rm -rf $TEMP_DIR
