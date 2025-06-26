import os
from aws_cdk import (
    Stack,
    aws_lambda as lambda_,
    BundlingOptions,
    BundlingOptions,
    DockerImage,
)
from constructs import Construct
from dataclasses import dataclass

from .layer_base import LambdaLayer, LambdaLayerConfig


@dataclass
class PowertoolsLayerConfig:
    architecture: str = lambda_.Architecture.X86_64
    layer_version: str = "68"


class PowertoolsLayer(Construct):
    def __init__(
        self,
        scope: Construct,
        id: str,
        config: PowertoolsLayerConfig,
        **kwargs,
    ):
        super().__init__(scope, id, **kwargs)

        stack = Stack.of(self)

        self.layer = lambda_.LayerVersion.from_layer_version_arn(
            self,
            "PowertoolsLayer",
            f"arn:{stack.partition}:lambda:{stack.region}:017000801446:layer:AWSLambdaPowertoolsPythonV3-python312-x86_64:4",
        )
        # f"arn:{stack.partition}:lambda:{stack.region}:017000801446:layer:AWSLambdaPowertoolsPythonV3-{'Arm64' if config.architecture == lambda_.Architecture.ARM_64 else ''}:{config.layer_version}",


class JinjaLambdaLayer(Construct):
    def __init__(self, scope: Construct, id: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        # Define the Lambda layer
        self.layer = LambdaLayer(
            self,
            "JinjaLayer",
            config=LambdaLayerConfig(
                entry="lambdas/layers/jinja",
                description="A Lambda layer with Jinja2 library",
            ),
        )

class ZipmergeLayer(Construct):
    def __init__(
        self,
        scope: Construct,
        id: str,
        *,
        architecture: lambda_.Architecture = lambda_.Architecture.ARM_64,
        **kwargs,
    ):
        super().__init__(scope, id, **kwargs)

        goarch = "arm64" if architecture == lambda_.Architecture.ARM_64 else "amd64"

        self.layer = lambda_.LayerVersion(
            self,
            "ZipmergeLayer",
            layer_version_name="zipmerge-layer",
            compatible_runtimes=[lambda_.Runtime.PYTHON_3_12],
            compatible_architectures=[architecture],
            description="Static zipmerge binary (rsc.io/zipmerge)",
            code=lambda_.Code.from_asset(
                path=".",  # dummy; all work happens in the container
                bundling=BundlingOptions(
                    user="root",
                    image=DockerImage.from_registry("public.ecr.aws/amazonlinux/amazonlinux:2023"),
                    command=[
                        "/bin/bash",
                        "-c",
                        f"""
                        set -euo pipefail

                        yum -y update && yum -y install golang git

                        # Where Go will put the binary
                        export GOPATH=/tmp/go

                        # 1. Cross-compile zipmerge
                        GOOS=linux GOARCH={goarch} CGO_ENABLED=0 \
                        go install rsc.io/zipmerge@latest

                        # 2. Copy the resulting binary into the layer structure
                        BIN_PATH="$GOPATH/bin/linux_{goarch}/zipmerge"
                        if [ ! -f "$BIN_PATH" ]; then
                            # Try alternate path
                            BIN_PATH="$GOPATH/bin/zipmerge"
                        fi
                        
                        mkdir -p /asset-output/bin
                        cp "$BIN_PATH" /asset-output/bin/zipmerge
                        
                        # 3. Ensure the binary is executable
                        chmod 755 /asset-output/bin/zipmerge
                        """
                    ],


                ),
            ),
        )


class OpenSearchPyLayer(Construct):
    def __init__(self, scope: Construct, id: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        # Define the Lambda layer
        self.layer = LambdaLayer(
            self,
            "OpenSearchPyLayer",
            config=LambdaLayerConfig(
                entry="lambdas/layers/opensearchpy",
                description="A Lambda layer with open serch py library",
            ),
        )


class PynamoDbLambdaLayer(Construct):
    def __init__(self, scope: Construct, id: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        # Define the Lambda layer
        self.layer = LambdaLayer(
            self,
            "PynamoDbLambdaLayer",
            config=LambdaLayerConfig(
                entry="lambdas/layers/pynamodb",
                description="A Lambda layer with pynamodb library",
            ),
        )


class PyMediaInfo(Construct):
    def __init__(self, scope: Construct, id: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        # Define the Lambda layer
        self.layer_version = LambdaLayer(
            self,
            "PyMediaInfoLayer",
            config=LambdaLayerConfig(
                entry="lambdas/layers/pymediainfo",
                description="A Lambda layer with pymediainfo library",
            ),
        )

    @property
    def layer(self) -> lambda_.LayerVersion:
        return self.layer_version.layer

class ImageMagickLayer(Construct):
    PORTABLE_VERSION = "7.1.1-30"

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        architecture: lambda_.Architecture = lambda_.Architecture.X86_64,
        **kwargs,
    ):
        super().__init__(scope, construct_id, **kwargs)

        arch_tag = "aarch64" if architecture == lambda_.Architecture.ARM_64 else "x86_64"
        tarball  = f"ImageMagick-{arch_tag}-linux-gnu.tar.gz"

        self.layer = lambda_.LayerVersion(
            self,
            "ImageMagickLayer",
            layer_version_name="imagemagick-layer",
            compatible_runtimes=[lambda_.Runtime.PYTHON_3_12],
            compatible_architectures=[architecture],
            description=f"ImageMagick {self.PORTABLE_VERSION} portable build",
            code=lambda_.Code.from_asset(
                path=".",
                bundling=BundlingOptions(
                    user="root",
                    image=DockerImage.from_registry("public.ecr.aws/amazonlinux/amazonlinux:2023"),
                    command=[
                        "/bin/bash",
                        "-c",
                        f"""
                        set -euo pipefail
                        dnf -y install wget xz tar

                        TMP=$(mktemp -d); cd "$TMP"
                        wget -q https://imagemagick.org/archive/binaries/{tarball}
                        tar -xzf {tarball}

                        IMDIR=$(find . -maxdepth 1 -type d -name 'ImageMagick-*' | head -n1)

                        mkdir -p /asset-output/bin /asset-output/lib
                        cp -r "$IMDIR"/bin/* /asset-output/bin/
                        cp -r "$IMDIR"/lib/* /asset-output/lib/
                        ln -s magick /asset-output/bin/convert
                        chmod -R 755 /asset-output
                        """
                    ],
                ),
            ),
        )

        
class CairoSvgLayer(Construct):
    def __init__(self, scope: Construct, id: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        if "CI" in os.environ:
            self.layer = lambda_.LayerVersion(
                self,
                "CairoSvgLayer",
                layer_version_name="cairosvg-layer",
                compatible_runtimes=[
                    lambda_.Runtime.PYTHON_3_12,
                ],
                description="Layer containing cairosvg depends",
                code=lambda_.Code.from_asset("dist/lambdas/layers/cairosvg"),
            )
        else:
            self.layer = lambda_.LayerVersion(
                self,
                "CairoSvgLayer",
                layer_version_name="cairosvg-layer",
                compatible_runtimes=[
                    lambda_.Runtime.PYTHON_3_12,
                ],
                description="Layer containing cairosvg dependencies, including native libraries",
                code=lambda_.Code.from_asset(
                    path=".",
                    bundling=BundlingOptions(
                        command=[
                            "/bin/bash",
                            "-c",
                            """
                            set -e
                            # Update packages and install required dependencies using yum
                            yum update -y && yum install -y cairo-devel pango-devel gdk-pixbuf2-devel libffi-devel pkg-config python3-pip
                            # Upgrade pip (optional, but often helpful)
                            python3 -m pip install --upgrade pip
                            # Install cairosvg and its dependencies into the python folder
                            python3 -m pip install cairosvg -t /asset-output/python
                            mkdir -p /asset-output/lib
                            # Copy native libraries required by CairoSVG and its dependencies
                            cp -v /usr/lib64/libcairo.so* /asset-output/lib/ || echo "Cairo libraries not found in /usr/lib64"
                            cp -v /usr/lib64/libpango-1.0.so* /asset-output/lib/ || echo "Pango libraries not found in /usr/lib64"
                            cp -v /usr/lib64/libgdk_pixbuf-2.0.so* /asset-output/lib/ || echo "gdk-pixbuf libraries not found in /usr/lib64"
                            cp -v /usr/lib64/libffi.so* /asset-output/lib/ || echo "libffi libraries not found in /usr/lib64"

                            # Additional dependencies as determined by ldd
                            cp -v /usr/lib64/libpthread.so* /asset-output/lib/ || echo "libpthread not found in /usr/lib64"
                            cp -v /usr/lib64/libpixman-1.so* /asset-output/lib/ || echo "libpixman not found in /usr/lib64"
                            cp -v /usr/lib64/libfontconfig.so* /asset-output/lib/ || echo "libfontconfig not found in /usr/lib64"
                            cp -v /usr/lib64/libfreetype.so* /asset-output/lib/ || echo "libfreetype not found in /usr/lib64"
                            cp -v /usr/lib64/libEGL.so* /asset-output/lib/ || echo "libEGL not found in /usr/lib64"
                            cp -v /usr/lib64/libdl.so* /asset-output/lib/ || echo "libdl not found in /usr/lib64"
                            cp -v /usr/lib64/libpng15.so* /asset-output/lib/ || echo "libpng15 not found in /usr/lib64"
                            cp -v /usr/lib64/libxcb-shm.so* /asset-output/lib/ || echo "libxcb-shm not found in /usr/lib64"
                            cp -v /usr/lib64/libxcb.so* /asset-output/lib/ || echo "libxcb not found in /usr/lib64"
                            cp -v /usr/lib64/libxcb-render.so* /asset-output/lib/ || echo "libxcb-render not found in /usr/lib64"
                            cp -v /usr/lib64/libXrender.so* /asset-output/lib/ || echo "libXrender not found in /usr/lib64"
                            cp -v /usr/lib64/libX11.so* /asset-output/lib/ || echo "libX11 not found in /usr/lib64"
                            cp -v /usr/lib64/libXext.so* /asset-output/lib/ || echo "libXext not found in /usr/lib64"
                            cp -v /usr/lib64/libz.so* /asset-output/lib/ || echo "libz not found in /usr/lib64"
                            cp -v /usr/lib64/libGL.so* /asset-output/lib/ || echo "libGL not found in /usr/lib64"
                            cp -v /usr/lib64/librt.so* /asset-output/lib/ || echo "librt not found in /usr/lib64"
                            cp -v /usr/lib64/libm.so* /asset-output/lib/ || echo "libm not found in /usr/lib64"
                            cp -v /usr/lib64/libc.so* /asset-output/lib/ || echo "libc not found in /usr/lib64"
                            cp -v /usr/lib64/libexpat.so* /asset-output/lib/ || echo "libexpat not found in /usr/lib64"
                            cp -v /usr/lib64/libuuid.so* /asset-output/lib/ || echo "libuuid not found in /usr/lib64"
                            cp -v /usr/lib64/libbz2.so* /asset-output/lib/ || echo "libbz2 not found in /usr/lib64"
                            cp -v /usr/lib64/libGLdispatch.so* /asset-output/lib/ || echo "libGLdispatch not found in /usr/lib64"
                            cp -v /usr/lib64/libXau.so* /asset-output/lib/ || echo "libXau not found in /usr/lib64"
                            cp -v /usr/lib64/libGLX.so* /asset-output/lib/ || echo "libGLX not found in /usr/lib64"
                            """
                        ],
                        user="root",
                        image=DockerImage.from_registry(
                            "public.ecr.aws/amazonlinux/amazonlinux:2.0.20250305.0-amd64"
                        ),
                    ),
                ),
            )


class FFProbeLayer(Construct):
    def __init__(self, scope: Construct, id: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        if "CI" in os.environ:
            self.layer = lambda_.LayerVersion(
                self,
                "FFProbeLayer",
                layer_version_name="ffprobe-layer",
                compatible_runtimes=[
                    lambda_.Runtime.PYTHON_3_12,
                ],
                description="Layer containing ffprobe binary",
                code=lambda_.Code.from_asset("dist/lambdas/layers/ffprobe"),
            )
        else:
            self.layer = lambda_.LayerVersion(
                self,
                "FFProbeLayer",
                layer_version_name="ffprobe-layer",
                compatible_runtimes=[
                    lambda_.Runtime.PYTHON_3_12,
                ],
                description="Layer containing ffprobe binary",
                code=lambda_.Code.from_asset(
                    path=".",
                    bundling=BundlingOptions(
                        command=[
                            "/bin/bash",
                            "-c",
                            f"""
                            set -e
                            yum update -y && yum install -y wget xz zip tar
                            TEMP_DIR=$(mktemp -d)
                            cd $TEMP_DIR
                            wget https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz
                            wget https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz.md5
                            md5sum -c ffmpeg-release-amd64-static.tar.xz.md5
                            mkdir ffmpeg-release-amd64
                            tar xvf ffmpeg-release-amd64-static.tar.xz -C ffmpeg-release-amd64
                            mkdir -p ffprobe/bin
                            cp ffmpeg-release-amd64/*/ffprobe ffprobe/bin/
                            cd ffprobe
                            zip -9 -r $TEMP_DIR/ffprobe.zip .
                            cp $TEMP_DIR/ffprobe.zip /asset-output/
                            cd /
                            rm -rf $TEMP_DIR
                            """,
                        ],
                        user="root",
                        image=DockerImage.from_registry(
                            "public.ecr.aws/amazonlinux/amazonlinux:latest"
                        ),
                    ),
                ),
            )

class FFmpegLayer(Construct):
    def __init__(self, scope: Construct, id: str, **kwargs):
        """
        This layer bundles a static build of FFmpeg. It downloads the FFmpeg release,
        verifies it with its MD5 checksum, extracts the binary, and packages it into a Lambda layer.
        """
        super().__init__(scope, id, **kwargs)

        # When running in CI or if you already have a built asset, use that asset.
        if "CI" in os.environ:
            self.layer = lambda_.LayerVersion(
                self,
                "FFmpegLayer",
                layer_version_name="ffmpeg-layer",
                compatible_runtimes=[lambda_.Runtime.PYTHON_3_12],
                description="Layer containing FFmpeg binary",
                code=lambda_.Code.from_asset("dist/lambdas/layers/ffmpeg"),
            )
        else:
            self.layer = lambda_.LayerVersion(
                self,
                "FFmpegLayer",
                layer_version_name="ffmpeg-layer",
                compatible_runtimes=[lambda_.Runtime.PYTHON_3_12],
                description="Layer containing FFmpeg binary",
                code=lambda_.Code.from_asset(
                    path=".",
                    bundling=BundlingOptions(
                        command=[
                            "/bin/bash",
                            "-c",
                            """
                            set -e
                            yum update -y && yum install -y wget xz zip tar
                            TEMP_DIR=$(mktemp -d)
                            cd $TEMP_DIR
                            wget https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz
                            wget https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz.md5
                            md5sum -c ffmpeg-release-amd64-static.tar.xz.md5
                            mkdir ffmpeg-release-amd64
                            tar xvf ffmpeg-release-amd64-static.tar.xz -C ffmpeg-release-amd64
                            mkdir -p ffmpeg/bin
                            cp ffmpeg-release-amd64/*/ffmpeg ffmpeg/bin/
                            cd ffmpeg
                            zip -9 -r $TEMP_DIR/ffmpeg.zip .
                            cp $TEMP_DIR/ffmpeg.zip /asset-output/
                            cd /
                            rm -rf $TEMP_DIR
                            """
                        ],
                        user="root",
                        image=DockerImage.from_registry("public.ecr.aws/amazonlinux/amazonlinux:latest"),
                    ),
                ),
            )

class GoogleCloudStorageLayer(Construct):
    def __init__(self, scope: Construct, id: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        # Define the Lambda layer
        self.layer = LambdaLayer(
            self,
            "GoogleCloudStorageLayer",
            config=LambdaLayerConfig(
                entry="lambdas/layers/googleCloudStorage",
                description="A Lambda layer with google cloud storage and google auth library",
            ),
        )


class IngestMediaProcessorLayer(Construct):
    def __init__(self, scope: Construct, construct_id: str, **kwargs):
        super().__init__(scope, construct_id, **kwargs)

        # Define the Lambda layer
        self.layer = LambdaLayer(
            self,
            "IngestMediaProcessorLayer",
            config=LambdaLayerConfig(
                entry="lambdas/layers/ingest_media_processor",
                description="A Lambda layer for analyzing media container media info",
            ),
        )


class SearchLayer(Construct):
    def __init__(self, scope: Construct, id: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        # Define the Lambda layer
        self.layer_version = LambdaLayer(
            self,
            "SearchLayer",
            config=LambdaLayerConfig(
                entry="lambdas/layers/search", description="A Lambda layer for search"
            ),
        )

    @property
    def layer(self) -> lambda_.LayerVersion:
        return self.layer_version.layer


class PyamlLayer(Construct):
    def __init__(self, scope: Construct, id: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        # Define the Lambda layer
        self.layer_version = LambdaLayer(
            self,
            "PyamlLayer",
            config=LambdaLayerConfig(
                entry="lambdas/layers/pyaml", description="A Lambda layer for pyaml"
            ),
        )

    @property
    def layer(self) -> lambda_.LayerVersion:
        return self.layer_version.layer


class ShortuuidLayer(Construct):
    def __init__(self, scope: Construct, id: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        # Define the Lambda layer
        self.layer_version = LambdaLayer(
            self,
            "ShortuuidLayer",
            config=LambdaLayerConfig(
                entry="lambdas/layers/shortuuid",
                description="A Lambda layer for shortuuid",
            ),
        )

    @property
    def layer(self) -> lambda_.LayerVersion:
        return self.layer_version.layer
