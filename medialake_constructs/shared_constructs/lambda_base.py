"""
Lambda base construct module that provides standardized Lambda function creation with common configurations.

This module contains utilities and classes for creating AWS Lambda functions with consistent
configuration, logging, IAM roles, and other AWS resources. It implements best practices for
Lambda deployment including standardized naming conventions and resource validation.
"""

import datetime
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from aws_cdk import Duration, RemovalPolicy, Stack
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_efs as efs
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_logs as logs
from aws_cdk.aws_lambda_nodejs import BundlingOptions as NodeJSBundlingOptions
from aws_cdk.aws_lambda_nodejs import NodejsFunction
from aws_cdk.aws_lambda_python_alpha import (
    BundlingOptions,
    PythonFunction,
    PythonLayerVersion,
)
from aws_lambda_powertools import Logger
from constructs import Construct

from config import DIST_PATH
from config import config as env_config
from medialake_constructs.shared_constructs.lambda_layers import (
    CommonLibrariesLayer,
    PowertoolsLayer,
    PowertoolsLayerConfig,
)

# Constants
DEFAULT_MEMORY_SIZE = 128
DEFAULT_TIMEOUT_MINUTES = 5
DEFAULT_RUNTIME = lambda_.Runtime.PYTHON_3_12
DEFAULT_ARCHITECTURE = lambda_.Architecture.X86_64
MAX_LAMBDA_NAME_LENGTH = 64
MAX_ROLE_NAME_LENGTH = 64
MAX_LOG_GROUP_NAME_LENGTH = 512


def get_log_retention_from_config() -> logs.RetentionDays:
    """
    Get the log retention setting from config and convert to RetentionDays enum.

    Returns:
        logs.RetentionDays: The retention period based on config
    """
    # Access the logging config properly from Pydantic model
    try:
        if hasattr(env_config, "logging") and env_config.logging:
            retention_days = getattr(
                env_config.logging, "lambda_cloudwatch_log_retention_days", 180
            )
        else:
            retention_days = 180  # Default fallback
    except (AttributeError, TypeError):
        retention_days = 180  # Default fallback

    # Map days to RetentionDays enum values
    retention_mapping = {
        1: logs.RetentionDays.ONE_DAY,
        3: logs.RetentionDays.THREE_DAYS,
        5: logs.RetentionDays.FIVE_DAYS,
        7: logs.RetentionDays.ONE_WEEK,
        14: logs.RetentionDays.TWO_WEEKS,
        30: logs.RetentionDays.ONE_MONTH,
        60: logs.RetentionDays.TWO_MONTHS,
        90: logs.RetentionDays.THREE_MONTHS,
        120: logs.RetentionDays.FOUR_MONTHS,
        150: logs.RetentionDays.FIVE_MONTHS,
        180: logs.RetentionDays.SIX_MONTHS,
        365: logs.RetentionDays.ONE_YEAR,
        400: logs.RetentionDays.THIRTEEN_MONTHS,
        545: logs.RetentionDays.EIGHTEEN_MONTHS,
        731: logs.RetentionDays.TWO_YEARS,
        1827: logs.RetentionDays.FIVE_YEARS,
        3653: logs.RetentionDays.TEN_YEARS,
    }

    # Find the closest matching retention period
    if retention_days in retention_mapping:
        return retention_mapping[retention_days]

    # Find the closest higher value if exact match not found
    sorted_days = sorted(retention_mapping.keys())
    for days in sorted_days:
        if days >= retention_days:
            return retention_mapping[days]

    # If retention_days is higher than any predefined value, use infinite retention
    return logs.RetentionDays.INFINITE


# Get log retention from config
LOG_RETENTION = get_log_retention_from_config()


