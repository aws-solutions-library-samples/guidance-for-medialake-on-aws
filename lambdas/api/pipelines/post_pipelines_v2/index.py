import os
import json
import re
import uuid
import yaml
from datetime import datetime
from typing import Dict, Any, List, Optional
import time

import boto3
from pydantic import BaseModel, Field

from aws_lambda_powertools import Logger, Tracer, Metrics
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.event_handler.api_gateway import (
    APIGatewayRestResolver,
    CORSConfig,
)

# Initialize AWS Lambda Powertools utilities
logger = Logger()
tracer = Tracer()
metrics = Metrics(namespace="PostPipeliNeV2")

# Configure CORS and API Gateway resolver
cors_config = CORSConfig(allow_origin="*", allow_headers=["*"])
app = APIGatewayRestResolver(cors=cors_config)

# Environment variables
ACCOUNT_ID = os.environ.get("ACCOUNT_ID")
NODE_TABLE = os.environ.get("NODE_TABLE")
PIPELINES_TABLE = os.environ.get("PIPELINES_TABLE")
IAC_BUCKET = os.environ.get("IAC_ASSETS_BUCKET")
NODE_TEMPLATES_BUCKET = os.environ.get("NODE_TEMPLATES_BUCKET")


NODE_TEMPLATES_BUCKET = os.environ.get("NODE_TEMPLATES_BUCKET")
if not all(
    [ACCOUNT_ID, NODE_TABLE, PIPELINES_TABLE, IAC_BUCKET, NODE_TEMPLATES_BUCKET]
):
    raise ValueError("One or more required environment variables are not set.")


# --------
# Data Models (Pydantic)
# --------
class NodeData(BaseModel):
    id: str
    type: str
    label: str
    icon: Dict[str, Any]
    inputTypes: List[str] = Field(default_factory=list)
    outputTypes: List[str] = Field(default_factory=list)
    configuration: Dict[str, Any]


class Node(BaseModel):
    id: str
    type: str
    position: Dict[str, Any]
    width: str
    height: str
    data: NodeData


class Edge(BaseModel):
    source: str
    sourceHandle: Optional[str]
    target: str
    targetHandle: Optional[str]
    id: str
    type: str
    data: Dict[str, Any]


class Settings(BaseModel):
    autoStart: bool
    retryAttempts: int
    timeout: int


class Configuration(BaseModel):
    nodes: List[Node]
    edges: List[Edge]
    settings: Settings


class PipelineDefinition(BaseModel):
    name: str
    description: str
    configuration: Configuration


def parse_pipeline_definition(event: Dict[str, Any]) -> PipelineDefinition:
    logger.info("Parsing pipeline definition from event body")
    body = json.loads(event.get("body", "{}"))
    pipeline = PipelineDefinition(**body)
    logger.debug(f"Parsed pipeline definition: {pipeline}")
    return pipeline


# --------
# Helper Functions
# --------
def get_node_info_from_dynamodb(node_id: str) -> Dict[str, Any]:
    logger.info(f"Retrieving node info from DynamoDB for node_id: {node_id}")
    dynamodb = boto3.resource("dynamodb")
    table_name = os.environ.get("NODE_TABLE")
    if not table_name:
        msg = "Environment variable NODE_TABLE is not set."
        logger.error(msg)
        raise ValueError(msg)
    table = dynamodb.Table(table_name)

    # Adjust the key to match the table schema.
    # For example, if the partition key is "pk" and the sort key is "sk" and your records use a prefix "NODE#":
    key = {"pk": f"NODE#{node_id}", "sk": "INFO"}
    logger.debug(f"Using DynamoDB key: {key}")

    response = table.get_item(Key=key)
    node_info = response.get("Item", {})
    logger.info(f"Retrieved node info for {node_id}: {node_info}")
    return node_info


def sanitize_function_name(pipeline_name, node_label, version):
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
    logger.info(f"Reading YAML file from S3: {bucket}/{key}")
    s3 = boto3.client("s3")
    try:
        response = s3.get_object(Bucket=bucket, Key=key)
        yaml_content = response["Body"].read().decode("utf-8")
        return yaml.safe_load(yaml_content)
    except Exception as e:
        logger.exception(f"Failed to read YAML file from S3: {e}")
        raise


