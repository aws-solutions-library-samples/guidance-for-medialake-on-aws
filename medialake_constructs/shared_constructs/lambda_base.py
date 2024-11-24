"""
Lambda base construct module that provides standardized Lambda function creation with common configurations.

This module contains utilities and classes for creating AWS Lambda functions with consistent
configuration, logging, IAM roles, and other AWS resources. It implements best practices for
Lambda deployment including standardized naming conventions and resource validation.
"""

from typing import Dict, Optional, List
from dataclasses import dataclass
import re
import logging

from aws_cdk import (
    aws_lambda as lambda_,
    Stack,
    aws_logs as logs,
    aws_iam as iam,
    aws_ec2 as ec2,
    RemovalPolicy,
    Duration,
)
from aws_cdk.aws_lambda_python_alpha import (
    PythonFunction,
    BundlingOptions,
    PythonLayerVersion,
)
from constructs import Construct
from medialake_constructs.shared_constructs.lambda_layers import (
    PowertoolsLayer,
    PowertoolsLayerConfig,
)
from aws_lambda_powertools import Logger

from config import WORKFLOW_PAYLOAD_TEMP_BUCKET

# Constants
DEFAULT_MEMORY_SIZE = 128
DEFAULT_TIMEOUT_MINUTES = 5
DEFAULT_RUNTIME = lambda_.Runtime.PYTHON_3_12
DEFAULT_ARCHITECTURE = lambda_.Architecture.X86_64
LOG_RETENTION = logs.RetentionDays.SIX_MONTHS
MAX_LAMBDA_NAME_LENGTH = 64
MAX_ROLE_NAME_LENGTH = 64
MAX_LOG_GROUP_NAME_LENGTH = 512

# Add debug logging in key methods


def validate_lambda_resources_names(base_name: str, construct_id: str) -> str:
    """
    Validates and constructs Lambda resource names ensuring they meet AWS requirements.
    """
    logger = Logger()
    logger.debug(
        f"Validating lambda resource names - base_name: {base_name}, construct_id: {construct_id}"
    )

    # Combine base_name and id
    lambda_full_name = f"{base_name}-{construct_id}"
    logger.debug(f"Generated lambda_full_name: {lambda_full_name}")

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

    logger.debug(f"Lambda resource names validated successfully: {lambda_full_name}")
    return lambda_full_name


@dataclass
class LambdaConfig:
    """
    Configuration dataclass for Lambda function creation.

    Attributes:
        name (str): Name of the Lambda function
        entry (Optional[str]): Entry point for the Lambda function code
        memory_size (int): Memory allocation in MB (default: 128)
        timeout_minutes (int): Function timeout in minutes (default: 5)
        environment_variables (Optional[Dict[str, str]]): Environment variables for the function
        runtime (lambda_.Runtime): Lambda runtime (default: PYTHON_3_12)
        architecture (lambda_.Architecture): CPU architecture (default: X86_64)
        layers (Optional[List[PythonLayerVersion]]): Lambda layers to attach
        iam_role_name (Optional[str]): Custom IAM role name
        vpc (Optional[ec2.IVpc]): VPC configuration for the Lambda
    """

    name: str
    entry: Optional[str] = None
    memory_size: int = DEFAULT_MEMORY_SIZE
    timeout_minutes: int = DEFAULT_TIMEOUT_MINUTES
    environment_variables: Optional[Dict[str, str]] = None
    runtime: lambda_.Runtime = DEFAULT_RUNTIME
    architecture: lambda_.Architecture = DEFAULT_ARCHITECTURE
    layers: Optional[List[PythonLayerVersion]] = None
    iam_role_name: Optional[str] = None
    vpc: Optional[ec2.IVpc] = None