def validate_lambda_resources_names(base_name: str) -> str:
    """
    Validates and constructs Lambda resource names.
    """
    logger = Logger()
    logger.debug(f"Validating lambda resource names - base_name: {base_name}")

    # Combine base_name and id
    lambda_full_name = (
        f"{env_config.resource_prefix}_{base_name}_{env_config.environment}"
    )
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

    # Note: IAM role name length is handled by truncation in the Lambda constructor

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
        environment_variables (
                                   Optional[Dict[str,
                                   str]]
                               ): Environment variables for the function
        runtime (lambda_.Runtime): Lambda runtime (default: PYTHON_3_13)
        architecture (lambda_.Architecture): CPU architecture (default: X86_64)
        layers (Optional[List[PythonLayerVersion]]): Lambda layers to attach
        iam_role_name (Optional[str]): Custom IAM role name
        vpc (Optional[ec2.IVpc]): VPC configuration for the Lambda
        log_removal_policy (Optional[RemovalPolicy]): Removal policy for the CloudWatch log group (default: DESTROY)
        python_bundling (Optional[BundlingOptions]): Bundling options for Python functions
        nodejs_bundling (Optional[NodeJSBundlingOptions]): Bundling options for Node.js functions
        filesystem_access_point (Optional[efs.IAccessPoint]): EFS access point for Lambda filesystem
        filesystem_mount_path (Optional[str]): Mount path for EFS filesystem
        snap_start (Optional[bool]): Enable SnapStart for faster cold starts (default: False).
        Note: SnapStart is supported for Java 11+, Python 3.12+, and .NET 8+ runtimes.
    """

    name: Optional[str] = None
    entry: Optional[str] = None
    memory_size: int = DEFAULT_MEMORY_SIZE
    timeout_minutes: int = DEFAULT_TIMEOUT_MINUTES
    environment_variables: Optional[Dict[str, str]] = None
    runtime: lambda_.Runtime = DEFAULT_RUNTIME
    architecture: lambda_.Architecture = DEFAULT_ARCHITECTURE
    layers: Optional[List[PythonLayerVersion]] = None
    iam_role_name: Optional[str] = None
    vpc: Optional[ec2.IVpc] = None
    security_groups: Optional[List[ec2.ISecurityGroup]] = None
    iam_role_boundary_policy: Optional[iam.ManagedPolicy] = None
    lambda_handler: Optional[str] = "lambda_handler"
    log_removal_policy: Optional[RemovalPolicy] = RemovalPolicy.DESTROY
    python_bundling: Optional[BundlingOptions] = None
    nodejs_bundling: Optional[NodeJSBundlingOptions] = None
    reserved_concurrent_executions: Optional[int] = None
    filesystem_access_point: Optional[efs.IAccessPoint] = None
    filesystem_mount_path: Optional[str] = None
    snap_start: Optional[bool] = False


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
    - Common libraries integration via Docker bundling (Python) or local copying (Node.js)

    Common Libraries Handling:
    - Python functions: Common libraries are automatically copied during Docker bundling,
      eliminating the need for local file duplication in Lambda directories.
    - Node.js functions: Common libraries are still copied locally due to different bundling process.

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

    # Class-level shared layer instances per stack to avoid duplicate layer creation
    _shared_common_libraries_layers = {}

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

        # Get the actual retention days value for logging
        try:
            if hasattr(env_config, "logging") and env_config.logging:
                config_retention_days = getattr(
                    env_config.logging, "lambda_cloudwatch_log_retention_days", 180
                )
            else:
                config_retention_days = 180
        except (AttributeError, TypeError):
            config_retention_days = 180

        logger.debug(
            f"Using log retention from config: {LOG_RETENTION} (based on {config_retention_days} days)"
        )

        # Validate config values
        if config.memory_size < 128 or config.memory_size > 10240:
            logger.error(f"Invalid memory size: {config.memory_size}")
            raise ValueError("Memory size must be between 128 MB and 10,240 MB")

        if config.timeout_minutes < 1 or config.timeout_minutes > 15:
            logger.error(f"Invalid timeout: {config.timeout_minutes}")
            raise ValueError("Timeout must be between 1 and 15 minutes")

        stack = Stack.of(self)
        logger.debug(f"Using stack region: {stack.region}")

        if config.name is not None:
            lambda_function_name = validate_lambda_resources_names(config.name)
        else:
            lambda_function_name = f"{construct_id}-{env_config.environment}"
        logger.debug(f"Validated function name: {lambda_function_name}")

        # Create powertools layer
        logger.debug("Creating PowerTools layer")
        power_tools_layer_config = PowertoolsLayerConfig()
        powertools_layer = PowertoolsLayer(
            self, "PowertoolsLayer", config=power_tools_layer_config
        )

        # Create or reuse common libraries layer (per-stack singleton pattern)
        stack_id = stack.stack_name
        if stack_id not in Lambda._shared_common_libraries_layers:
            logger.debug(
                f"Creating shared Common Libraries layer for stack: {stack_id}"
            )
            # Use the stack variable that was already created above
            Lambda._shared_common_libraries_layers[stack_id] = CommonLibrariesLayer(
                stack, "CommonLibsLayer"
            )
        else:
            logger.debug(
                f"Reusing existing Common Libraries layer for stack: {stack_id}"
            )

        common_libraries_layer = Lambda._shared_common_libraries_layers[stack_id]

        layer_objects = [powertools_layer.layer, common_libraries_layer.layer]

        # Add layers from config
        if config.layers:
            logger.debug(f"Adding {len(config.layers)} additional layers")
            layer_objects.extend(config.layers)

        # Create Log Group with retention from config
        log_group_name = f"/aws/lambda/{lambda_function_name}-logs"
        logger.debug(
            f"Creating log group: {log_group_name} with retention: {LOG_RETENTION}"
        )
        lambda_log_group = logs.LogGroup(
            self,
            "LambdaLogGroup",
            log_group_name=log_group_name,
            retention=LOG_RETENTION,
        )
        lambda_log_group.apply_removal_policy(config.log_removal_policy)

        # Create IAM role
        logger.debug("Setting up IAM role")

        ## Creation of IAM role for Lambda function
        role_id = f"{lambda_function_name}ExecutionRole"
        role_props = {
            "assumed_by": iam.ServicePrincipal("lambda.amazonaws.com"),
        }

        if config.iam_role_name:
            logger.debug(f"Using custom role name: {config.iam_role_name}")
            # Truncate role name if it exceeds 64 characters
            if len(config.iam_role_name) > MAX_ROLE_NAME_LENGTH:
                logger.warning(
                    f"IAM role name '{config.iam_role_name}' exceeds {MAX_ROLE_NAME_LENGTH} characters. "
                    f"Truncating to '{config.iam_role_name[:MAX_ROLE_NAME_LENGTH]}'"
                )
                role_name = config.iam_role_name[:MAX_ROLE_NAME_LENGTH]
            else:
                role_name = config.iam_role_name
            logger.debug(f"Final role name: {role_name}")
            role_props["role_name"] = role_name
        else:
            # Handle default role name truncation
            default_role_name = f"role-{lambda_function_name}"
            if len(default_role_name) > MAX_ROLE_NAME_LENGTH:
                logger.warning(
                    f"IAM role name '{default_role_name}' exceeds {MAX_ROLE_NAME_LENGTH} characters. "
                    f"Truncating to '{default_role_name[:MAX_ROLE_NAME_LENGTH]}'"
                )
                role_name = default_role_name[:MAX_ROLE_NAME_LENGTH]
            else:
                role_name = default_role_name
            logger.debug(f"Using role name: {role_name}")
            role_props["role_name"] = role_name

        if config.iam_role_boundary_policy:
            logger.debug("Adding boundary permissions to role")
            role_props["permissions_boundary"] = config.iam_role_boundary_policy

        self._lambda_role = iam.Role(self, role_id, **role_props)

        logger.debug("Adding AWSLambdaBasicExecutionRole to Lambda role")
        self._lambda_role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name(
                "service-role/AWSLambdaBasicExecutionRole"
            )
        )
        # Prepare common Lambda props
        logger.debug("Preparing Lambda function properties")
        common_lambda_props = {
            "function_name": lambda_function_name,
            "handler": config.lambda_handler,
            "entry": config.entry or f"lambdas/{lambda_function_name}",
            "role": self._lambda_role,
            "log_group": lambda_log_group,
            "runtime": config.runtime,
            "architecture": config.architecture,
            "timeout": Duration.minutes(config.timeout_minutes),
            "memory_size": config.memory_size,
            "tracing": lambda_.Tracing.ACTIVE,
            "layers": layer_objects,
        }

        # Add reserved concurrent executions if provided
        if config.reserved_concurrent_executions is not None:
            logger.debug(
                f"Setting reserved concurrent executions to {config.reserved_concurrent_executions}"
            )
            common_lambda_props["reserved_concurrent_executions"] = (
                config.reserved_concurrent_executions
            )

        # Add environment variables if provided
        if config.environment_variables:
            logger.debug("Adding environment variables")
            lambda_environment_variables = config.environment_variables
            lambda_environment_variables["RESOURCE_PREFIX"] = env_config.resource_prefix
            lambda_environment_variables["ENVIRONMENT"] = env_config.environment
            lambda_environment_variables["METRICS_NAMESPACE"] = (
                env_config.resource_prefix
            )
        else:
            lambda_environment_variables = {}
            lambda_environment_variables["RESOURCE_PREFIX"] = env_config.resource_prefix
            lambda_environment_variables["ENVIRONMENT"] = env_config.environment
            lambda_environment_variables["METRICS_NAMESPACE"] = (
                env_config.resource_prefix
            )

        # --- SnapStart: Force new version on each deployment ---
        if config.snap_start:
            lambda_environment_variables["DEPLOYMENT_TIMESTAMP"] = (
                datetime.datetime.utcnow().isoformat()
            )
        # --- End SnapStart versioning ---

        common_lambda_props["environment"] = lambda_environment_variables

        # Add VPC if provided
        if config.vpc:
            logger.debug(f"Adding VPC configuration: {config.vpc}")
            common_lambda_props["vpc"] = config.vpc

        # Add Security Groups if provided
        if config.security_groups:
            logger.debug(f"Adding security groups: {config.security_groups}")
            if not config.vpc:
                logger.error("Security groups provided without VPC configuration")
                raise ValueError(
                    "Security groups can only be added when a VPC is configured"
                )
            common_lambda_props["security_groups"] = config.security_groups

        # Add filesystem if provided
        if config.filesystem_access_point and config.filesystem_mount_path:
            logger.debug(
                f"Adding filesystem with access point and mount path {config.filesystem_mount_path}"
            )
            common_lambda_props["filesystem"] = (
                lambda_.FileSystem.from_efs_access_point(
                    config.filesystem_access_point, config.filesystem_mount_path
                )
            )

        # Add SnapStart if enabled
        if config.snap_start:
            logger.debug("SnapStart enabled for Lambda function")
            # SnapStart is supported for Java 11+, Python 3.12+, and .NET 8+ runtimes
            # SnapStart requires SnapStartConf object, not a simple boolean
            common_lambda_props["snap_start"] = (
                lambda_.SnapStartConf.ON_PUBLISHED_VERSIONS
            )
            logger.info(
                f"SnapStart enabled for {config.runtime.family} function - using ON_PUBLISHED_VERSIONS"
            )

            # Validate runtime support for SnapStart
            supported_families = [
                lambda_.RuntimeFamily.JAVA,
                lambda_.RuntimeFamily.DOTNET_CORE,
                lambda_.RuntimeFamily.PYTHON,
            ]
            if config.runtime.family not in supported_families:
                logger.warning(
                    f"SnapStart requested for runtime {config.runtime.family}. SnapStart is currently supported for Java 11+, Python 3.12+, and .NET 8+ runtimes."
                )
            elif config.runtime.family == lambda_.RuntimeFamily.PYTHON:
                # Additional validation for Python - must be 3.12 or later
                python_version = config.runtime.name
                if "python3.12" not in python_version.lower() and not any(
                    ver in python_version.lower()
                    for ver in ["python3.13", "python3.14", "python3.15"]
                ):
                    logger.warning(
                        f"SnapStart requires Python 3.12 or later. Current runtime: {config.runtime.name}"
                    )
                else:
                    logger.info(f"SnapStart is supported for {config.runtime.name}")

        # Create the Lambda function based on runtime
        logger.info(f"Creating {config.runtime.family} Lambda function with properties")
        entry_path = Path(common_lambda_props["entry"])
        logger.debug(f"Lambda entry path: {entry_path}")

        try:
            if config.runtime.family == lambda_.RuntimeFamily.NODEJS:
                # the Node.js bundling process is different
                self._create_nodejs_function(common_lambda_props)
            else:
                # Python bundling now handles common libraries via Docker - no local copying needed
                logger.debug(
                    "Using enhanced Docker bundling for Python - common libraries handled automatically"
                )
                self._create_python_function(
                    common_lambda_props, config, entry_path, {}
                )

            # --- SnapStart: Ensure versioning if enabled ---
            if config.snap_start:
                self._function_version = self._function.current_version
            else:
                self._function_version = None
            # --- End SnapStart versioning ---

        except Exception as e:
            logger.error(f"Failed to create Lambda function: {str(e)}", exc_info=True)
            raise

    def _create_nodejs_function(self, props: dict):
        logger = Logger()

        # Corrected Node.js specific paths
        props["runtime"] = lambda_.Runtime.NODEJS_20_X
        props["project_root"] = props["entry"]
        props["deps_lock_file_path"] = os.path.join(props["entry"], "lock.json")

        # If the deployment is part of a CI/CD pipeline, avoid using PythonFunction as it's relying on DnD
        # CI env var is exposed by Gitlab. TODO: add Github specific env var
        if "CI" in os.environ:

            # Replace the entry path to point to the dist folder
            dist_path = os.path.join(DIST_PATH, props["entry"])
            del props["entry"]
            del props["project_root"]
            del props["deps_lock_file_path"]

            # Add a default index document if not defined
            if "." not in props["handler"]:
                props["handler"] = f"index.{props['handler']}"

            self._function = lambda_.Function(
                self,
                "StandardNodeJSLambda",
                code=lambda_.Code.from_asset(dist_path),
                **props,
            )
        else:
            props["entry"] = os.path.join(props["entry"], "index.js")

            self._function = NodejsFunction(
                self,
                "StandardNodeJSLambda",
                bundling=NodeJSBundlingOptions(
                    node_modules=["exifr", "aws-sdk", "xml2js"],
                    force_docker_bundling=True,
                ),
                **props,
            )

        logger.info(f"Created Node.js Lambda: {self.function_name}")

    def _create_python_function(
        self, props: dict, config: LambdaConfig, entry_path: Path, common_libs: dict
    ):
        """Handle Python specific function creation with enhanced bundling"""
        logger = Logger()

        # Enhanced bundling options that copy common libraries during Docker build
        bundling_options = BundlingOptions(
            command=[
                "bash",
                "-c",
                """
                set -e
                echo "Starting Lambda bundling process..."

                # Install requirements if they exist
                if [ -f requirements.txt ]; then
                    echo "Installing Python requirements..."
                    pip install --no-cache-dir -r requirements.txt -t /asset-output
                fi

                # Copy lambda source files
                echo "Copying Lambda source files..."
                cp -au . /asset-output

                echo "Bundling process completed successfully"
                """,
            ],
            working_directory="/asset-input",
        )

        # Use custom bundling if provided, otherwise use enhanced bundling
        if config.python_bundling:
            logger.debug("Using custom Python bundling options from config")
            bundling_options = config.python_bundling

        # No need to copy common libraries locally since Docker bundling handles it
        logger.debug(
            "Skipping local common libraries copying - handled by Docker bundling"
        )

        # If the deployment is part of a CI/CD pipeline, avoid using PythonFunction as it's relying on DnD
        # CI env var is exposed by Gitlab. TODO: add Github specific env var
        if "CI" in os.environ:

            # Replace the entry path to point to the dist folder
            dist_path = os.path.join(DIST_PATH, props["entry"])
            del props["entry"]

            # Add a default index document if not defined
            if "." not in props["handler"]:
                props["handler"] = f"index.{props['handler']}"

            self._function = lambda_.Function(
                self,
                "StandardPythonLambda",
                code=lambda_.Code.from_asset(dist_path),
                **props,
            )
        else:
            self._function = PythonFunction(
                self,
                "StandardPythonLambda",
                bundling=bundling_options,
                **props,
            )
        logger.info(f"Created Python Lambda: {config.name}")

    def _generate_source_hash(self, entry_path: Path, common_libs: dict) -> str:
        """Generate MD5 hash of all source files in the entry directory"""
        import hashlib

        hash_md5 = hashlib.md5()

        # Hash application code
        for file_path in entry_path.glob("**/*"):
            if file_path.is_file():
                with open(file_path, "rb") as f:
                    while chunk := f.read(4096):
                        hash_md5.update(chunk)

        # Hash common libraries
        for lib_path in common_libs.values():
            with open(lib_path, "rb") as f:
                while chunk := f.read(4096):
                    hash_md5.update(chunk)

        return hash_md5.hexdigest()

    @property
    def function(self) -> lambda_.Function:
        """
        Get the underlying Lambda function.

        Returns:
            lambda_.Function: The created Lambda function instance
        """
        return self._function

    def add_environment_variables(self, new_variables: Dict[str, str]) -> None:
        """
        Add or update environment variables for the Lambda function while preserving existing ones.

        Args:
            new_variables (
                               Dict[str,
                               str]
                           ): Dictionary of new environment variables to add/update

        Example:
            lambda_construct.add_environment_variables({
                "NEW_KEY": "new_value",
                "ANOTHER_KEY": "another_value"
            })
        """
        logger = Logger()
        logger.debug(f"Adding/updating environment variables: {new_variables}")

        # Add environment variables one by one using the add_environment method
        # This works for both PythonFunction and regular Function classes
        for key, value in new_variables.items():
            self._function.add_environment(key, value)

        logger.info(
            f"Successfully updated environment variables for function: {self.function_name}"
        )

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

    @property
    def iam_role(self) -> iam.Role:
        """
        Get the IAM role associated with the Lambda function.

        Returns:
            iam.Role: The IAM role attached to the Lambda function
        """
        return self._lambda_role

    @property
    def function_version(self) -> Optional[lambda_.Version]:
        """
        Get the versioned Lambda function (if SnapStart is enabled).

        Returns:
            lambda_.Version | None: The versioned Lambda function, or None if not versioned
        """
        return getattr(self, "_function_version", None)