def get_zip_file_key(bucket: str, prefix: str) -> str:
    s3 = boto3.client("s3")
    response = s3.list_objects_v2(Bucket=bucket, Prefix=prefix)

    for obj in response.get("Contents", []):
        if obj["Key"].endswith(".zip"):
            return obj["Key"]

    raise ValueError(f"No zip file found in {bucket}/{prefix}")


def create_iam_lambda_s3_dynamo_rw_policy():
    iam_lambda_s3_dynamo_rw_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": [
                    "dynamodb:UpdateItem",
                    "dynamodb:GetItem",
                    "dynamodb:PutItem",
                ],
                "Resource": [f"{os.environ['MEDIALAKE_ASSET_TABLE']}"],
            },
            {
                "Effect": "Allow",
                "Action": ["s3:GetObject", "s3:PutObject", "s3:PutObjectAcl"],
                "Resource": [
                    f"arn:aws:s3:::{os.environ['MEDIA_ASSETS_BUCKET_NAME']}/*",
                    f"arn:aws:s3:::{os.environ['MEDIA_ASSETS_BUCKET_NAME']}",
                ],
            },
            {
                "Effect": "Allow",
                "Action": ["s3:GetObject"],
                "Resource": [
                    f"arn:aws:s3:::*",
                    f"arn:aws:s3:::*/*",
                ],
            },
            {
                "Effect": "Allow",
                "Action": [
                    "kms:Encrypt",
                    "kms:Decrypt",
                    "kms:ReEncrypt*",
                    "kms:GenerateDataKey*",
                    "kms:DescribeKey",
                ],
                "Resource": ["*"],
            },
            {
                "Effect": "Allow",
                "Action": ["kms:GenerateDataKey"],
                "Resource": [
                    os.environ["MEDIA_ASSETS_BUCKET_NAME_KMS_KEY"],
                ],
            },
        ],
    }
    return iam_lambda_s3_dynamo_rw_policy


def wait_for_role_deletion(role_name: str, max_attempts: int = 40) -> None:
    """Wait for an IAM role to be fully deleted."""
    iam_client = boto3.client("iam")
    attempt = 0

    while attempt < max_attempts:
        try:
            iam_client.get_role(RoleName=role_name)
            attempt += 1
            logger.info(
                f"Role {role_name} is still being deleted, waiting... (attempt {attempt}/{max_attempts})"
            )
            time.sleep(5)  # Wait 5 seconds between checks
        except iam_client.exceptions.NoSuchEntityException:
            logger.info(f"Role {role_name} has been deleted")
            return
        except Exception as e:
            logger.error(f"Error checking role status: {e}")
            attempt += 1
            time.sleep(5)

    raise TimeoutError(
        f"Role {role_name} deletion timed out after {max_attempts} attempts"
    )


def delete_role(role_name: str) -> None:
    """Delete an IAM role and its attached policies."""
    iam_client = boto3.client("iam")
    try:
        # First detach all policies
        paginator = iam_client.get_paginator("list_attached_role_policies")
        for page in paginator.paginate(RoleName=role_name):
            for policy in page["AttachedPolicies"]:
                logger.info(
                    f"Detaching policy {policy['PolicyArn']} from role {role_name}"
                )
                iam_client.detach_role_policy(
                    RoleName=role_name, PolicyArn=policy["PolicyArn"]
                )

        # Then delete the role
        iam_client.delete_role(RoleName=role_name)
        logger.info(f"Deleted role: {role_name}")
    except iam_client.exceptions.NoSuchEntityException:
        logger.debug(f"Role {role_name} does not exist")
    except Exception as e:
        logger.error(f"Error deleting role: {e}")
        raise


