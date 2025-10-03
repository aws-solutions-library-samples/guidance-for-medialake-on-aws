import os
from dataclasses import dataclass

from aws_cdk import AssetHashType, BundlingOptions, DockerImage, Stack
from aws_cdk import aws_lambda as lambda_
from constructs import Construct

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
                    image=DockerImage.from_registry(
                        "public.ecr.aws/amazonlinux/amazonlinux:2023"
                    ),
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
                        """,
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


class ResvgCliLayer(Construct):
    """
    A Lambda layer shipping the `resvg` CLI compiled from source for Amazon Linux 2023.
    In CI, you can build once and point to a pre-bundled asset under dist/lambdas/layers/resvg.
    """

    def __init__(self, scope: Construct, id: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        if "CI" in os.environ:
            # In CI, use a prebuilt zip under dist/
            code = lambda_.Code.from_asset("dist/lambdas/layers/resvg")
        else:
            # Build from source in a container each time
            code = lambda_.Code.from_asset(
                path=".",
                bundling=BundlingOptions(
                    image=DockerImage.from_registry(
                        "public.ecr.aws/amazonlinux/amazonlinux:2.0.20250305.0-amd64"
                    ),
                    user="root",
                    command=[
                        "/bin/bash",
                        "-c",
                        """
                        set -euo pipefail
                        # 1) Install build tools & deps
                        yum -y update
                        yum -y install rust cargo fontconfig fontconfig-devel

                        # 2) Install resvg using cargo
                        cargo install resvg

                        # 3) Package the binary into a layer structure
                        mkdir -p /asset-output/bin
                        cp ~/.cargo/bin/resvg /asset-output/bin/
                        chmod +x /asset-output/bin/resvg
                        """,
                    ],
                ),
            )

        self.layer = lambda_.LayerVersion(
            self,
            "ResvgCliLayer",
            layer_version_name="resvg-cli-layer",
            description="A Lambda layer containing the resvg CLI (SVG→PNG converter)",
            compatible_runtimes=[lambda_.Runtime.PYTHON_3_12],
            compatible_architectures=[
                lambda_.Architecture.X86_64,
                lambda_.Architecture.ARM_64,
            ],
            code=code,
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
                            wget https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-linux64-gpl.tar.xz
                            wget https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/checksums.sha256
                            grep ffmpeg-master-latest-linux64-gpl.tar.xz checksums.sha256 | sha256sum -c
                            mkdir ffmpeg-master-latest-linux64-gpl
                            tar xvf ffmpeg-master-latest-linux64-gpl.tar.xz -C ffmpeg-master-latest-linux64-gpl
                            mkdir -p ffprobe/bin
                            cp ffmpeg-master-latest-linux64-gpl/*/bin/ffprobe ffprobe/bin/
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
        verifies it with its SHA256 checksum, extracts the binary, and packages it into a Lambda layer.
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
                            wget https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-linux64-gpl.tar.xz
                            wget https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/checksums.sha256
                            grep ffmpeg-master-latest-linux64-gpl.tar.xz checksums.sha256 | sha256sum -c
                            mkdir ffmpeg-master-latest-linux64-gpl
                            tar xvf ffmpeg-master-latest-linux64-gpl.tar.xz -C ffmpeg-master-latest-linux64-gpl
                            mkdir -p ffmpeg/bin
                            cp ffmpeg-master-latest-linux64-gpl/*/bin/ffmpeg ffmpeg/bin/
                            cd ffmpeg
                            zip -9 -r $TEMP_DIR/ffmpeg.zip .
                            cp $TEMP_DIR/ffmpeg.zip /asset-output/
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


# class CustomBoto3Layer(Construct):
#     """
#     A Lambda layer containing custom unreleased boto3 SDK.
#     Uses wheel files for boto3 and botocore packages.
#     """

#     def __init__(self, scope: Construct, id: str, **kwargs):
#         super().__init__(scope, id, **kwargs)

