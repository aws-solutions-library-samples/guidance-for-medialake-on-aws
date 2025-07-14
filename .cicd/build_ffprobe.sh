#!/bin/bash

BASE_DIR=$(pwd)
TEMP_DIR=$(mktemp -d)
cd $TEMP_DIR
curl https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz -o ffmpeg-release-amd64-static.tar.xz
curl https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz.md5 -o ffmpeg-release-amd64-static.tar.xz.md5
md5sum -c ffmpeg-release-amd64-static.tar.xz.md5
mkdir ffmpeg-release-amd64
tar xvf ffmpeg-release-amd64-static.tar.xz -C ffmpeg-release-amd64
mkdir -p $BASE_DIR/dist/lambdas/layers/ffprobe/bin
cp ffmpeg-release-amd64/*/ffprobe $BASE_DIR/dist/lambdas/layers/ffprobe/bin
cd $BASE_DIR
rm -rf $TEMP_DIR
