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
        self.layer = LambdaLayer(
            self,
            "SearchLayer",
            config=LambdaLayerConfig(
                entry="lambdas/layers/search", description="A Lambda layer for search"
            ),
        )


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
