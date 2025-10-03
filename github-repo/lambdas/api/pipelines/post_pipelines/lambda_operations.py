import os
import re
import time
import traceback
from typing import Any, Dict, List, Optional

import boto3
import shortuuid
import yaml
from aws_lambda_powertools import Logger
from dynamodb_operations import (
    get_integration_secret_arn,
    get_node_auth_config,
    get_node_info,
)
from iam_operations import (
    create_lambda_role,
    wait_for_role_propagation,
)

from config import (
    IAC_ASSETS_BUCKET,
    MEDIALAKE_ASSET_TABLE,
    NODE_TEMPLATES_BUCKET,
    OPENSEARCH_SECURITY_GROUP_ID,
    OPENSEARCH_VPC_SUBNET_IDS,
    PIPELINES_EVENT_BUS_NAME,
)

# Initialize logger
logger = Logger()

resource_prefix = os.environ["RESOURCE_PREFIX"]


def sanitize_function_name(pipeline_name, node_label, version):
    """
    Create a sanitized Lambda function name from pipeline name, node label, and version.

    Args:
        pipeline_name: Name of the pipeline
        node_label: Label of the node
        version: Version string

    Returns:
        A sanitized function name suitable for AWS Lambda
    """
    # Combine the components
    parts = re.split(r"[^A-Za-z0-9]+", pipeline_name)

    # Take the first character of each non-empty part, uppercase it, join
    abvr = "".join(p[0].upper() for p in parts if p)
    uuid = shortuuid.uuid()

    raw_name = f"{resource_prefix}_{abvr}_{node_label}_{version}_{uuid}".lower()

    # Replace spaces with hyphens
    raw_name = raw_name.replace(" ", "-")

    # Replace non-alphanumeric characters (except hyphens) with underscores
    sanitized_name = re.sub(r"[^a-z0-9-]", "_", raw_name)

    # Ensure the name starts with a letter or number
    sanitized_name = re.sub(r"^[^a-z0-9]+", "", sanitized_name)

    # Truncate to 64 characters (maximum length for Lambda function names)
    sanitized_name = sanitized_name[:64]

    # Ensure the name doesn't end with a hyphen or underscore
    sanitized_name = re.sub(r"[-_]+$", "", sanitized_name)

    return sanitized_name


