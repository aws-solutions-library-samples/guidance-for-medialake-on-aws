"""
Lambda Layer Constructs for MediaLake

This module provides reusable CDK constructs for Lambda layers used across
the MediaLake application. Layers are organized by functionality:

- Media Processing: FFmpeg, FFProbe, PyMediaInfo, ResvgCli, OpenEXR, Numpy
- Python Libraries: Powertools, Jinja, OpenSearchPy, PynamoDB
- Utilities: Zipmerge, CommonLibraries, Search, Pyaml, Shortuuid
- Cloud Storage: GoogleCloudStorage
- Ingest Processing: IngestMediaProcessor

Each layer supports both CI/CD pre-built assets and local Docker-based builds.

Security Considerations:
- All layers use official base images from public.ecr.aws or trusted sources
- Binary downloads (FFmpeg, FFProbe) include SHA256 checksum verification
- Compiled binaries use static linking where possible to reduce attack surface
- Layer sizes are optimized by removing cache files and unnecessary artifacts
"""

import os
from dataclasses import dataclass

from aws_cdk import AssetHashType, BundlingOptions, DockerImage, Stack
from aws_cdk import aws_lambda as lambda_
from constructs import Construct

from .layer_base import LambdaLayer, LambdaLayerConfig


@dataclass
class PowertoolsLayerConfig:
    """Configuration for AWS Lambda Powertools layer."""

    architecture: lambda_.Architecture = lambda_.Architecture.X86_64
    layer_version: str = "4"  # Version of the Powertools layer


class PowertoolsLayer(Construct):
    """
    AWS Lambda Powertools layer for Python 3.12.

    Provides structured logging, tracing, and metrics capabilities.
    Uses the official AWS-published layer ARN.

    Security: Uses official AWS-managed layer (account 017000801446) which is
    maintained and updated by AWS. No custom code or third-party dependencies.

    Attributes:
        layer: The Lambda layer version reference
    """

    def __init__(
        self,
        scope: Construct,
        id: str,
        config: PowertoolsLayerConfig,
        **kwargs,
    ):
        super().__init__(scope, id, **kwargs)

        stack = Stack.of(self)

        # Use official AWS Lambda Powertools layer
        # ARN format: arn:partition:lambda:region:017000801446:layer:AWSLambdaPowertoolsPythonV3-python312-x86_64:version
        # Account 017000801446 is the official AWS account for Powertools layers
        arch_suffix = (
            "Arm64" if config.architecture == lambda_.Architecture.ARM_64 else "x86_64"
        )

        self.layer = lambda_.LayerVersion.from_layer_version_arn(
            self,
            "PowertoolsLayer",
            f"arn:{stack.partition}:lambda:{stack.region}:017000801446:layer:AWSLambdaPowertoolsPythonV3-python312-{arch_suffix}:{config.layer_version}",
        )