def create_sfn_role(role_name: str) -> str:
    """Create a Step Functions execution role."""
    iam_client = boto3.client("iam")

    # Define the trust relationship policy
    trust_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"Service": "states.amazonaws.com"},
                "Action": "sts:AssumeRole",
            }
        ],
    }

    try:
        # Check if role exists
        try:
            iam_client.get_role(RoleName=role_name)
            logger.info(f"Found existing role {role_name}, deleting it")
            delete_role(role_name)
            wait_for_role_deletion(role_name)
        except iam_client.exceptions.NoSuchEntityException:
            pass

        # Create the IAM role
        logger.info(f"Creating new role: {role_name}")
        response = iam_client.create_role(
            RoleName=role_name, AssumeRolePolicyDocument=json.dumps(trust_policy)
        )

        role_arn = response["Role"]["Arn"]

        # Wait for role to be available
        waiter = iam_client.get_waiter("role_exists")
        waiter.wait(RoleName=role_name, WaiterConfig={"Delay": 1, "MaxAttempts": 10})

        # Attach necessary policies
        iam_client.attach_role_policy(
            RoleName=role_name,
            PolicyArn="arn:aws:iam::aws:policy/service-role/AWSLambdaRole",
        )

        logger.info(f"Role {role_name} created successfully with ARN: {role_arn}")
        return role_arn

    except Exception as e:
        logger.error(f"Error creating role: {str(e)}")
        raise


def process_policy_template(template_str: str) -> str:
    """Process a policy template string by replacing environment variables."""
    # Find all ${VAR} patterns in the template
    var_pattern = r"\${([^}]+)}"
    matches = re.finditer(var_pattern, template_str)

    # Replace each match with the corresponding environment variable value
    result = template_str
    for match in matches:
        var_name = match.group(1)
        var_value = os.environ.get(var_name, "")
        if not var_value and var_name not in [
            "EXTERNAL_PAYLOAD_BUCKET"
        ]:  # Allow some vars to be empty
            raise ValueError(f"Required environment variable {var_name} not set")
        result = result.replace(f"${{{var_name}}}", var_value)

    return result


def create_lambda_execution_policy(role_name: str, yaml_data: Dict[str, Any]) -> None:
    """Create and attach the execution policy to the Lambda role based on YAML configuration."""
    iam = boto3.client("iam")

    # Default policy if no IAM policy is defined in YAML
    default_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": ["s3:GetObject", "s3:PutObject"],
                "Resource": [
                    f"arn:aws:s3:::{os.environ['NODE_TEMPLATES_BUCKET']}/*",
                    f"arn:aws:s3:::{os.environ['IAC_BUCKET']}/*",
                ],
            },
            {
                "Effect": "Allow",
                "Action": ["dynamodb:GetItem", "dynamodb:PutItem"],
                "Resource": [
                    f"arn:aws:dynamodb:{os.environ.get('AWS_REGION', 'us-east-1')}:{os.environ['ACCOUNT_ID']}:table/{os.environ['NODE_TABLE']}",
                ],
            },
        ],
    }

    try:
        # Get IAM policy from YAML if it exists
        policy_document = default_policy
        if (
            yaml_data.get("node", {})
            .get("integration", {})
            .get("config", {})
            .get("lambda", {})
            .get("iam_policy")
        ):
            statements = yaml_data["node"]["integration"]["config"]["lambda"][
                "iam_policy"
            ]["statements"]

            # Process each statement to replace environment variables
            processed_statements = []
            for statement in statements:
                # Convert statement to JSON string to process all nested values
                statement_str = json.dumps(statement)
                processed_str = process_policy_template(statement_str)
                processed_statement = json.loads(processed_str)
                processed_statements.append(processed_statement)

            policy_document = {
                "Version": "2012-10-17",
                "Statement": processed_statements,
            }

        # Create inline policy
        policy_name = f"{role_name}ExecutionPolicy"
        iam.put_role_policy(
            RoleName=role_name,
            PolicyName=policy_name,
            PolicyDocument=json.dumps(policy_document),
        )
        logger.info(
            f"Successfully attached inline policy {policy_name} to role {role_name}"
        )
    except Exception as e:
        logger.error(f"Error creating/attaching policy to role {role_name}: {str(e)}")
        raise