class Lambda(Construct):
    """
    A CDK construct for creating standardized Lambda functions with common configurations.

    This construct creates a Lambda function with standardized configurations including:
    - IAM roles and policies
    - CloudWatch log groups
    - Lambda layers (including AWS PowerTools)
    - VPC configuration (optional)
    - Environment variables
    - Resource naming and validation

    Example:
        ```python
        config = LambdaConfig(
            name="my-function",
            memory_size=256,
            timeout_minutes=10
        )
        lambda_function = Lambda(self, "MyFunction", config)
        ```
    """

    def __init__(
        self, scope: Construct, construct_id: str, config: LambdaConfig, **kwargs
    ):
        """
        Initialize the Lambda construct.

        Args:
            scope (Construct): The scope in which to define this construct
            construct_id (str): The scoped construct ID
            config (LambdaConfig): Configuration for the Lambda function
            **kwargs: Additional keyword arguments passed to the parent construct

        Raises:
            ValueError: If memory size or timeout values are invalid
        """
        super().__init__(scope, construct_id, **kwargs)

        logger = Logger()
        logger.debug(f"Initializing Lambda construct with config: {config}")

        # Validate config values
        if config.memory_size < 128 or config.memory_size > 10240:
            logger.error(f"Invalid memory size: {config.memory_size}")
            raise ValueError("Memory size must be between 128 MB and 10,240 MB")

        if config.timeout_minutes < 1 or config.timeout_minutes > 15:
            logger.error(f"Invalid timeout: {config.timeout_minutes}")
            raise ValueError("Timeout must be between 1 and 15 minutes")

        stack = Stack.of(self)
        logger.debug(f"Using stack region: {stack.region}")

        lambda_function_name = validate_lambda_resources_names(
            config.name, construct_id
        )
        logger.debug(f"Validated function name: {lambda_function_name}")

        # Create powertools layer
        logger.debug("Creating PowerTools layer")
        power_tools_layer_config = PowertoolsLayerConfig()
        powertools_layer = PowertoolsLayer(
            self, "PowertoolsLayer", config=power_tools_layer_config
        )
        layer_objects = [powertools_layer.layer]

        # Add layers from config
        if config.layers:
            logger.debug(f"Adding {len(config.layers)} additional layers")
            layer_objects.extend(config.layers)

        # Create Log Group
        log_group_name = f"/aws/lambda/{lambda_function_name}-logs"
        logger.debug(f"Creating log group: {log_group_name}")
        lambda_log_group = logs.LogGroup(
            self,
            "LambdaLogGroup",
            log_group_name=log_group_name,
            retention=LOG_RETENTION,
        )
        lambda_log_group.apply_removal_policy(RemovalPolicy.DESTROY)

        # Create IAM role
        logger.debug("Setting up IAM role")
        basic_execution_policy = iam.ManagedPolicy.from_aws_managed_policy_name(
            "service-role/AWSLambdaBasicExecutionRole"
        )

        if config.iam_role_name:
            role_id = f"{lambda_function_name}ExecutionRole"
            logger.debug(f"Using custom role name: {config.iam_role_name}")
            self._lambda_role = iam.Role(
                self,
                role_id,
                assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
                role_name=config.iam_role_name,
                managed_policies=[basic_execution_policy],
            )
        else:
            role_id = f"{lambda_function_name}ExecutionRole"
            logger.debug(f"Creating default role: {role_id}")
            self._lambda_role = iam.Role(
                self,
                role_id,
                assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
                managed_policies=[basic_execution_policy],
            )

        # Prepare Lambda props
        logger.debug("Preparing Lambda function properties")
        lambda_props = {
            "function_name": lambda_function_name,
            "entry": config.entry or f"lambdas/{lambda_function_name}",
            "handler": "lambda_handler",
            "role": self._lambda_role,
            "log_group": lambda_log_group,
            "runtime": config.runtime,
            "architecture": config.architecture,
            "timeout": Duration.minutes(config.timeout_minutes),
            "memory_size": config.memory_size,
            "bundling": BundlingOptions(
                asset_excludes=[".venv", "cdk.out"],
            ),
            "tracing": lambda_.Tracing.ACTIVE,
            "layers": layer_objects,
        }

        # Add environment variables if provided
        if config.environment_variables:
            logger.debug("Adding environment variables")
            lambda_environment_variables = config.environment_variables
            lambda_environment_variables["external_payload_s3_bucket"] = (
                f"{WORKFLOW_PAYLOAD_TEMP_BUCKET}-{stack.region}"
            )
            lambda_props["environment"] = config.environment_variables

        # Add VPC if provided
        if config.vpc:
            logger.debug(f"Adding VPC configuration: {config.vpc}")
            lambda_vpc = config.vpc
            lambda_props["vpc"] = lambda_vpc

        # Create the Lambda function
        logger.debug("Creating Lambda function with properties")
        try:
            self._function = PythonFunction(self, "StandardLambda", **lambda_props)
            logger.info(f"Successfully created Lambda function: {lambda_function_name}")
        except Exception as e:
            logger.error(f"Failed to create Lambda function: {str(e)}", exc_info=True)
            raise

    @property
    def function(self) -> lambda_.Function:
        """
        Get the underlying Lambda function.

        Returns:
            lambda_.Function: The created Lambda function instance
        """
        return self._function

    @property
    def function_name(self) -> str:
        """
        Get the name of the Lambda function.

        Returns:
            str: The function name
        """
        return self._function.function_name

    @property
    def function_arn(self) -> str:
        """
        Get the ARN of the Lambda function.

        Returns:
            str: The function ARN
        """
        return self._function.function_arn

    @property
    def lambda_role(self) -> iam.Role:
        """
        Get the IAM role associated with the Lambda function.

        Returns:
            iam.Role: The IAM role attached to the Lambda function
        """
        return self._lambda_role
