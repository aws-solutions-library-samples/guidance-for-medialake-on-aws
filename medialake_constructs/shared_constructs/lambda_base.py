from aws_cdk import (
    aws_lambda as lambda_,
    Stack,
    aws_logs as logs,
    aws_iam as iam,
    RemovalPolicy,
    Duration,
)
from constructs import Construct
from aws_cdk.aws_lambda_python_alpha import PythonFunction, BundlingOptions
from medialake_constructs.shared_constructs.lambda_layers import (
    PowertoolsLayer,
    PowertoolsLayerConfig,
)
from typing import Dict, Optional, List
from dataclasses import dataclass
import constants
import re

# Constants
DEFAULT_MEMORY_SIZE = 128
DEFAULT_TIMEOUT_MINUTES = 5
DEFAULT_RUNTIME = lambda_.Runtime.PYTHON_3_12
DEFAULT_ARCHITECTURE = lambda_.Architecture.X86_64
LOG_RETENTION = logs.RetentionDays.SIX_MONTHS
MAX_LAMBDA_NAME_LENGTH = 64
MAX_ROLE_NAME_LENGTH = 64
MAX_LOG_GROUP_NAME_LENGTH = 512


def validate_lambda_resources_names(base_name: str, id: str) -> str:
    # Combine base_name and id
    lambda_full_name = f"{base_name}-{id}"

    # Check if the base_name is empty
    if not base_name:
        raise ValueError("Base name cannot be empty")

    # Check if the full name contains invalid characters
    if not re.match(r"^[a-zA-Z0-9_-]+$", lambda_full_name):
        raise ValueError(
            "Resource name can only contain alphanumeric characters, "
            "hyphens, and underscores"
        )

    # Check Lambda function name length
    if len(lambda_full_name) > MAX_LAMBDA_NAME_LENGTH:
        raise ValueError(
            f"Lambda function name '{lambda_full_name}' exceeds the "
            f"maximum length of {MAX_LAMBDA_NAME_LENGTH} characters"
        )

    # Check IAM role name length (prefix with 'role-')
    role_name = f"role-{lambda_full_name}"
    if len(role_name) > MAX_ROLE_NAME_LENGTH:
        raise ValueError(
            f"IAM role name '{role_name}' exceeds the maximum length of "
            f"{MAX_ROLE_NAME_LENGTH} characters"
        )

    # Check CloudWatch log group name length
    log_group_name = f"/aws/lambda/{lambda_full_name}"
    if len(log_group_name) > MAX_LOG_GROUP_NAME_LENGTH:
        raise ValueError(
            f"CloudWatch log group name '{log_group_name}' exceeds the "
            f"maximum length of {MAX_LOG_GROUP_NAME_LENGTH} characters"
        )

    return lambda_full_name


@dataclass
class LambdaConfig:
    """Configuration for Lambda function creation."""
    name: str
    entry: Optional[str] = None
    memory_size: int = DEFAULT_MEMORY_SIZE
    timeout_minutes: int = DEFAULT_TIMEOUT_MINUTES
    environment_variables: Optional[Dict[str, str]] = None
    runtime: lambda_.Runtime = DEFAULT_RUNTIME
    architecture: lambda_.Architecture = DEFAULT_ARCHITECTURE
    layers: Optional[List[str]] = None
    iam_role_name: Optional[str] = None


class Lambda(Construct):
    """
    A construct for creating a standardized Lambda function with common
    configurations.
    """

    def __init__(
        self,
        scope: Construct,
        id: str,
        config: LambdaConfig,
        **kwargs
    ):
        """
        Initialize the LambdaBase construct.

        :param scope: The scope in which to define this construct.
        :param id: The scoped construct ID.
        :param config: Configuration for the Lambda function.
        :param kwargs: Additional keyword arguments.
        """
        super().__init__(scope, id, **kwargs)

        if config.memory_size < 128 or config.memory_size > 10240:
            raise ValueError("Memory size must be between 128 MB and 10,240 MB")
        if config.timeout_minutes < 1 or config.timeout_minutes > 15:
            raise ValueError("Timeout must be between 1 and 15 minutes")
        stack = Stack.of(self)

        lambda_function_name = validate_lambda_resources_names(
            config.name, id
        )
        lambda_runtime = config.runtime

        # Create powertools layer
        power_tools_layer_config = PowertoolsLayerConfig()
        powertools_layer = PowertoolsLayer(
            self, "PowertoolsLayer", config=power_tools_layer_config
        )
        layer_objects = [powertools_layer.layer]

        # Create Log Group
        log_group_name = f"/aws/lambda/{lambda_function_name}-logs"
        lambda_log_group = logs.LogGroup(
            self,
            "LambdaLogGroup",
            log_group_name=log_group_name,
            retention=LOG_RETENTION,
        )
        lambda_log_group.apply_removal_policy(RemovalPolicy.DESTROY)

        # AWS Lambda basic execution role policy
        basic_execution_policy = iam.ManagedPolicy.from_aws_managed_policy_name(
            "service-role/AWSLambdaBasicExecutionRole"
        )

        if config.iam_role_name:
            role_id = f"{lambda_function_name}ExecutionRole"
            self._lambda_role = iam.Role(
                self,
                role_id,
                assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
                role_name=config.iam_role_name,
                managed_policies=[basic_execution_policy],
            )
        else:
            role_id = f"{lambda_function_name}ExecutionRole"
            self._lambda_role = iam.Role(
                self,
                role_id,
                assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
                managed_policies=[basic_execution_policy],
                role_name=f"{lambda_function_name}ExecutionRole"
            )

        # Apply removal policy to the role
        self._lambda_role.apply_removal_policy(RemovalPolicy.DESTROY)

        self._lambda_role.add_to_principal_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["logs:CreateLogStream", "logs:PutLogEvents"],
                resources=[lambda_log_group.log_group_arn],
            )
        )

        # Prepare Lambda function properties
        lambda_props = {
            "function_name": lambda_function_name,
            "entry": config.entry or f"lambdas/{lambda_function_name}",
            "handler": "lambda_handler",
            "role": self._lambda_role,
            "log_group": lambda_log_group,
            "runtime": lambda_runtime,
            "architecture": config.architecture,
            "timeout": Duration.minutes(config.timeout_minutes),
            "memory_size": config.memory_size,
            "bundling": BundlingOptions(
                asset_excludes=[".venv", "cdk.out"],
            ),
            "tracing": lambda_.Tracing.ACTIVE,
            "layers": layer_objects,
        }
        if config.environment_variables:
            lambda_environment_variables = config.environment_variables
            lambda_environment_variables["external_payload_s3_bucket"] = (
                f"{constants.WORKFLOW_PAYLOAD_TEMP_BUCKET}-{stack.region}"
            )
            lambda_props["environment"] = config.environment_variables

        # Create the Lambda function
        self._function = PythonFunction(self, "StandardLambda", **lambda_props)

    @property
    def function(self) -> lambda_.Function:
        """Get the underlying Lambda function."""
        return self._function

    @property
    def function_name(self) -> str:
        """Get the name of the Lambda function."""
        return self._function.function_name

    @property
    def function_arn(self) -> str:
        """Get the ARN of the Lambda function."""
        return self._function.function_arn

    @property
    def lambda_role(self) -> iam.Role:
        """Get the IAM role associated with the Lambda function."""
        return self._lambda_role
