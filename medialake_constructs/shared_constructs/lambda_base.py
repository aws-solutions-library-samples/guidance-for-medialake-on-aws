"""
Lambda base construct module that provides standardized Lambda function creation with common configurations.

This module contains utilities and classes for creating AWS Lambda functions with consistent
configuration, logging, IAM roles, and other AWS resources. It implements best practices for
Lambda deployment including standardized naming conventions and resource validation.
"""

from typing import Dict, Optional, List, Set
from dataclasses import dataclass
import re
import os
import glob
from pathlib import Path

from aws_cdk import (
    aws_lambda as lambda_,
    aws_logs as logs,
    aws_iam as iam,
    aws_ec2 as ec2,
    AssetHashType,
    Stack,
    RemovalPolicy,
    Duration,
)
from aws_cdk.aws_lambda_python_alpha import (
    PythonFunction,
    PythonLayerVersion,
    BundlingOptions,
)
from aws_cdk.aws_lambda_nodejs import (
    NodejsFunction,
    BundlingOptions as NodeJSBundlingOptions,
)

from constructs import Construct
from medialake_constructs.shared_constructs.lambda_layers import (
    PowertoolsLayer,
    PowertoolsLayerConfig,
    PynamoDbLambdaLayer,
)
from aws_lambda_powertools import Logger

from config import WORKFLOW_PAYLOAD_TEMP_BUCKET, config as env_config