def create_lambda_role(node_id: str, yaml_data: Dict[str, Any]) -> str:
    """Create a Lambda execution role."""
    iam = boto3.client("iam")
    role_name = f"{node_id}LambdaExecutionRole"
    max_retries = 3
    retry_delay = 2  # seconds

    assume_role_policy_document = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"Service": "lambda.amazonaws.com"},
                "Action": "sts:AssumeRole",
            }
        ],
    }

    try:
        # Check if role exists
        try:
            iam.get_role(RoleName=role_name)
            logger.info(f"Found existing role {role_name}, deleting it")
            delete_role(role_name)
            wait_for_role_deletion(role_name)
        except iam.exceptions.NoSuchEntityException:
            pass

        # Create the role with retries
        logger.info(f"Creating new role: {role_name}")
        for attempt in range(max_retries):
            try:
                response = iam.create_role(
                    RoleName=role_name,
                    AssumeRolePolicyDocument=json.dumps(assume_role_policy_document),
                )

                role_arn = response["Role"]["Arn"]

                # Wait for role to be available
                waiter = iam.get_waiter("role_exists")
                waiter.wait(
                    RoleName=role_name, WaiterConfig={"Delay": 1, "MaxAttempts": 10}
                )

                # Attach the basic execution policy
                iam.attach_role_policy(
                    RoleName=role_name,
                    PolicyArn="arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
                )

                # Create and attach our custom execution policy
                create_lambda_execution_policy(role_name, yaml_data)

                logger.info(
                    f"Role {role_name} created successfully with ARN: {role_arn}"
                )
                return role_arn

            except iam.exceptions.EntityAlreadyExistsException:
                # Role was created by another process while we were trying
                logger.info(f"Role {role_name} was created by another process")
                return iam.get_role(RoleName=role_name)["Role"]["Arn"]

            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(
                        f"Failed to create role '{role_name}' after {max_retries} attempts: {str(e)}"
                    )
                    raise
                logger.warning(f"Attempt {attempt + 1}/{max_retries} failed: {str(e)}")
                time.sleep(retry_delay * (attempt + 1))  # Exponential backoff

    except Exception as e:
        logger.error(f"Error creating role: {str(e)}")
        raise


def wait_for_lambda_deletion(function_name: str, max_attempts: int = 40) -> None:
    """Wait for a Lambda function to be fully deleted."""
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
    """Check if a Lambda function exists."""
    lambda_client = boto3.client("lambda")
    try:
        lambda_client.get_function(FunctionName=function_name)
        return True
    except lambda_client.exceptions.ResourceNotFoundException:
        return False


def delete_lambda_function(function_name: str) -> None:
    """Delete a Lambda function if it exists."""
    lambda_client = boto3.client("lambda")
    try:
        lambda_client.delete_function(FunctionName=function_name)
        logger.info(f"Deleted existing Lambda function: {function_name}")
    except lambda_client.exceptions.ResourceNotFoundException:
        logger.debug(f"Lambda function {function_name} does not exist")


def create_lambda_function(pipeline_name: str, node: Node) -> str:
    logger.info(f"Creating/updating Lambda function for node: {node.id}")
    lambda_client = boto3.client("lambda")

    version = node.data.configuration.get("version", "v1")
    function_name = sanitize_function_name(pipeline_name, node.data.label, version)
    logger.debug(f"Lambda function name generated: {function_name}")

    # Read YAML file from S3
    yaml_file_path = f"node_templates/integrations/{node.data.id}.yaml"
    yaml_data = read_yaml_from_s3(NODE_TEMPLATES_BUCKET, yaml_file_path)
    logger.debug(yaml_data)

    # Get Lambda configuration from YAML
    lambda_config = yaml_data["node"]["integration"]["config"]["lambda"]
    zip_file_prefix = f"lambda-code/nodes/{lambda_config['handler']}"

    # Get the actual zip file key
    zip_file_key = get_zip_file_key(IAC_BUCKET, zip_file_prefix)

    runtime = lambda_config["runtime"].lower()
    role_arn = create_lambda_role(node.data.id, yaml_data)

    max_retries = 3
    retry_delay = 2  # seconds

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
                    time.sleep(retry_delay * (attempt + 1))  # Exponential backoff
                    continue
                raise
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(
                        f"Failed to create Lambda function after {max_retries} attempts: {str(e)}"
                    )
                    raise
                logger.warning(f"Attempt {attempt + 1}/{max_retries} failed: {str(e)}")
                time.sleep(retry_delay * (attempt + 1))  # Exponential backoff

        return function_arn
    except Exception as e:
        logger.exception(
            f"Failed to create/update Lambda function {function_name}: {e}"
        )
        raise