#         if "CI" in os.environ:
#             # In CI, use pre-built layer from dist directory
#             self.layer = lambda_.LayerVersion(
#                 self,
#                 "CustomBoto3Layer",
#                 layer_version_name="custom-boto3-layer",
#                 compatible_runtimes=[lambda_.Runtime.PYTHON_3_12],
#                 compatible_architectures=[
#                     lambda_.Architecture.X86_64,
#                     lambda_.Architecture.ARM_64,
#                 ],
#                 description="A Lambda layer with custom unreleased boto3 SDK",
#                 code=lambda_.Code.from_asset("dist/lambdas/layers/custom_boto3"),
#             )
#         else:
#             # Build layer from wheel files using Docker bundling
#             self.layer = lambda_.LayerVersion(
#                 self,
#                 "CustomBoto3Layer",
#                 layer_version_name="custom-boto3-layer",
#                 compatible_runtimes=[lambda_.Runtime.PYTHON_3_12],
#                 compatible_architectures=[
#                     lambda_.Architecture.X86_64,
#                     lambda_.Architecture.ARM_64,
#                 ],
#                 description="A Lambda layer with custom unreleased boto3 SDK",
#                 code=lambda_.Code.from_asset(
#                     path=".",
#                     bundling=BundlingOptions(
#                         image=DockerImage.from_registry("public.ecr.aws/amazonlinux/amazonlinux:2023"),
#                         user="root",
#                         command=[
#                             "/bin/bash",
#                             "-c",
#                             """
#                             set -euo pipefail

#                             # Install Python and pip
#                             yum -y update && yum -y install python3 python3-pip

#                             # Create layer directory structure
#                             mkdir -p /asset-output/python

#                             # Install custom boto3 and botocore wheels
#                             pip3 install \
#                                 lambdas/layers/custom_boto3/boto3-1.39.4-py3-none-any.whl \
#                                 lambdas/layers/custom_boto3/botocore-1.39.4-py3-none-any.whl \
#                                 --target /asset-output/python \
#                                 --no-deps

#                             # Clean up unnecessary files to reduce layer size
#                             find /asset-output/python -type d -name "__pycache__" -exec rm -rf {} + || true
#                             find /asset-output/python -name "*.pyc" -delete || true
#                             find /asset-output/python -name "*.pyo" -delete || true
#                             """
#                         ],
#                     ),
#                 ),
#             )


class CommonLibrariesLayer(Construct):
    """
    A Lambda layer that bundles shared Python utility modules under the
    required `python/` directory so that AWS Lambda automatically includes
    them in PYTHONPATH at runtime.

    We use CDK bundling to wrap the flat `.py` files into the correct
    directory structure by copying them into `/asset-output/python/`
    inside a container matching the Lambda Python 3.12 environment.
    """

    def __init__(
        self,
        scope: Construct,
        id: str,
        *,
        entry: str = "lambdas/common_libraries",
        **kwargs,
    ):
        super().__init__(scope, id, **kwargs)

        # Package the layer code from the source directory, hashing on
        # the source files so updates are detected when any file changes.
        layer_code = lambda_.Code.from_asset(
            entry,
            asset_hash_type=AssetHashType.SOURCE,
            bundling=BundlingOptions(
                # Use Lambda-compatible Python 3.12 image for bundling
                image=DockerImage.from_registry("public.ecr.aws/lambda/python:3.12"),
                # Override entrypoint to run our custom commands
                entrypoint=["bash", "-c"],
                # 1) Create python/ in the output
                # 2) Copy all Python modules into that folder
                command=[
                    "mkdir -p /asset-output/python && cp /asset-input/*.py /asset-output/python/"
                ],
                # Run inside the input directory
                working_directory="/asset-input",
                # Run as root to avoid permission issues
                user="root",
            ),
        )

        # Define the Lambda layer with the correctly structured code
        self.layer = lambda_.LayerVersion(
            self,
            "CommonLibrariesLayer",
            code=layer_code,
            compatible_runtimes=[lambda_.Runtime.PYTHON_3_12],
            description="Common utility libraries for all MediaLake Lambda functions",
        )
