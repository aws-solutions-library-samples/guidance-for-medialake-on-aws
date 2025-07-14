import os
from dataclasses import dataclass, field
from typing import Optional

from aws_cdk import aws_lambda as lambda_
from aws_cdk.aws_lambda_python_alpha import PythonLayerVersion
from aws_lambda_powertools import Logger
from constructs import Construct

from config import DIST_PATH

# Constants
DEFAULT_RUNTIMES = [lambda_.Runtime.PYTHON_3_12]
DEFAULT_ARCHITECTURES = [lambda_.Architecture.X86_64, lambda_.Architecture.ARM_64]


@dataclass
class PowertoolsLayerConfig:
    architecture: str = lambda_.Architecture.X86_64
    layer_version: str = "68"


@dataclass
class LambdaLayerConfig:
    """
    Configuration dataclass for Lambda layer creation.

    Attributes:
        entry (Optional[str]): Entry point for the Lambda function code
        compatible_runtimes (List[lambda_.Runtime]): Lambda runtime (default: PYTHON_3_13)
        compatible_architectures (
                                      List[lambda_.Architecture]): CPU architecture (default: [X86_64,
                                      ARM_64]
                                  )
        description (Optional[str]): Layer description
    """

    entry: Optional[str] = None
    compatible_runtimes: list = field(default_factory=lambda: DEFAULT_RUNTIMES)
    compatible_architectures: list = field(
        default_factory=lambda: DEFAULT_ARCHITECTURES
    )
    description: Optional[str] = None


class LambdaLayer(Construct):
    """
    A CDK construct for creating standardized Lambda layers with common configurations.

    Example:
        ```python
        config = LambdaLayerConfig(
            entry="path/to/layer"
        )
        lambda_layer = LambdaLayer(self, "MyLayer", config)
        ```
    """

    def __init__(
        self, scope: Construct, construct_id: str, config: LambdaLayerConfig, **kwargs
    ):
        """
        Initialize the LambdaLayer construct.

        Args:
            scope (Construct): The scope in which to define this construct
            construct_id (str): The scoped construct ID
            config (LambdaLayerConfig): Configuration for the Lambda layer
            **kwargs: Additional keyword arguments passed to the parent construct
        """
        super().__init__(scope, construct_id, **kwargs)

        logger = Logger()
        logger.debug(f"Initializing LambdaLayer construct with config: {config}")

        common_layer_props = {
            "entry": config.entry,
            "compatible_runtimes": config.compatible_runtimes,
            "compatible_architectures": config.compatible_architectures,
        }

        # If the deployment is part of a CI/CD pipeline, avoid using PythonLayerVersion as it's relying on DnD
        # CI env var is exposed by Gitlab. TODO: add Github specific env var
        if "CI" in os.environ:

            # Replace the entry path to point to the dist folder
            dist_path = os.path.join(DIST_PATH, common_layer_props["entry"])
            del common_layer_props["entry"]

            self._layer = lambda_.LayerVersion(
                self,
                "StandardPythonLayer",
                code=lambda_.Code.from_asset(dist_path),
                **common_layer_props,
            )
        else:
            self._layer = PythonLayerVersion(
                self,
                "StandardPythonLayer",
                **common_layer_props,
            )

    @property
    def layer(self) -> lambda_.ILayerVersion:
        """
        Get the underlying Lambda layer.

        Returns:
            lambda_.ILayerVersion: The created Lambda layer instance
        """
        return self._layer

    @property
    def layer_version_arn(self) -> str:
        return self._layer.layer_version_arn