def build_step_function_definition(
    pipeline: PipelineDefinition, lambda_arns: Dict[str, str]
) -> Dict[str, Any]:
    logger.info("Building Step Functions state machine definition")
    states = {}
    for node in pipeline.configuration.nodes:
        node_id = node.data.id
        lambda_arn = lambda_arns.get(node_id)
        if not lambda_arn:
            logger.warning(
                f"No Lambda ARN found for node {node_id}; skipping state creation."
            )
            continue

        state_def = {
            "Type": "Task",
            "Resource": lambda_arn,
            "Retry": [
                {
                    "ErrorEquals": ["States.ALL"],
                    "IntervalSeconds": 2,
                    "MaxAttempts": pipeline.configuration.settings.retryAttempts,
                    "BackoffRate": 2.0,
                }
            ],
            "End": True,
        }
        states[node_id] = state_def
        logger.debug(f"State definition for node {node_id}: {state_def}")

    start_at = (
        pipeline.configuration.nodes[0].data.id
        if pipeline.configuration.nodes
        else None
    )
    definition = {
        "Comment": f"State machine for pipeline {pipeline.name}",
        "StartAt": start_at,
        "States": states,
    }
    logger.info(f"Built state machine definition: {definition}")
    return definition


def wait_for_state_machine_deletion(
    state_machine_name: str, max_attempts: int = 40
) -> None:
    """Wait for a state machine to be fully deleted."""
    sfn_client = boto3.client("stepfunctions")
    attempt = 0

    while attempt < max_attempts:
        try:
            paginator = sfn_client.get_paginator("list_state_machines")
            exists = False
            for page in paginator.paginate():
                for state_machine in page["stateMachines"]:
                    if state_machine["name"] == state_machine_name:
                        exists = True
                        break
                if exists:
                    break

            if not exists:
                logger.info(f"State machine {state_machine_name} has been deleted")
                return

            attempt += 1
            logger.info(
                f"State machine {state_machine_name} is still being deleted, waiting... (attempt {attempt}/{max_attempts})"
            )
            time.sleep(5)  # Wait 5 seconds between checks

        except Exception as e:
            logger.error(f"Error checking state machine status: {e}")
            attempt += 1
            time.sleep(5)

    raise TimeoutError(
        f"State machine {state_machine_name} deletion timed out after {max_attempts} attempts"
    )


def check_step_function_exists(state_machine_name: str) -> bool:
    """Check if a Step Function state machine exists."""
    sfn_client = boto3.client("stepfunctions")
    try:
        paginator = sfn_client.get_paginator("list_state_machines")
        for page in paginator.paginate():
            for state_machine in page["stateMachines"]:
                if state_machine["name"] == state_machine_name:
                    return True
        return False
    except Exception as e:
        logger.error(f"Error checking Step Function existence: {e}")
        return False


def delete_step_function(state_machine_name: str) -> None:
    """Delete a Step Function state machine if it exists."""
    sfn_client = boto3.client("stepfunctions")
    try:
        # First get the ARN
        paginator = sfn_client.get_paginator("list_state_machines")
        for page in paginator.paginate():
            for state_machine in page["stateMachines"]:
                if state_machine["name"] == state_machine_name:
                    sfn_client.delete_state_machine(
                        stateMachineArn=state_machine["stateMachineArn"]
                    )
                    logger.info(f"Deleted existing Step Function: {state_machine_name}")
                    return
    except Exception as e:
        logger.error(f"Error deleting Step Function: {e}")


def create_step_function(
    pipeline_name: str, definition: Dict[str, Any]
) -> Dict[str, Any]:
    """Create a Step Functions state machine."""
    logger.info(f"Creating Step Functions state machine for pipeline: {pipeline_name}")
    sfn_client = boto3.client("stepfunctions")
    role_arn = create_sfn_role(f"{pipeline_name}StepFunctionRole")

    try:
        # Check if state machine exists
        if check_step_function_exists(pipeline_name):
            logger.info(f"Found existing Step Function {pipeline_name}, deleting it")
            delete_step_function(pipeline_name)
            wait_for_state_machine_deletion(pipeline_name)

        # Create new state machine
        logger.info(f"Creating new Step Function: {pipeline_name}")
        response = sfn_client.create_state_machine(
            name=pipeline_name,
            definition=json.dumps(definition),
            roleArn=role_arn,
        )
        logger.info(f"Created state machine for pipeline '{pipeline_name}': {response}")
        return response
    except Exception as e:
        logger.exception(
            f"Failed to create/update state machine for pipeline '{pipeline_name}': {e}"
        )
        raise