class JinjaLambdaLayer(Construct):
    """
    Jinja2 templating library layer.

    Provides Jinja2 template engine for Lambda functions that need
    dynamic template rendering capabilities.

    Attributes:
        layer: The Lambda layer version containing Jinja2
    """

    def __init__(self, scope: Construct, id: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        self.layer = LambdaLayer(
            self,
            "JinjaLayer",
            config=LambdaLayerConfig(
                entry="lambdas/layers/jinja",
                description="Lambda layer with Jinja2 templating library",
            ),
        )


class ZipmergeLayer(Construct):
    """
    Zipmerge utility layer for ZIP file operations.

    Provides the zipmerge binary (rsc.io/zipmerge) compiled for Lambda.
    Supports both ARM64 and x86_64 architectures.

    Security: Compiles from source with CGO_ENABLED=0 for static linking,
    reducing attack surface. Uses official Amazon Linux 2023 base image.

    Args:
        architecture: Target Lambda architecture (default: ARM_64)

    Attributes:
        layer: The Lambda layer version containing zipmerge binary
    """

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
            description="Static zipmerge binary for ZIP file operations (rsc.io/zipmerge)",
            code=lambda_.Code.from_asset(
                path=".",
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

                        # Install build dependencies
                        yum -y update && yum -y install golang git

                        # Configure Go workspace
                        export GOPATH=/tmp/go

                        # Cross-compile zipmerge for Lambda architecture with static linking
                        # CGO_ENABLED=0 ensures static binary with no external dependencies
                        GOOS=linux GOARCH={goarch} CGO_ENABLED=0 \
                        go install rsc.io/zipmerge@latest

                        # Locate compiled binary (path varies by Go version)
                        BIN_PATH="$GOPATH/bin/linux_{goarch}/zipmerge"
                        if [ ! -f "$BIN_PATH" ]; then
                            BIN_PATH="$GOPATH/bin/zipmerge"
                        fi

                        # Package binary into layer structure with secure permissions
                        mkdir -p /asset-output/bin
                        cp "$BIN_PATH" /asset-output/bin/zipmerge
                        chmod 755 /asset-output/bin/zipmerge
                        """,
                    ],
                ),
            ),
        )


class OpenSearchPyLayer(Construct):
    """
    OpenSearch Python client library layer.

    Provides the opensearch-py client for interacting with OpenSearch clusters.

    Attributes:
        layer: The Lambda layer version containing opensearch-py
    """

    def __init__(self, scope: Construct, id: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        self.layer = LambdaLayer(
            self,
            "OpenSearchPyLayer",
            config=LambdaLayerConfig(
                entry="lambdas/layers/opensearchpy",
                description="Lambda layer with OpenSearch Python client library",
            ),
        )


class PynamoDbLambdaLayer(Construct):
    """
    PynamoDB library layer for DynamoDB operations.

    Provides PynamoDB ORM for simplified DynamoDB interactions.

    Attributes:
        layer: The Lambda layer version containing PynamoDB
    """

    def __init__(self, scope: Construct, id: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        self.layer = LambdaLayer(
            self,
            "PynamoDbLambdaLayer",
            config=LambdaLayerConfig(
                entry="lambdas/layers/pynamodb",
                description="Lambda layer with PynamoDB ORM library",
            ),
        )


class PyMediaInfo(Construct):
    """
    PyMediaInfo library layer for media metadata extraction.

    Provides pymediainfo library for extracting technical metadata
    from audio and video files.

    Attributes:
        layer: The Lambda layer version containing pymediainfo
    """

    def __init__(self, scope: Construct, id: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        self.layer_version = LambdaLayer(
            self,
            "PyMediaInfoLayer",
            config=LambdaLayerConfig(
                entry="lambdas/layers/pymediainfo",
                description="Lambda layer with pymediainfo for media metadata extraction",
            ),
        )

    @property
    def layer(self) -> lambda_.LayerVersion:
        """Returns the underlying Lambda layer version."""
        return self.layer_version.layer


class ResvgCliLayer(Construct):
    """
    Resvg CLI layer for SVG to PNG conversion.

    Provides the resvg command-line tool compiled for Amazon Linux 2023.
    Supports both CI pre-built assets and local Docker-based builds.

    In CI environments, uses pre-built assets from dist/lambdas/layers/resvg.
    In local development, compiles from source using Rust/Cargo.

    Security: Compiles from source using official Rust toolchain. Uses
    Amazon Linux 2 base image for compatibility with Lambda runtime.

    Attributes:
        layer: The Lambda layer version containing resvg binary
    """

    def __init__(self, scope: Construct, id: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        if "CI" in os.environ:
            # Use pre-built layer in CI for faster deployments
            code = lambda_.Code.from_asset("dist/lambdas/layers/resvg")
        else:
            # Build from source locally
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

                        # Install Rust toolchain and dependencies
                        yum -y update
                        yum -y install rust cargo fontconfig fontconfig-devel

                        # Compile resvg from source (latest stable version)
                        cargo install resvg

                        # Package binary into Lambda layer structure with secure permissions
                        mkdir -p /asset-output/bin
                        cp ~/.cargo/bin/resvg /asset-output/bin/
                        chmod 755 /asset-output/bin/resvg
                        """,
                    ],
                ),
            )

        self.layer = lambda_.LayerVersion(
            self,
            "ResvgCliLayer",
            layer_version_name="resvg-cli-layer",
            description="Lambda layer with resvg CLI for SVG to PNG conversion",
            compatible_runtimes=[lambda_.Runtime.PYTHON_3_12],
            compatible_architectures=[
                lambda_.Architecture.X86_64,
                lambda_.Architecture.ARM_64,
            ],
            code=code,
        )


