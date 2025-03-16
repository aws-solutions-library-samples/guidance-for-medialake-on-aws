import os
import re
import time
import yaml
import traceback
from typing import Dict, Any, Optional

import boto3
from aws_lambda_powertools import Logger

from config import IAC_ASSETS_BUCKET, NODE_TEMPLATES_BUCKET, INGEST_EVENT_BUS_NAME, OPENSEARCH_VPC_SUBNET_IDS, OPENSEARCH_SECURITY_GROUP_ID
from iam_operations import create_lambda_role, wait_for_role_propagation, sanitize_role_name
from dynamodb_operations import (
    get_node_info,
    get_node_method,
    get_node_auth_config,
    get_integration_secret_arn,
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
    raw_name = f"{resource_prefix}_{pipeline_name}_{node_label}_{version}".lower()

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


def create_lambda_function(pipeline_name: str, node: Any) -> Optional[str]:
    """
    Create or update a Lambda function for a node.

    Args:
        pipeline_name: Name of the pipeline
        node: Node object containing configuration

    Returns:
        ARN of the created Lambda function, or None if creation was skipped
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
    if operation_id:
        # We'll create the function name with the operation_id and let sanitize_function_name handle the truncation
        function_name = sanitize_function_name(pipeline_name, f"{base_name}_{operation_id}", version)
    else:
        function_name = sanitize_function_name(pipeline_name, base_name, version)
    logger.debug(f"Lambda function name generated: {function_name}")

    # Read YAML file from S3
    yaml_file_path = f"node_templates/{node.data.type.lower()}/{node.data.id}.yaml"
    yaml_data = read_yaml_from_s3(NODE_TEMPLATES_BUCKET, yaml_file_path)
    logger.debug(yaml_data)

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
    role_arn = create_lambda_role(pipeline_name, node.data.id, yaml_data, operation_id)

    # Wait for the role to propagate before attempting to create the Lambda function
    try:
        # Use the same role name construction logic as in create_lambda_role
        base_role_name = f"{resource_prefix}_{pipeline_name}_{node.data.id}_lambda_execution_role"
        
        if operation_id:
            # Calculate how much space we have left for the operation_id
            max_base_length = 63 - len(operation_id) - 1  # 63 to leave room for the underscore
            
            if len(base_role_name) > max_base_length:
                # Truncate the base_role_name to make room for the operation_id
                base_role_name = base_role_name[:max_base_length]
            
            # Now add the operation_id
            role_name = sanitize_role_name(f"{base_role_name}_{operation_id}")
        else:
            role_name = sanitize_role_name(base_role_name)
        
        # Ensure the final role name is within the 64-character limit
        if len(role_name) > 64:
            role_name = role_name[:64]
            
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
                    "Timeout": 300,
                    "Role": role_arn,
                    "Handler": "index.lambda_handler",
                    "Code": {"S3Bucket": IAC_ASSETS_BUCKET, "S3Key": zip_file_key},
                    "Publish": True,
                }

                # Common environment variables for all Lambda functions
                common_env_vars = {
                    "LARGE_PAYLOAD_BUCKET": os.environ.get("EXTERNAL_PAYLOAD_BUCKET"),
                    "EVENT_BUS_NAME": INGEST_EVENT_BUS_NAME or "default-event-bus",
                }

                # Only include additional Environment variables if the node type is "integration"
                if node.data.type.lower() == "integration":
                    env_vars = {
                        **common_env_vars,  # Include common env vars
                        "WORKFLOW_STEP_NAME": function_name,
                        "IS_LAST_STEP": os.environ.get("IS_LAST_STEP", "false"),
                        "REQUEST_TEMPLATES_PATH": request_templates_path,
                        "RESPONSE_TEMPLATES_PATH": response_templates_path,
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
                        "API_TEMPLATE_BUCKET": os.environ.get("NODE_TEMPLATES_BUCKET"),
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
                if node.data.type.lower() == "utility" and node.data.id == 'embedding_store':
                    # Extract Index Name and Content Type from node configuration
                    index_name = node.data.configuration.get("Index Name", "embeddings")
                    content_type = node.data.configuration.get("Content Type", "text")
                    
                    env_vars = {
                        **common_env_vars,  # Include common env vars
                        "OPENSEARCH_ENDPOINT": os.environ.get(
                            "OPENSEARCH_ENDPOINT"
                        ),
                        "INDEX_NAME": index_name,
                        "CONTENT_TYPE": content_type
                    }
                    create_function_params["Environment"] = {"Variables": env_vars}
                    
                    logger.info(f"Added environment variables for embedding_store Lambda: INDEX_NAME={index_name}, CONTENT_TYPE={content_type}")
                    
                    # Add VPC configuration for the embedding_store Lambda to access OpenSearch
                    # OPENSEARCH_VPC_SUBNET_IDS contains a comma-separated list of subnet IDs
                    subnet_ids = OPENSEARCH_VPC_SUBNET_IDS.split(',') if OPENSEARCH_VPC_SUBNET_IDS else []
                    create_function_params["VpcConfig"] = {
                        "SubnetIds": subnet_ids,
                        "SecurityGroupIds": [OPENSEARCH_SECURITY_GROUP_ID]
                    }
                    logger.info(f"Added VPC configuration to embedding_store Lambda: Subnets={subnet_ids}, SecurityGroup={OPENSEARCH_SECURITY_GROUP_ID}")
                # For all other node types, just add the common environment variables
                elif node.data.type.lower() != "integration":  # Integration nodes already handled above
                    create_function_params["Environment"] = {"Variables": common_env_vars}
                    logger.info(f"Added common environment variables to {node.data.type} Lambda function: {function_name}")
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

        return function_arn
    except Exception as e:
        # Use logger.exception which automatically includes the traceback
        logger.exception(
            f"Failed to create/update Lambda function {function_name}: {e}"
        )
        raise