def compare_pipeline_definitions(
    existing_def: Dict[str, Any], new_def: Dict[str, Any]
) -> bool:
    """Compare two pipeline definitions to check if they are functionally equivalent."""
    # Compare nodes
    existing_nodes = {
        node["data"]["id"]: node
        for node in existing_def.get("configuration", {}).get("nodes", [])
    }
    new_nodes = {
        node["data"]["id"]: node
        for node in new_def.get("configuration", {}).get("nodes", [])
    }

    if existing_nodes.keys() != new_nodes.keys():
        return False

    for node_id, existing_node in existing_nodes.items():
        new_node = new_nodes[node_id]
        if (
            existing_node["data"]["type"] != new_node["data"]["type"]
            or existing_node["data"]["configuration"]
            != new_node["data"]["configuration"]
        ):
            return False

    # Compare edges
    existing_edges = {
        edge["id"]: edge
        for edge in existing_def.get("configuration", {}).get("edges", [])
    }
    new_edges = {
        edge["id"]: edge for edge in new_def.get("configuration", {}).get("edges", [])
    }

    if existing_edges.keys() != new_edges.keys():
        return False

    for edge_id, existing_edge in existing_edges.items():
        new_edge = new_edges[edge_id]
        if (
            existing_edge["source"] != new_edge["source"]
            or existing_edge["target"] != new_edge["target"]
        ):
            return False

    return True


def get_pipeline_by_name(
    pipeline_name: str, definition: Optional[Dict[str, Any]] = None
) -> Optional[Dict[str, Any]]:
    """
    Get pipeline record from DynamoDB by name and optionally check if definition matches.

    Args:
        pipeline_name: Name of the pipeline to look up
        definition: Optional pipeline definition to compare against

    Returns:
        Pipeline record if found and definition matches (if provided), None otherwise
    """
    logger.info(f"Looking up pipeline with name: {pipeline_name}")
    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(PIPELINES_TABLE)

    try:
        # Scan for items with matching name
        response = table.scan(
            FilterExpression="#n = :name",
            ExpressionAttributeNames={"#n": "name"},
            ExpressionAttributeValues={":name": pipeline_name},
        )
        items = response.get("Items", [])
        if items:
            pipeline = items[0]
            # Check if the pipeline has a definition
            if "definition" in pipeline:
                # If definition is provided, check if it matches
                if definition and not compare_pipeline_definitions(
                    pipeline["definition"], definition
                ):
                    logger.info("Found pipeline but definition does not match")
                    return None
                return pipeline
        return None
    except Exception as e:
        logger.error(f"Error looking up pipeline: {e}")
        return None


def store_pipeline_info(
    pipeline: PipelineDefinition, state_machine_arn: str, lambda_arns: Dict[str, str]
) -> None:
    """Store or update pipeline information in DynamoDB."""
    logger.info("Storing/updating pipeline information in DynamoDB")
    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(PIPELINES_TABLE)

    # Check for existing pipeline with same name and definition
    existing_pipeline = get_pipeline_by_name(pipeline.name, pipeline.dict())
    now_iso = datetime.utcnow().isoformat()

    dependent_resources = []
    for node_id, arn in lambda_arns.items():
        dependent_resources.append(["lambda", arn])
        logger.debug(f"Added dependent resource for node {node_id}: lambda -> {arn}")
    dependent_resources.append(["step_function", state_machine_arn])
    logger.debug(
        f"Added dependent resource for state machine: step_function -> {state_machine_arn}"
    )

    if existing_pipeline:
        # Update existing pipeline
        pipeline_id = existing_pipeline["id"]
        logger.info(f"Updating existing pipeline with id {pipeline_id}")

        try:
            update_expr = """
            SET #def = :def,
                #res = :res,
                #arn = :arn,
                #up = :updated
            """

            expr_values = {
                ":def": pipeline.dict(),
                ":res": dependent_resources,
                ":arn": state_machine_arn,
                ":updated": now_iso,
            }

            expr_names = {
                "#def": "definition",
                "#res": "dependentResources",
                "#arn": "stateMachineArn",
                "#up": "updatedAt",
            }

            table.update_item(
                Key={"id": pipeline_id},
                UpdateExpression=update_expr,
                ExpressionAttributeValues=expr_values,
                ExpressionAttributeNames=expr_names,
            )
            logger.info(f"Successfully updated pipeline info with id {pipeline_id}")
        except Exception as e:
            logger.exception(f"Failed to update pipeline info: {e}")
            raise
    else:
        # Create new pipeline
        pipeline_id = str(uuid.uuid4())
        item = {
            "id": pipeline_id,
            "createdAt": now_iso,
            "updatedAt": now_iso,
            "definition": pipeline.dict(),
            "dependentResources": dependent_resources,
            "name": pipeline.name,
            "stateMachineArn": state_machine_arn,
            "type": "Ingest Triggered",
            "system": False,
        }

        try:
            table.put_item(Item=item)
            logger.info(f"Successfully stored new pipeline info with id {pipeline_id}")
        except Exception as e:
            logger.exception(f"Failed to store pipeline info: {e}")
            raise