class NumpyLayer(Construct):
    """
    NumPy library layer for scientific computing.

    Provides NumPy for numerical operations, array processing, and
    mathematical computations in Lambda functions.

    Supports both CI pre-built assets and local Docker-based builds.
    Optimized for Lambda by removing unnecessary cache files.

    Security: Uses official Amazon Linux 2023 base image. Installs only
    binary wheels (--only-binary) to prevent compilation of untrusted code.
    Strips debug symbols to reduce attack surface.

    Attributes:
        layer: The Lambda layer version containing NumPy
    """

    def __init__(self, scope: Construct, id: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        if "CI" in os.environ:
            # Use pre-built layer in CI for faster deployments
            code = lambda_.Code.from_asset("dist/lambdas/layers/numpy")
        else:
            # Build locally with Docker for development
            code = lambda_.Code.from_asset(
                path=".",
                bundling=BundlingOptions(
                    image=DockerImage.from_registry(
                        "public.ecr.aws/amazonlinux/amazonlinux:2023"
                    ),
                    user="root",
                    command=[
                        "/bin/bash",
                        "-c",
                        """
                        set -euo pipefail

                        # Install Python 3.12 and pip (matches Lambda runtime)
                        yum -y update
                        yum -y install python3.12 python3.12-pip findutils

                        # Create layer directory structure
                        mkdir -p /asset-output/python

                        # Install numpy with platform-specific wheels for Lambda Python 3.12
                        # --only-binary ensures no compilation of untrusted code
                        # --platform ensures compatibility with Lambda execution environment
                        python3.12 -m pip install \
                          --platform manylinux_2_28_x86_64 \
                          --target /asset-output/python \
                          --implementation cp \
                          --python-version 3.12 \
                          --only-binary=:all: \
                          --upgrade \
                          numpy

                        cd /asset-output/python

                        # Remove cache files to reduce layer size
                        find . -type d -name "__pycache__" -exec rm -rf {} + || true
                        find . -name "*.pyc" -delete || true
                        find . -name "*.pyo" -delete || true

                        # Remove tests and documentation to reduce layer size
                        find . -type d -name "tests" -exec rm -rf {} + || true
                        find . -type d -name "test" -exec rm -rf {} + || true
                        find . -type d -name "doc" -exec rm -rf {} + || true
                        find . -type d -name "docs" -exec rm -rf {} + || true
                        find . -type d -name "examples" -exec rm -rf {} + || true

                        # CRITICAL: Remove setup/build artifacts that cause import errors
                        # These files can interfere with Python's import system
                        find . -name "setup.py" -delete || true
                        find . -name "setup.cfg" -delete || true
                        find . -name "pyproject.toml" -delete || true
                        find . -name "MANIFEST.in" -delete || true

                        # Strip debug symbols from shared objects to reduce size and attack surface
                        find . -name "*.so*" -type f -exec strip --strip-debug {} \\; 2>/dev/null || true
                        """,
                    ],
                ),
            )

        self.layer = lambda_.LayerVersion(
            self,
            "NumpyLayer",
            layer_version_name="numpy-layer",
            description="Lambda layer with NumPy for scientific computing and array operations",
            compatible_runtimes=[lambda_.Runtime.PYTHON_3_12],
            compatible_architectures=[
                lambda_.Architecture.X86_64,
                lambda_.Architecture.ARM_64,
            ],
            code=code,
        )


class OpenEXRLayer(Construct):
    """
    OpenEXR library layer for HDR image processing.

    Provides OpenEXR 3.4.4 with all required C++ dependencies for reading
    and writing high dynamic range (HDR) image files in the EXR format.

    Built specifically for AWS Lambda Amazon Linux 2023 environment.
    Includes all necessary shared libraries (libOpenEXR, libImath, etc.).

    **Important**: Requires NumpyLayer to be attached to the Lambda function
    as well, as OpenEXR depends on NumPy for array operations.

    Security: Pins specific OpenEXR version (3.4.4) for reproducible builds.
    Compiles from source with --no-binary flag to ensure compatibility with
    Lambda runtime. Git is required during build to fetch OpenJPH dependency.

    Supports both CI pre-built assets and local Docker-based builds.

    Attributes:
        layer: The Lambda layer version containing OpenEXR and dependencies
    """

    def __init__(self, scope: Construct, id: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        if "CI" in os.environ:
            # Use pre-built layer in CI
            code = lambda_.Code.from_asset("dist/lambdas/layers/openexr")
        else:
            # Build from source locally
            code = lambda_.Code.from_asset(
                path=".",
                bundling=BundlingOptions(
                    image=DockerImage.from_registry(
                        "public.ecr.aws/amazonlinux/amazonlinux:2023"
                    ),
                    user="root",
                    command=[
                        "/bin/bash",
                        "-c",
                        """
                        set -euo pipefail

                        # Install Python 3.12 and dependencies
                        yum -y update
                        yum -y install python3.12 python3.12-pip findutils

                        # Create layer directory structure
                        mkdir -p /asset-output/python

                        # Try to install with platform-specific wheels first
                        if python3.12 -m pip install \
                          --platform manylinux_2_28_x86_64 \
                          --target /asset-output/python \
                          --implementation cp \
                          --python-version 3.12 \
                          --only-binary=:all: \
                          OpenEXR==3.4.4 2>/dev/null; then
                            echo 'Successfully installed OpenEXR from pre-built wheel'
                        else
                            echo 'Pre-built wheel not available, trying manylinux2014...'
                            if python3.12 -m pip install \
                              --platform manylinux2014_x86_64 \
                              --target /asset-output/python \
                              --implementation cp \
                              --python-version 3.12 \
                              --only-binary=:all: \
                              OpenEXR==3.4.4 2>/dev/null; then
                                echo 'Successfully installed OpenEXR from manylinux2014 wheel'
                            else
                                echo 'No compatible wheel found, building from source...'
                                yum -y install python3.12-devel gcc-c++ cmake make \
                                    zlib-devel openexr-devel openexr-libs imath-devel \
                                    git tar gzip wget

                                python3.12 -m pip install OpenEXR==3.4.4 --no-binary OpenEXR -t /asset-output/python

                                echo 'Copying required shared libraries...'
                                mkdir -p /asset-output/lib
                                cp -P /usr/lib64/libOpenEXR*.so* /asset-output/lib/ || true
                                cp -P /usr/lib64/libImath*.so* /asset-output/lib/ || true
                                cp -P /usr/lib64/libIex*.so* /asset-output/lib/ || true
                                cp -P /usr/lib64/libIlmThread*.so* /asset-output/lib/ || true
                            fi
                        fi

                        cd /asset-output

                        # Remove cache files
                        find python -type d -name "__pycache__" -exec rm -rf {} + || true
                        find python -name "*.pyc" -delete || true
                        find python -name "*.pyo" -delete || true

                        # Remove tests, docs, examples
                        find python -type d -name "tests" -exec rm -rf {} + || true
                        find python -type d -name "test" -exec rm -rf {} + || true
                        find python -type d -name "doc" -exec rm -rf {} + || true
                        find python -type d -name "docs" -exec rm -rf {} + || true
                        find python -type d -name "examples" -exec rm -rf {} + || true
                        find python -type d -name "benchmarks" -exec rm -rf {} + || true

                        # CRITICAL: Remove setup/build artifacts that cause import errors
                        find python -name "setup.py" -delete || true
                        find python -name "setup.cfg" -delete || true
                        find python -name "pyproject.toml" -delete || true
                        find python -name "MANIFEST.in" -delete || true

                        # Remove cmake build artifacts
                        find python -type d -name "CMakeFiles" -exec rm -rf {} + || true
                        find python -name "CMakeCache.txt" -delete || true
                        find python -name "cmake_install.cmake" -delete || true
                        find python -name "Makefile" -delete || true

                        # Remove static libraries
                        find . -name "*.a" -delete || true

                        # Strip debug symbols from .so files
                        find . -name "*.so*" -type f -exec strip --strip-debug {} \\; 2>/dev/null || true
                        """,
                    ],
                ),
            )

        self.layer = lambda_.LayerVersion(
            self,
            "OpenEXRLayer",
            layer_version_name="openexr-layer",
            description="Lambda layer with OpenEXR 3.4.4 for HDR image processing (requires NumpyLayer)",
            compatible_runtimes=[lambda_.Runtime.PYTHON_3_12],
            compatible_architectures=[
                lambda_.Architecture.X86_64,
                lambda_.Architecture.ARM_64,
            ],
            code=code,
        )


class FFProbeLayer(Construct):
    # Pin to a specific FFmpeg build version to avoid Lambda layer size limit issues.
    # The combined size of FFProbe + PyMediaInfo + Powertools + CommonLibraries layers
    # must stay under 250MB. Using 'latest' can cause builds to exceed this limit.
    # Version: autobuild-2025-11-30-12-53 (131MB compressed)
    FFMPEG_VERSION = "autobuild-2025-11-30-12-53"
    FFMPEG_FILENAME = "ffmpeg-N-121938-g2456a39581-linux64-gpl.tar.xz"
    FFMPEG_SHA256 = "fec46f7984352b988bda79be0521964a5148fecf7aa13db4e18a4383aa88e87f"  # pragma: allowlist secret

    def __init__(self, scope: Construct, id: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        if "CI" in os.environ:
            # Use pre-built layer in CI
            self.layer = lambda_.LayerVersion(
                self,
                "FFProbeLayer",
                layer_version_name="ffprobe-layer",
                compatible_runtimes=[lambda_.Runtime.PYTHON_3_12],
                description="Lambda layer with ffprobe for media metadata extraction",
                code=lambda_.Code.from_asset("dist/lambdas/layers/ffprobe"),
            )
        else:
            # Build locally with Docker
            self.layer = lambda_.LayerVersion(
                self,
                "FFProbeLayer",
                layer_version_name="ffprobe-layer",
                compatible_runtimes=[lambda_.Runtime.PYTHON_3_12],
                description="Lambda layer with ffprobe for media metadata extraction",
                code=lambda_.Code.from_asset(
                    path=".",
                    bundling=BundlingOptions(
                        command=[
                            "/bin/bash",
                            "-c",
                            f"""
                            set -euo pipefail

                            # Install download tools
                            yum update -y && yum install -y wget xz zip tar

                            # Create temporary workspace
                            TEMP_DIR=$(mktemp -d)
                            cd $TEMP_DIR
                            wget https://github.com/BtbN/FFmpeg-Builds/releases/download/{self.FFMPEG_VERSION}/{self.FFMPEG_FILENAME}
                            echo "{self.FFMPEG_SHA256}  {self.FFMPEG_FILENAME}" | sha256sum -c
                            mkdir ffmpeg-extracted
                            tar xvf {self.FFMPEG_FILENAME} -C ffmpeg-extracted
                            mkdir -p ffprobe/bin
                            cp ffmpeg-extracted/*/bin/ffprobe ffprobe/bin/
                            cd ffprobe
                            zip -9 -r $TEMP_DIR/ffprobe.zip .
                            cp $TEMP_DIR/ffprobe.zip /asset-output/

                            # Cleanup temporary files
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
    # Pin to a specific FFmpeg build version to avoid Lambda layer size limit issues.
    # The combined size of FFmpeg + other layers must stay under 250MB.
    # Using 'latest' can cause builds to exceed this limit as FFmpeg grows.
    # Version: autobuild-2025-11-30-12-53 (131MB compressed)
    FFMPEG_VERSION = "autobuild-2025-11-30-12-53"
    FFMPEG_FILENAME = "ffmpeg-N-121938-g2456a39581-linux64-gpl.tar.xz"
    FFMPEG_SHA256 = "fec46f7984352b988bda79be0521964a5148fecf7aa13db4e18a4383aa88e87f"  # pragma: allowlist secret

    def __init__(self, scope: Construct, id: str, **kwargs):
        """
        This layer bundles a static build of FFmpeg. It downloads a pinned FFmpeg release,
        verifies it with its SHA256 checksum, extracts the binary, and packages it into a Lambda layer.
        """
        super().__init__(scope, id, **kwargs)

        if "CI" in os.environ:
            # Use pre-built layer in CI
            self.layer = lambda_.LayerVersion(
                self,
                "FFmpegLayer",
                layer_version_name="ffmpeg-layer",
                compatible_runtimes=[lambda_.Runtime.PYTHON_3_12],
                description="Lambda layer with FFmpeg for video/audio processing",
                code=lambda_.Code.from_asset("dist/lambdas/layers/ffmpeg"),
            )
        else:
            # Build locally with Docker
            self.layer = lambda_.LayerVersion(
                self,
                "FFmpegLayer",
                layer_version_name="ffmpeg-layer",
                compatible_runtimes=[lambda_.Runtime.PYTHON_3_12],
                description="Lambda layer with FFmpeg for video/audio processing",
                code=lambda_.Code.from_asset(
                    path=".",
                    bundling=BundlingOptions(
                        command=[
                            "/bin/bash",
                            "-c",
                            f"""
                            set -e
                            yum update -y && yum install -y wget xz zip tar

                            # Create temporary workspace
                            TEMP_DIR=$(mktemp -d)
                            cd $TEMP_DIR
                            wget https://github.com/BtbN/FFmpeg-Builds/releases/download/{self.FFMPEG_VERSION}/{self.FFMPEG_FILENAME}
                            echo "{self.FFMPEG_SHA256}  {self.FFMPEG_FILENAME}" | sha256sum -c
                            mkdir ffmpeg-extracted
                            tar xvf {self.FFMPEG_FILENAME} -C ffmpeg-extracted
                            mkdir -p ffmpeg/bin
                            cp ffmpeg-extracted/*/bin/ffmpeg ffmpeg/bin/
                            cd ffmpeg
                            zip -9 -r $TEMP_DIR/ffmpeg.zip .
                            cp $TEMP_DIR/ffmpeg.zip /asset-output/

                            # Cleanup temporary files
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
    """
    Google Cloud Storage client library layer.

    Provides Google Cloud Storage SDK and authentication libraries for
    integrating with Google Cloud Platform storage services.

    Attributes:
        layer: The Lambda layer version containing GCS libraries
    """

    def __init__(self, scope: Construct, id: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        self.layer = LambdaLayer(
            self,
            "GoogleCloudStorageLayer",
            config=LambdaLayerConfig(
                entry="lambdas/layers/googleCloudStorage",
                description="Lambda layer with Google Cloud Storage and authentication libraries",
            ),
        )


class IngestMediaProcessorLayer(Construct):
    """
    Media container analysis layer.

    Provides utilities for analyzing media container formats and extracting
    technical information about media files during ingest processing.

    Attributes:
        layer: The Lambda layer version containing media processor utilities
    """

    def __init__(self, scope: Construct, construct_id: str, **kwargs):
        super().__init__(scope, construct_id, **kwargs)

        self.layer = LambdaLayer(
            self,
            "IngestMediaProcessorLayer",
            config=LambdaLayerConfig(
                entry="lambdas/layers/ingest_media_processor",
                description="Lambda layer for analyzing media container formats and metadata",
            ),
        )


class SearchLayer(Construct):
    """
    Search functionality layer.

    Provides search-related utilities and helpers for implementing
    search features across MediaLake.

    Attributes:
        layer: The Lambda layer version containing search utilities
    """

    def __init__(self, scope: Construct, id: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        self.layer_version = LambdaLayer(
            self,
            "SearchLayer",
            config=LambdaLayerConfig(
                entry="lambdas/layers/search",
                description="Lambda layer with search utilities and helpers",
            ),
        )

    @property
    def layer(self) -> lambda_.LayerVersion:
        """Returns the underlying Lambda layer version."""
        return self.layer_version.layer


class PyamlLayer(Construct):
    """
    PyYAML library layer.

    Provides PyYAML for parsing and generating YAML configuration files.

    Attributes:
        layer: The Lambda layer version containing PyYAML
    """

    def __init__(self, scope: Construct, id: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        self.layer_version = LambdaLayer(
            self,
            "PyamlLayer",
            config=LambdaLayerConfig(
                entry="lambdas/layers/pyaml",
                description="Lambda layer with PyYAML for YAML processing",
            ),
        )

    @property
    def layer(self) -> lambda_.LayerVersion:
        """Returns the underlying Lambda layer version."""
        return self.layer_version.layer


class ShortuuidLayer(Construct):
    """
    ShortUUID library layer.

    Provides shortuuid for generating concise, unambiguous, URL-safe UUIDs.

    Attributes:
        layer: The Lambda layer version containing shortuuid
    """

    def __init__(self, scope: Construct, id: str, **kwargs):
        super().__init__(scope, id, **kwargs)
        self.layer_version = LambdaLayer(
            self,
            "ShortuuidLayer",
            config=LambdaLayerConfig(
                entry="lambdas/layers/shortuuid",
                description="Lambda layer with shortuuid for generating concise UUIDs",
            ),
        )

    @property
    def layer(self) -> lambda_.LayerVersion:
        """Returns the underlying Lambda layer version."""
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
    Common utility libraries layer for MediaLake Lambda functions.

    Bundles shared Python utility modules that are used across multiple
    Lambda functions in the MediaLake application. Includes:
    - lambda_error_handler: Error handling utilities
    - lambda_middleware: Event normalization and pipeline management
    - lambda_utils: Common Lambda utilities and decorators
    - nodes_utils: Node-specific utilities (SMPTE timecode, duration formatting)
    - bedrock_utils: AWS Bedrock utilities with retry logic

    The layer uses CDK bundling to package flat .py files into the correct
    Lambda layer structure (`python/` directory) so they are automatically
    included in PYTHONPATH at runtime.

    Security: Uses official AWS Lambda Python 3.12 base image for bundling.
    Source-based hashing ensures layer updates when any utility file changes.
    No external dependencies - only internal MediaLake utilities.

    Args:
        entry: Path to common libraries directory (default: lambdas/common_libraries)

    Attributes:
        layer: The Lambda layer version containing common utilities
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
        # SOURCE hashing ensures layer version updates when utilities change.
        layer_code = lambda_.Code.from_asset(
            entry,
            asset_hash_type=AssetHashType.SOURCE,
            bundling=BundlingOptions(
                # Use official Lambda-compatible Python 3.12 image for bundling
                image=DockerImage.from_registry("public.ecr.aws/lambda/python:3.12"),
                # Override entrypoint to run our custom commands
                entrypoint=["bash", "-c"],
                # 1) Create python/ directory in the output (Lambda layer structure)
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