def get_lambda_config_with_defaults(lambda_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract Lambda configuration parameters from YAML with fallback defaults.

    Args:
        lambda_config: Lambda configuration from YAML

    Returns:
        Dictionary with Lambda configuration parameters including:
        - memory_size: Memory allocation in MB (default: 1024)
        - ephemeral_storage_size: Ephemeral storage size in MB (default: 10240)
        - timeout: Function timeout in seconds (default: 300)
    """
    # Extract parameters with defaults matching current hardcoded values
    memory_size = lambda_config.get("memory_size", 1024)
    ephemeral_storage = lambda_config.get("ephemeral_storage", 10240)
    timeout = lambda_config.get("timeout", 300)

    # Validate parameters within AWS Lambda limits
    memory_size = max(128, min(10240, int(memory_size)))
    ephemeral_storage = max(512, min(10240, int(ephemeral_storage)))
    timeout = max(1, min(900, int(timeout)))

    logger.info(
        f"Lambda configuration: memory_size={memory_size}MB, "
        f"ephemeral_storage={ephemeral_storage}MB, timeout={timeout}s"
    )

    return {
        "memory_size": memory_size,
        "ephemeral_storage_size": ephemeral_storage,
        "timeout": timeout,
    }


def read_yaml_from_s3(bucket: str, key: str) -> Dict[str, Any]:
    """
    Read and parse a YAML file from S3.

    Args:
        bucket: S3 bucket name
        key: S3 object key

    Returns:
        Parsed YAML content as dictionary
    """
    logger.info(f"Reading YAML file from S3: {bucket}/{key}")
    s3 = boto3.client("s3")
    try:
        response = s3.get_object(Bucket=bucket, Key=key)
        yaml_content = response["Body"].read().decode("utf-8")
        return yaml.safe_load(yaml_content)
    except Exception as e:
        logger.exception(f"Failed to read YAML file {bucket}/{key} from S3: {e}")
        raise


def get_zip_file_key(bucket: str, prefix: str) -> str:
    """
    Find a zip file in an S3 bucket with the given prefix.

    Args:
        bucket: S3 bucket name
        prefix: Prefix to search for

    Returns:
        S3 key of the first zip file found
    """
    s3 = boto3.client("s3")
    response = s3.list_objects_v2(Bucket=bucket, Prefix=prefix)

    for obj in response.get("Contents", []):
        if obj["Key"].endswith(".zip"):
            return obj["Key"]

    raise ValueError(f"No zip file found in {bucket}/{prefix}")


def wait_for_lambda_deletion(function_name: str, max_attempts: int = 40) -> None:
    """
    Wait for a Lambda function to be fully deleted.

    Args:
        function_name: Name of the Lambda function
        max_attempts: Maximum number of attempts to check
    """
    lambda_client = boto3.client("lambda")
    attempt = 0

    while attempt < max_attempts:
        try:
            lambda_client.get_function(FunctionName=function_name)
            attempt += 1
            logger.info(
                f"Lambda function {function_name} is still being deleted, waiting... (attempt {attempt}/{max_attempts})"
            )
            time.sleep(5)  # Wait 5 seconds between checks
        except lambda_client.exceptions.ResourceNotFoundException:
            logger.info(f"Lambda function {function_name} has been deleted")
            return
        except Exception as e:
            logger.error(f"Error checking Lambda function status: {e}")
            attempt += 1
            time.sleep(5)

    raise TimeoutError(
        f"Lambda function {function_name} deletion timed out after {max_attempts} attempts"
    )


def check_lambda_exists(function_name: str) -> bool:
    """
    Check if a Lambda function exists.

    Args:
        function_name: Name of the Lambda function

    Returns:
        True if the function exists, False otherwise
    """
    lambda_client = boto3.client("lambda")
    try:
        lambda_client.get_function(FunctionName=function_name)
        return True
    except lambda_client.exceptions.ResourceNotFoundException:
        return False


def get_auth_type_for_node(node_id: str) -> str:
    """
    Get the auth type for a node from DynamoDB.

    Args:
        node_id: ID of the node

    Returns:
        Auth type string in the format "type:in:name" (e.g., "apiKey:header:x-api-key")
    """
    logger.info(f"Getting auth type for node: {node_id}")
    auth_config = get_node_auth_config(node_id)
    # Default empty auth type
    api_auth_type = ""

    if auth_config and "authConfig" in auth_config:
        auth_config_map = auth_config.get("authConfig", {})
        if auth_config_map:
            # Get the auth type, in, and name
            auth_type = auth_config_map.get("type", {})

            api_auth_type = f"{auth_type}"
            logger.info(f"Constructed auth type for node {node_id}: {api_auth_type}")

    return api_auth_type


def delete_lambda_function(function_name: str) -> None:
    """
    Delete a Lambda function if it exists.

    Args:
        function_name: Name of the Lambda function
    """
    lambda_client = boto3.client("lambda")
    try:
        lambda_client.delete_function(FunctionName=function_name)
        logger.info(f"Deleted existing Lambda function: {function_name}")
    except lambda_client.exceptions.ResourceNotFoundException:
        logger.debug(f"Lambda function {function_name} does not exist")


def create_service_roles_from_yaml(
    pipeline_name: str, node_id: str, yaml_data: Dict[str, Any]
) -> Dict[str, str]:
    """
    Create service roles defined in the YAML configuration.

    Args:
        pipeline_name: Name of the pipeline
        node_id: ID of the node
        yaml_data: YAML configuration data

    Returns:
        Dictionary mapping role names to role ARNs
    """
    from iam_operations import create_service_role

    service_roles = {}

    # Check if service_roles is defined in the YAML
    service_roles_config = (
        yaml_data.get("node", {})
        .get("integration", {})
        .get("config", {})
        .get("service_roles", [])
    ) or (
        yaml_data.get("node", {})
        .get("utility", {})
        .get("config", {})
        .get("service_roles", [])
    )

    if not service_roles_config:
        logger.info(f"No service roles defined in YAML for node {node_id}")
        return service_roles

    logger.info(
        f"Found {len(service_roles_config)} service roles defined in YAML for node {node_id}"
    )

    # Create each service role
    for role_config in service_roles_config:
        role_name = role_config.get("name", "default_service_role")
        service_principal = role_config.get("service")

        if not service_principal:
            logger.warning(
                f"Service principal not specified for role {role_name}, skipping"
            )
            continue

        # Extract policy statements
        policy_statements = []
        for policy in role_config.get("policies", []):
            policy_statements.extend(policy.get("statements", []))

        if not policy_statements:
            logger.warning(
                f"No policy statements found for role {role_name}, creating role with no permissions"
            )

        # Create the service role
        try:
            role_arn = create_service_role(
                pipeline_name=pipeline_name,
                node_id=node_id,
                service_principal=service_principal,
                policy_statements=policy_statements,
                role_name_suffix=role_name,
            )

            service_roles[role_name] = role_arn
            logger.info(f"Created service role {role_name} with ARN: {role_arn}")
        except Exception as e:
            logger.error(f"Failed to create service role {role_name}: {e}")

    return service_roles


def determine_layers_for_node(
    node_id: str, node_type: str, yaml_data: Dict[str, Any]
) -> List[str]:
    """
    Determine which layers to attach to a Lambda function based on its YAML configuration.

    Args:
        node_id: ID of the node
        node_type: Type of the node (e.g., "utility", "integration")
        yaml_data: YAML configuration data

    Returns:
        List of layer ARNs to attach
    """
    layers = []

    # Then, try to get layers from DynamoDB
    try:
        # Get the layers item from DynamoDB
        dynamodb = boto3.resource("dynamodb")
        table = dynamodb.Table(os.environ["NODE_TABLE"])
        response = table.get_item(Key={"pk": f"NODE#{node_id}", "sk": "LAYERS"})

        if "Item" in response and "layers" in response["Item"]:
            # Add each layer ARN to the list
            for layer_name, layer_arn in response["Item"]["layers"].items():
                layers.append(layer_arn)
                logger.info(
                    f"Adding layer {layer_name} (ARN: {layer_arn}) from DynamoDB to Lambda function for node {node_id}"
                )
    except Exception as e:
        logger.warning(f"Error retrieving layers from DynamoDB for node {node_id}: {e}")

    # Always add the Powertools layer for all Lambda functions if not already specified
    if not any("POWERTOOLS_LAYER_ARN" in layer for layer in layers):
        powertools_layer_arn = os.environ.get("POWERTOOLS_LAYER_ARN")
        if powertools_layer_arn:
            layers.append(powertools_layer_arn)
            logger.info(
                f"Adding default Powertools layer to Lambda function for node {node_id}"
            )

    # Always add the Common Libraries layer for all Lambda functions if not already specified
    if not any("COMMON_LIBRARIES_LAYER_ARN" in layer for layer in layers):
        common_libraries_layer_arn = os.environ.get("COMMON_LIBRARIES_LAYER_ARN")
        if common_libraries_layer_arn:
            layers.append(common_libraries_layer_arn)
            logger.info(
                f"Adding default Common Libraries layer to Lambda function for node {node_id}"
            )

    return layers


def _determine_connection_input_type(
    pipeline: Any, target_node_id: str
) -> Optional[str]:
    """
    Determine the input type for any node based on its incoming connections.

    Args:
        pipeline: Pipeline object containing edges and nodes
        target_node_id: ID of the target node to analyze

    Returns:
        The connection input type ('video', 'image', 'text', 'audio', etc.) or None if not determinable
    """
    if (
        not pipeline
        or not hasattr(pipeline, "configuration")
        or not hasattr(pipeline.configuration, "edges")
    ):
        return None

    # Find incoming edges to this node
    for edge in pipeline.configuration.edges:
        edge_target = edge.target if hasattr(edge, "target") else edge.get("target")
        if edge_target == target_node_id:
            # Extract input type from target handle (e.g., "input-video" -> "video")
            target_handle = (
                edge.targetHandle
                if hasattr(edge, "targetHandle")
                else edge.get("targetHandle")
            )
            if target_handle and target_handle.startswith("input-"):
                input_type = target_handle.replace("input-", "")
                logger.info(
                    f"Determined connection input type for {target_node_id}: {input_type}"
                )
                return input_type

            # Extract input type from source handle if it's a specific type
            source_handle = (
                edge.sourceHandle
                if hasattr(edge, "sourceHandle")
                else edge.get("sourceHandle")
            )
            if source_handle and source_handle not in [
                "Next",
                "Processor",
                "Completed",
                "In Progress",
                "Fail",
            ]:
                logger.info(
                    f"Determined connection input type for {target_node_id} from source handle: {source_handle}"
                )
                return source_handle

            # If we found an edge but couldn't determine type, break to avoid checking other edges
            break

    return None


def create_lambda_function(
    pipeline_name: str,
    node: Any,
    pipeline: Any = None,
    is_first: bool = False,
    is_last: bool = False,
) -> Optional[Dict[str, Any]]:
    """
    Create or update a Lambda function for a node.

    Args:
        pipeline_name: Name of the pipeline
        node: Node object containing configuration
        pipeline: Pipeline object containing edges and nodes for connection analysis
        is_first: Whether this is the first lambda in the pipeline
        is_last: Whether this is the last lambda in the pipeline

    Returns:
        Dictionary containing:
        - function_arn: ARN of the created Lambda function
        - role_arn: ARN of the IAM role created for the Lambda function
        - service_roles: Dictionary mapping service role names to ARNs (if any)
        Or None if creation was skipped
    """
    # Skip Lambda creation for flow-type and trigger-type nodes
    if node.data.type.lower() == "flow" or node.data.type.lower() == "trigger":
        logger.info(
            f"Skipping Lambda creation for {node.data.type.lower()}-type node: {node.id}"
        )
        return None

    logger.info(f"Creating/updating Lambda function for node: {node.id}")
    lambda_client = boto3.client("lambda")

    # For integration nodes, include the method in the function name to differentiate
    # between different operations (GET, POST, etc.) on the same integration
    method_suffix = ""
    if node.data.type.lower() == "integration" and "method" in node.data.configuration:
        method_suffix = f"_{node.data.configuration['method']}"

    # Extract operation_id from node configuration
    operation_id = node.data.configuration.get("operationId", "")
    version = node.data.configuration.get("version", "v1")

    # Create a base function name without the operation_id
    base_name = f"{node.data.label}{method_suffix}"

    # If we have an operation_id, we need to ensure we don't exceed the 64-character limit
    candidate = (
        f"{base_name}_{operation_id}"
        if operation_id and operation_id not in base_name
        else base_name
    )
    function_name = sanitize_function_name(pipeline_name, candidate, version)
    logger.debug(f"Lambda function name generated: {function_name}")

    # Read YAML file from S3
    yaml_file_path = f"node_templates/{node.data.type.lower()}/{node.data.id}.yaml"
    yaml_data = read_yaml_from_s3(NODE_TEMPLATES_BUCKET, yaml_file_path)
    logger.debug(yaml_data)

    # Create service roles defined in the YAML
    service_roles = create_service_roles_from_yaml(
        pipeline_name, node.data.id, yaml_data
    )
    if service_roles:
        logger.info(
            f"Created {len(service_roles)} service roles for node {node.data.id}"
        )

    # Get API service URL from OpenAPI spec if available
    api_service_url = os.environ.get("API_SERVICE_URL", "")
    api_path = os.environ.get("API_PATH", "")
    request_templates_path = node.data.configuration.get("requestMapping")
    response_templates_path = node.data.configuration.get("responseMapping")

    try:
        if (
            node.data.type.lower() == "integration"
            and "integration" in yaml_data.get("node", {})
            and "api" in yaml_data["node"]["integration"]
        ):
            node_info = get_node_info(node.data.id)
            production_server = next(
                (
                    server
                    for server in node_info["servers"]
                    if server.get("x-server-environment") == "Production"
                ),
                None,
            )
            if production_server:
                api_service_url = production_server.get("url")
                api_path = production_server.get("path", "")
            else:
                raise ValueError(f"No Production server found for node {node.data.id}")

            if api_service_url is None:
                raise ValueError(
                    f"No Production server URL found for node {node.data.id}"
                )

            logger.info(f"Using API service URL: {api_service_url}")
            logger.info(f"Using API path: {api_path}")

    except Exception as e:
        logger.warning(
            f"Failed to extract API service URL and path from node info: {e}"
        )

    # Get Lambda configuration from YAML
    lambda_config = yaml_data["node"]["integration"]["config"]["lambda"]
    zip_file_prefix = f"lambda-code/nodes/{lambda_config['handler']}"

    # Get the actual zip file key
    zip_file_key = get_zip_file_key(IAC_ASSETS_BUCKET, zip_file_prefix)

    runtime = lambda_config["runtime"].lower()

    # Extract configurable Lambda parameters with defaults
    config_params = get_lambda_config_with_defaults(lambda_config)

    role_arn = create_lambda_role(
        pipeline_name, node.data.id, yaml_data, operation_id, function_name
    )

    # Wait for the role to propagate before attempting to create the Lambda function
    try:
        # Use the function name as the role name (same as in create_lambda_role)
        role_name = function_name

        wait_for_role_propagation(role_name)
    except Exception as e:
        logger.warning(
            f"Error waiting for role propagation: {e}, will proceed with Lambda creation anyway"
        )

    max_retries = 5  # Increased from 3 to 5
    retry_delay = 5  # Increased from 2 to 5 seconds

    try:
        # If function exists, delete it and wait for deletion to complete
        if check_lambda_exists(function_name):
            logger.info(f"Deleting existing Lambda function: {function_name}")
            delete_lambda_function(function_name)
            wait_for_lambda_deletion(function_name)

        logger.info(f"Creating new Lambda function: {function_name}")
        for attempt in range(max_retries):
            try:

                # Build common parameters for the Lambda function creation
                create_function_params = {
                    "FunctionName": function_name,
                    "Runtime": runtime,
                    "MemorySize": config_params["memory_size"],
                    "EphemeralStorage": {
                        "Size": config_params["ephemeral_storage_size"]
                    },
                    "Timeout": config_params["timeout"],
                    "Role": role_arn,
                    "Handler": "index.lambda_handler",
                    "Code": {"S3Bucket": IAC_ASSETS_BUCKET, "S3Key": zip_file_key},
                    "Publish": True,
                }

                # Determine which layers to attach
                layers = determine_layers_for_node(
                    node.data.id, node.data.type.lower(), yaml_data
                )
                if layers:
                    create_function_params["Layers"] = layers
                    logger.info(
                        f"Attaching layers to Lambda function {function_name}: {layers}"
                    )

                # Determine connection input type for this node
                connection_input_type = _determine_connection_input_type(
                    pipeline, node.id
                )

                # Common environment variables for all Lambda functions
                common_env_vars = {
                    "EXTERNAL_PAYLOAD_BUCKET": os.environ.get(
                        "EXTERNAL_PAYLOAD_BUCKET"
                    ),
                    "EVENT_BUS_NAME": PIPELINES_EVENT_BUS_NAME or "default-event-bus",
                    "MEDIA_ASSETS_BUCKET_NAME": os.environ.get(
                        "MEDIA_ASSETS_BUCKET_NAME", ""
                    ),
                    "MEDIALAKE_ASSET_TABLE": MEDIALAKE_ASSET_TABLE,
                    "API_TEMPLATE_BUCKET": os.environ.get("NODE_TEMPLATES_BUCKET"),
                    "OPENSEARCH_ENDPOINT": os.environ.get("OPENSEARCH_ENDPOINT"),
                    # Add required environment variables
                    "SERVICE": node.data.id,  # node Title
                    "STEP_NAME": node.data.label,  # friendly name of the node
                    "PIPELINE_NAME": pipeline_name,  # name of the pipeline
                }

                # Add connection input type if determined
                if connection_input_type:
                    common_env_vars["CONNECTION_INPUT_TYPE"] = connection_input_type
                    logger.info(
                        f"Added CONNECTION_INPUT_TYPE={connection_input_type} to Lambda {function_name}"
                    )

                # Add IS_FIRST and IS_LAST if applicable
                if is_first:
                    common_env_vars["IS_FIRST"] = "true"
                    logger.info(
                        f"Marking lambda {function_name} as first lambda in pipeline"
                    )

                if is_last:
                    common_env_vars["IS_LAST"] = "true"
                    logger.info(
                        f"Marking lambda {function_name} as last lambda in pipeline"
                    )

                # Add node configuration parameters to common environment variables
                if (
                    hasattr(node.data, "configuration")
                    and "parameters" in node.data.configuration
                ):
                    # Loop through all parameters and add them to common_env_vars
                    for param_key, param_value in node.data.configuration[
                        "parameters"
                    ].items():
                        # Skip numeric keys as they are just parameter definitions
                        if param_key.isdigit():
                            continue

                        # Create sanitized environment variable name (replace spaces with underscores)
                        env_var_name = param_key.replace(" ", "_").upper()

                        # Get the parameter value or default if not available
                        if param_value:
                            env_var_value = str(param_value)

                            # Check if the value is in the format ${VARIABLE_NAME}
                            # Check for standard environment variables
                            var_match = re.match(
                                r"^\${([A-Za-z0-9_]+)}$", env_var_value
                            )
                            # Check for CloudFormation parameters (AWS::Region, AWS::AccountId)
                            cf_match = re.match(
                                r"^\${(AWS::Region|AWS::AccountId)}$", env_var_value
                            )

                            if cf_match:
                                # Handle CloudFormation parameters
                                cf_param = cf_match.group(1)
                                if cf_param == "AWS::Region":
                                    resolved_value = boto3.session.Session().region_name
                                elif cf_param == "AWS::AccountId":
                                    sts_client = boto3.client("sts")
                                    resolved_value = sts_client.get_caller_identity()[
                                        "Account"
                                    ]
                                common_env_vars[env_var_name] = resolved_value
                                logger.info(
                                    f"Added CloudFormation parameter {env_var_name}={resolved_value} to Lambda environment variables"
                                )
                            elif var_match:
                                # Handle environment variable references
                                env_var_ref = var_match.group(1)
                                resolved_value = os.environ.get(env_var_ref, "")
                                common_env_vars[env_var_name] = resolved_value
                                logger.info(
                                    f"Added environment variable reference {env_var_name}={resolved_value} to Lambda environment variables"
                                )
                            else:
                                # Regular parameter value
                                common_env_vars[env_var_name] = env_var_value
                                logger.info(
                                    f"Added parameter {env_var_name}={env_var_value} to Lambda environment variables"
                                )

                # Only include additional Environment variables if the node type is "integration"
                if node.data.type.lower() == "integration":
                    env_vars = {
                        **common_env_vars,  # Include common env vars (now with node parameters)
                        "WORKFLOW_STEP_NAME": function_name,
                        "IS_LAST_STEP": os.environ.get("IS_LAST_STEP", "false"),
                        "REQUEST_TEMPLATES_PATH": request_templates_path or "",
                        "RESPONSE_TEMPLATES_PATH": response_templates_path or "",
                        "API_SERVICE_URL": api_service_url,
                        "API_SERVICE_RESOURCE": (
                            node.data.configuration.get("path", "")
                            if node.data.type.lower() == "integration"
                            else os.environ.get("API_SERVICE_RESOURCE", "")
                        ),
                        "API_SERVICE_PATH": api_path,
                        "API_SERVICE_METHOD": (
                            node.data.configuration.get("method", "")
                            if node.data.type.lower() == "integration"
                            else os.environ.get("API_SERVICE_METHOD", "")
                        ),
                        "API_AUTH_TYPE": (
                            get_auth_type_for_node(node.data.id)
                            if node.data.type.lower() == "integration"
                            else os.environ.get("API_AUTH_TYPE", "")
                        ),
                        "API_SERVICE_NAME": node.data.id,
                        "API_CUSTOM_URL": os.environ.get("API_CUSTOM_URL", "false"),
                        "API_CUSTOM_CODE": os.environ.get("API_CUSTOM_CODE", "false"),
                        **(
                            {
                                "API_KEY_SECRET_ARN": get_integration_secret_arn(
                                    node.data.configuration.get("integrationId", "")
                                )
                                or ""
                            }
                            if node.data.type.lower() == "integration"
                            and node.data.configuration.get("integrationId")
                            else {}
                        ),
                        "EXTERNAL_PAYLOAD_BUCKET": os.environ.get(
                            "EXTERNAL_PAYLOAD_BUCKET"
                        ),
                        "CUSTOM_HEADERS": os.environ.get("CUSTOM_HEADERS", "{}"),
                    }
                    create_function_params["Environment"] = {"Variables": env_vars}

                # For all other node types, just add the common environment variables
                elif (
                    node.data.type.lower() != "integration"
                ):  # Integration nodes already handled above
                    env_vars = common_env_vars.copy()

                    # Add service role ARNs to environment variables if available
                    if service_roles:
                        for role_name, role_arn in service_roles.items():
                            # Create a standardized environment variable name for the service role
                            # Convert to uppercase and replace spaces with underscores
                            env_var_name = (
                                f"{role_name.upper().replace(' ', '_')}_ROLE_ARN"
                            )
                            env_vars[env_var_name] = role_arn
                            logger.info(
                                f"Added {env_var_name} to Lambda environment variables: {role_arn}"
                            )

                    create_function_params["Environment"] = {"Variables": env_vars}
                    logger.info(
                        f"Added environment variables to {node.data.type} Lambda function: {function_name}"
                    )

                # Check if VPC configuration is needed based on YAML config
                vpc_config = None
                try:
                    # Check for VPC configuration in the YAML
                    lambda_config = (
                        yaml_data.get("node", {})
                        .get("integration", {})
                        .get("config", {})
                        .get("lambda", {})
                    )
                    if not lambda_config:
                        # Also check utility nodes
                        lambda_config = (
                            yaml_data.get("node", {})
                            .get("utility", {})
                            .get("config", {})
                            .get("lambda", {})
                        )

                    if lambda_config and lambda_config.get("vpc", False):
                        subnet_ids = (
                            OPENSEARCH_VPC_SUBNET_IDS.split(",")
                            if OPENSEARCH_VPC_SUBNET_IDS
                            else []
                        )
                        if subnet_ids and OPENSEARCH_SECURITY_GROUP_ID:
                            vpc_config = {
                                "SubnetIds": subnet_ids,
                                "SecurityGroupIds": [OPENSEARCH_SECURITY_GROUP_ID],
                            }
                            logger.info(
                                f"Added VPC configuration to Lambda {function_name}: Subnets={subnet_ids}, SecurityGroup={OPENSEARCH_SECURITY_GROUP_ID}"
                            )
                        else:
                            logger.warning(
                                f"VPC configuration requested for {function_name} but VPC subnet IDs or security group not available"
                            )
                except Exception as e:
                    logger.warning(
                        f"Error checking VPC configuration for {function_name}: {e}"
                    )

                if vpc_config:
                    create_function_params["VpcConfig"] = vpc_config

                # Create the Lambda function with the appropriate parameters
                response = lambda_client.create_function(**create_function_params)

                function_arn = response["FunctionArn"]

                # Wait for function to be active
                waiter = lambda_client.get_waiter("function_active")
                waiter.wait(
                    FunctionName=function_name,
                    WaiterConfig={"Delay": 5, "MaxAttempts": 12},
                )

                logger.info(
                    f"Created Lambda function '{function_name}' with ARN: {function_arn}"
                )
                break
            except lambda_client.exceptions.InvalidParameterValueException as e:
                if "role" in str(e).lower() and attempt < max_retries - 1:
                    logger.warning(
                        f"Role not yet ready, retrying... (attempt {attempt + 1}/{max_retries})"
                    )
                    # More aggressive exponential backoff with longer initial delay
                    backoff_time = retry_delay * (2**attempt)
                    logger.info(f"Waiting {backoff_time} seconds before retry")
                    time.sleep(backoff_time)
                    continue
                raise
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(
                        f"Failed to create Lambda function after {max_retries} attempts: {str(e)}"
                    )
                    raise
                # Log the full traceback for debugging
                tb_str = traceback.format_exc()
                logger.warning(
                    f"Attempt {attempt + 1}/{max_retries} failed: {str(e)}\nTraceback:\n{tb_str}"
                )
                # More aggressive exponential backoff
                backoff_time = retry_delay * (2**attempt)
                logger.info(f"Waiting {backoff_time} seconds before retry")
                time.sleep(backoff_time)

        return {
            "function_arn": function_arn,
            "role_arn": role_arn,
            "service_roles": service_roles,
        }
    except Exception as e:
        # Use logger.exception which automatically includes the traceback
        logger.exception(
            f"Failed to create/update Lambda function {function_name}: {e}"
        )
        raise