# --------
# Route Handler
# --------
@app.post("/pipelinesv2")
@tracer.capture_method
def create_pipeline() -> Dict[str, Any]:
    """
    Create or update a pipeline based on the provided configuration.
    """
    try:
        logger.info("Received request to create/update a pipeline")
        request_data = app.current_event.json_body
        pipeline = PipelineDefinition(**request_data)
        logger.debug(f"Pipeline configuration: {pipeline}")

        pipeline_name = pipeline.name
        logger.info(f"Processing pipeline: {pipeline_name} - {pipeline.description}")

        # Check if a pipeline with this name already exists
        existing_pipeline = get_pipeline_by_name(pipeline_name)
        if existing_pipeline:
            error_body = {
                "error": "Pipeline name already exists",
                "details": f"A pipeline with the name '{pipeline_name}' already exists. Please use a different name.",
            }
            logger.info(
                f"Rejecting pipeline creation - name already exists: {pipeline_name}"
            )
            return {
                "statusCode": 400,
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*",
                },
                "body": json.dumps(error_body),
            }

        # Create/update Lambda functions for each node
        lambda_arns = {}
        for node in pipeline.configuration.nodes:
            logger.info(f"Processing node with id: {node.id}")
            logger.info(node.id)
            lambda_arn = create_lambda_function(pipeline_name, node)
            lambda_arns[node.data.id] = lambda_arn

        # Log edge processing (if any)
        for edge in pipeline.configuration.edges:
            logger.info(
                f"Processing edge: {edge.id} from {edge.source} to {edge.target}"
            )

        settings = pipeline.configuration.settings
        logger.info(
            f"Pipeline settings: AutoStart={settings.autoStart}, RetryAttempts={settings.retryAttempts}, Timeout={settings.timeout}"
        )

        # Build and create/update the state machine
        state_machine_definition = build_step_function_definition(pipeline, lambda_arns)
        sfn_response = create_step_function(pipeline_name, state_machine_definition)
        state_machine_arn = sfn_response.get("stateMachineArn")
        logger.info(f"State machine ARN: {state_machine_arn}")

        # Store/update pipeline info in DynamoDB
        store_pipeline_info(pipeline, state_machine_arn, lambda_arns)

        # If we found an existing pipeline with identical name and definition,
        # we still recreated all resources but didn't create a new DB record
        action = "recreated" if existing_pipeline else "created"
        response_body = {
            "message": f"Pipeline {action} successfully",
            "pipeline_name": pipeline_name,
            "state_machine_arn": state_machine_arn,
        }
        logger.info(f"Returning success response: {response_body}")
        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
            },
            "body": json.dumps(response_body),
        }

    except Exception as e:
        logger.exception("Error creating/updating pipeline")
        error_body = {"error": "Failed to create/update pipeline", "details": str(e)}
        logger.error(f"Returning error response: {error_body}")
        return {
            "statusCode": 500,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
            },
            "body": json.dumps(error_body),
        }


# --------
# Lambda Handler
# --------
@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """
    AWS Lambda handler entry point.
    """
    logger.info("Lambda handler invoked", extra={"event": event})
    response = app.resolve(event, context)
    logger.info(f"Returning response from lambda_handler: {response}")
    return response
