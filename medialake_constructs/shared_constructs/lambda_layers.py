import os
from aws_cdk import Stack, aws_lambda as lambda_, BundlingOptions
from constructs import Construct
from aws_cdk.aws_lambda_python_alpha import PythonLayerVersion
from dataclasses import dataclass


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
            f"arn:{stack.partition}:lambda:{stack.region}:017000801446:layer:AWSLambdaPowertoolsPythonV2{'Arm64' if config.architecture == lambda_.Architecture.ARM_64 else ''}:{config.layer_version}",
        )

class ExiftoolLayer(Construct):
    def __init__(self, scope: Construct, id: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        # Define the Lambda layer from the zip file
        self.layer = lambda_.LayerVersion(
            self,
            "ExiftoolLayer",
            code=lambda_.Code.from_asset(
                os.path.join(
                    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                    "medialake_constructs",
                    "shared_constructs",
                    "exiftool_x86_64.zip"
                )
            ),
            description="Exiftool binary and dependencies",
            compatible_runtimes=[lambda_.Runtime.PYTHON_3_12]
        )

    @property
    def layer_version(self) -> lambda_.LayerVersion:
        return self.layer
    
class JinjaLambdaLayer(Construct):
    def __init__(self, scope: Construct, id: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        # Define the Lambda layer
        self.layer = PythonLayerVersion(
            self,
            "JinjaLayer",
            entry="lambdas/layers/jinja",
            compatible_runtimes=[lambda_.Runtime.PYTHON_3_12],
            description="A Lambda layer with Jinja2 library",
        )


class OpenSearchPyLayer(Construct):
    def __init__(self, scope: Construct, id: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        # Define the Lambda layer
        self.layer = PythonLayerVersion(
            self,
            "OpenSearchPyLayer",
            entry="lambdas/layers/opensearchpy",
            compatible_runtimes=[lambda_.Runtime.PYTHON_3_12],
            description="A Lambda layer with open serch py library",
        )


class PynamoDbLambdaLayer(Construct):
    def __init__(self, scope: Construct, id: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        # Define the Lambda layer
        self.layer = PythonLayerVersion(
            self,
            "PynamoDbLambdaLayer",
            entry="lambdas/layers/pynamodb",
            compatible_runtimes=[lambda_.Runtime.PYTHON_3_12],
            description="A Lambda layer with pynamodb library",
        )


class PyMediaInfo(Construct):
    def __init__(self, scope: Construct, id: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        # Define the Lambda layer
        self.layer = PythonLayerVersion(
            self,
            "PyMediaInfoLayer",
            entry="lambdas/layers/pymediainfo",
            compatible_runtimes=[lambda_.Runtime.PYTHON_3_12],
            description="A Lambda layer with pymediainfo library",
        )


class GoogleCloudStorageLayer(Construct):
    def __init__(self, scope: Construct, id: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        # Define the Lambda layer
        self.layer = PythonLayerVersion(
            self,
            "GoogleCloudStorageLayer",
            entry="lambdas/layers/googleCloudStorage",
            compatible_runtimes=[lambda_.Runtime.PYTHON_3_12],
            description="A Lambda layer with google cloud storage and google auth library",
        )


class IngestMediaProcessorLayer(Construct):
    def __init__(self, scope: Construct, construct_id: str, **kwargs):
        super().__init__(scope, construct_id, **kwargs)

        # Define the Lambda layer
        self.layer = PythonLayerVersion(
            self,
            "IngestMediaProcessorLayer",
            entry="lambdas/layers/ingest_media_processor",
            compatible_runtimes=[lambda_.Runtime.PYTHON_3_12],
            description="A Lambda layer for analyzing media container media info",
        )


class SearchLayer(Construct):
    def __init__(self, scope: Construct, id: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        # Define the Lambda layer
        self.layer = PythonLayerVersion(
            self,
            "SearchLayer",
            entry="lambdas/layers/search",
            compatible_runtimes=[lambda_.Runtime.PYTHON_3_12],
            description="A Lambda layer for search",
        )

    @property
    def layer_version(self) -> lambda_.LayerVersion:
        return self.layer