# Constants
DEFAULT_MEMORY_SIZE = 128
DEFAULT_TIMEOUT_MINUTES = 5
DEFAULT_RUNTIME = lambda_.Runtime.PYTHON_3_12
DEFAULT_ARCHITECTURE = lambda_.Architecture.X86_64
LOG_RETENTION = logs.RetentionDays.SIX_MONTHS
MAX_LAMBDA_NAME_LENGTH = 64
MAX_ROLE_NAME_LENGTH = 64
MAX_LOG_GROUP_NAME_LENGTH = 512


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
        runtime (lambda_.Runtime): Lambda runtime (default: PYTHON_3_13)
        architecture (lambda_.Architecture): CPU architecture (default: X86_64)
        layers (Optional[List[PythonLayerVersion]]): Lambda layers to attach
        iam_role_name (Optional[str]): Custom IAM role name
        vpc (Optional[ec2.IVpc]): VPC configuration for the Lambda
        log_removal_policy (Optional[RemovalPolicy]): Removal policy for the CloudWatch log group (default: DESTROY)
        python_bundling (Optional[BundlingOptions]): Bundling options for Python functions
        nodejs_bundling (Optional[NodeJSBundlingOptions]): Bundling options for Node.js functions
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
            role_props["role_name"] = config.iam_role_name

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

        # Add environment variables if provided
        if config.environment_variables:
            logger.debug("Adding environment variables")
            lambda_environment_variables = config.environment_variables
            lambda_environment_variables["RESOURCE_PREFIX"] = env_config.resource_prefix
            lambda_environment_variables["ENVIRONMENT"] = env_config.environment
            lambda_environment_variables["METRICS_NAMESPACE"] = (
                env_config.resource_prefix
            )
            # lambda_environment_variables["external_payload_s3_bucket"] = (
            #     f"{WORKFLOW_PAYLOAD_TEMP_BUCKET}-{stack.region}"
            # )
            common_lambda_props["environment"] = lambda_environment_variables
        else:
            lambda_environment_variables = {}
            lambda_environment_variables["RESOURCE_PREFIX"] = env_config.resource_prefix
            lambda_environment_variables["ENVIRONMENT"] = env_config.environment
            lambda_environment_variables["METRICS_NAMESPACE"] = (
                env_config.resource_prefix
            )

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

        # Create the Lambda function based on runtime
        logger.debug(
            f"Creating {config.runtime.family} Lambda function with properties"
        )
        # Collect common libraries
        entry_path = Path(common_lambda_props["entry"])
        common_libs = self._collect_common_libraries(entry_path)
        logger.debug(f"Found common libraries: {common_libs}")

        try:
            if config.runtime.family == lambda_.RuntimeFamily.NODEJS:
                # Corrected Node.js specific paths
                common_lambda_props["runtime"] = lambda_.Runtime.NODEJS_20_X
                common_lambda_props["project_root"] = common_lambda_props["entry"]
                common_lambda_props["deps_lock_file_path"] = os.path.join(
                    common_lambda_props["entry"], "lock.json"
                )
                common_lambda_props["entry"] = os.path.join(
                    common_lambda_props["entry"], "index.js"
                )

                # Copy common libraries to entry directory
                if common_libs:
                    self._copy_common_libraries(
                        common_libs, Path(common_lambda_props["project_root"])
                    )

                self._function = NodejsFunction(
                    self,
                    "StandardNodeJSLambda",
                    bundling=NodeJSBundlingOptions(
                        node_modules=["exifr", "aws-sdk"],
                        force_docker_bundling=True,
                    ),
                    **common_lambda_props,
                )
                logger.info(f"Created Node.js Lambda: {self.function_name}")
            else:
                # Python specific bundling with hash-based asset tracking
                self._create_python_function(common_lambda_props, config, entry_path, common_libs)
            
        except Exception as e:
            logger.error(f"Failed to create Lambda function: {str(e)}", exc_info=True)
            raise

    def _collect_common_libraries(self, entry_path: Path) -> Dict[str, str]:
        """
        Collect common libraries from parent directories.
        Returns a dictionary mapping file names to their full paths,
        with more specific (closer to lambda) libraries taking precedence.
        """
        common_libs = {}
        current_path = entry_path

        # Walk up the directory tree until we reach the lambdas directory
        while "lambdas" in str(current_path):
            common_lib_path = current_path / "common_libraries"
            if common_lib_path.exists():
                # Collect all files in the common_libraries directory
                for file_path in common_lib_path.rglob("*"):
                    if file_path.is_file():
                        # Use the relative path from common_libraries as the key
                        rel_path = file_path.relative_to(common_lib_path)
                        # Only add if we haven't seen this file before (more specific ones take precedence)
                        if str(rel_path) not in common_libs:
                            common_libs[str(rel_path)] = str(file_path)
            current_path = current_path.parent

        return common_libs

    def _copy_common_libraries(
        self, common_libs: Dict[str, str], target_dir: Path
    ) -> None:
        """
        Copy common libraries to the target directory, flattening the structure.
        """
        import shutil

        # Create the  directory if it doesn't exist
        target_dir.mkdir(parents=True, exist_ok=True)

        # Copy each file
        for rel_path, source_path in common_libs.items():
            target_path = target_dir / Path(rel_path).name
            shutil.copy2(source_path, target_path)

    def _create_nodejs_function(self, props: dict, config: LambdaConfig, common_libs: dict):
        """Handle Node.js specific function creation"""
        logger = Logger()
        
        # Set up Node.js specific paths
        props["project_root"] = props["entry"]
        props["deps_lock_file_path"] = str(Path(props["entry"]) / "lock.json")
        props["entry"] = str(Path(props["entry"]) / "index.js")

        # Merge user-provided bundling options with defaults
        bundling_options = config.nodejs_bundling or NodeJSBundlingOptions(
            node_modules=["exifr", "aws-sdk"],
            force_docker_bundling=True
        )
        
        # Handle common libraries
        if common_libs:
            self._copy_common_libraries(common_libs, Path(props['project_root']))

        self._function = NodejsFunction(
            self,
            "StandardNodeJSLambda",
            bundling=bundling_options,
            **props,
        )
        logger.info(f"Created Node.js Lambda: {self.function_name}")

    def _create_python_function(self, props: dict, config: LambdaConfig, entry_path: Path, common_libs: dict):
        """Handle Python specific function creation with asset hashing"""
        logger = Logger()
        
        # Generate hash of source files for deterministic builds
        source_hash = self._generate_source_hash(entry_path, common_libs)
        
        # Merge user-provided bundling options with hash
        bundling_options = config.python_bundling or BundlingOptions(
            # asset_hash=source_hash,
            asset_hash_type=AssetHashType.SOURCE
        )

        # Copy common libraries
        if common_libs:
            self._copy_common_libraries(common_libs, entry_path)

        self._function = PythonFunction(
            self,
            "StandardPythonLambda",
            bundling=bundling_options,
            **props,
        )
        logger.info(f"Created Python Lambda: {self.function_name}")

    def _generate_source_hash(self, entry_path: Path, common_libs: dict) -> str:
        """Generate MD5 hash of all source files in the entry directory"""
        import hashlib
        hash_md5 = hashlib.md5()
        
        # Hash application code
        for file_path in entry_path.glob('**/*'):
            if file_path.is_file():
                with open(file_path, 'rb') as f:
                    while chunk := f.read(4096):
                        hash_md5.update(chunk)
        
        # Hash common libraries
        for lib_path in common_libs.values():
            with open(lib_path, 'rb') as f:
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
            new_variables (Dict[str, str]): Dictionary of new environment variables to add/update

        Example:
            lambda_construct.add_environment_variables({
                "NEW_KEY": "new_value",
                "ANOTHER_KEY": "another_value"
            })
        """
        logger = Logger()
        logger.debug(f"Adding/updating environment variables: {new_variables}")

        # Get current environment variables
        current_env = dict(self._function.get_environment() or {})

        # Merge new variables with existing ones
        updated_env = {**current_env, **new_variables}

        # Update the function's environment
        self._function.add_environment_variables(updated_env)

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
