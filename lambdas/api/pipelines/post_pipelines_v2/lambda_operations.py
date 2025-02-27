import os
import re
import time
import yaml
from typing import Dict, Any, Optional

import boto3
from aws_lambda_powertools import Logger

from config import IAC_BUCKET, NODE_TEMPLATES_BUCKET
from iam_operations import create_lambda_role, wait_for_role_propagation

# Initialize logger
logger = Logger()


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
    raw_name = f"{pipeline_name}-{node_label}-{version}".lower()

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

    version = node.data.configuration.get("version", "v1")
    function_name = sanitize_function_name(pipeline_name, node.data.label, version)
    logger.debug(f"Lambda function name generated: {function_name}")

    # Read YAML file from S3
    yaml_file_path = f"node_templates/{node.data.type.lower()}/{node.data.id}.yaml"
    yaml_data = read_yaml_from_s3(NODE_TEMPLATES_BUCKET, yaml_file_path)
    logger.debug(yaml_data)

    # Get Lambda configuration from YAML
    lambda_config = yaml_data["node"]["integration"]["config"]["lambda"]
    zip_file_prefix = f"lambda-code/nodes/{lambda_config['handler']}"

    # Get the actual zip file key
    zip_file_key = get_zip_file_key(IAC_BUCKET, zip_file_prefix)

    runtime = lambda_config["runtime"].lower()
    role_arn = create_lambda_role(node.data.id, yaml_data)

    # Wait for the role to propagate before attempting to create the Lambda function
    try:
        wait_for_role_propagation(f"{node.data.id}LambdaExecutionRole")
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
                response = lambda_client.create_function(
                    FunctionName=function_name,
                    Runtime=runtime,
                    Timeout=300,
                    Role=role_arn,
                    Handler="lambda_function.lambda_handler",
                    Code={"S3Bucket": IAC_BUCKET, "S3Key": zip_file_key},
                    Environment={
                        "Variables": {
                            # Core workflow variables
                            "WORKFLOW_STEP_NAME": os.environ.get(
                                "WORKFLOW_STEP_NAME", ""
                            ),
                            "IS_LAST_STEP": os.environ.get("IS_LAST_STEP", "false"),
                            # API Service Configuration
                            "API_SERVICE_URL": os.environ.get("API_SERVICE_URL", ""),
                            "API_SERVICE_RESOURCE": os.environ.get(
                                "API_SERVICE_RESOURCE", ""
                            ),
                            "API_SERVICE_PATH": os.environ.get("API_SERVICE_PATH", ""),
                            "API_SERVICE_METHOD": os.environ.get(
                                "API_SERVICE_METHOD", ""
                            ),
                            "API_AUTH_TYPE": os.environ.get("API_AUTH_TYPE", ""),
                            "API_SERVICE_NAME": os.environ.get("API_SERVICE_NAME", ""),
                            "API_TEMPLATE_BUCKET": os.environ.get(
                                "API_TEMPLATE_BUCKET", ""
                            ),
                            "API_CUSTOM_URL": os.environ.get("API_CUSTOM_URL", "false"),
                            "API_CUSTOM_CODE": os.environ.get(
                                "API_CUSTOM_CODE", "false"
                            ),
                            # S3 Configuration
                            "EXTERNAL_PAYLOAD_S3_BUCKET": os.environ.get(
                                "EXTERNAL_PAYLOAD_S3_BUCKET", ""
                            ),
                            # Custom Headers (defaults to empty JSON object)
                            "CUSTOM_HEADERS": os.environ.get("CUSTOM_HEADERS", "{}"),
                        }
                    },
                    Publish=True,
                )
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
                logger.warning(f"Attempt {attempt + 1}/{max_retries} failed: {str(e)}")
                # More aggressive exponential backoff
                backoff_time = retry_delay * (2**attempt)
                logger.info(f"Waiting {backoff_time} seconds before retry")
                time.sleep(backoff_time)

        return function_arn
    except Exception as e:
        logger.exception(
            f"Failed to create/update Lambda function {function_name}: {e}"
        )
        raise
