import json
import os
import re
import time
import traceback
from typing import Any, Dict, List

import boto3
from aws_lambda_powertools import Logger

from config import MEDIALAKE_ASSET_TABLE, PIPELINES_EVENT_BUS_NAME

# Initialize logger
logger = Logger()

resource_prefix = os.environ["RESOURCE_PREFIX"]


def sanitize_role_name(name: str) -> str:
    """Sanitize the role name to comply with AWS IAM naming rules."""
    # Remove any characters that are not alphanumeric or in the set +=,.@_-
    sanitized = re.sub(r"[^a-zA-Z0-9+=,.@_-]", "", name)

    # Ensure the name doesn't start with 'aws' or 'AWS'
    if sanitized.lower().startswith("aws"):
        sanitized = "_" + sanitized

    # Truncate to 64 characters if necessary (IAM role name limit)
    return sanitized[:64]


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


def wait_for_role_propagation(role_name: str, max_attempts: int = 20) -> None:
    """
    Wait for an IAM role to be fully propagated and ready to be assumed by Lambda.

    This function uses a combination of checks and delays to ensure the role has
    propagated through AWS's systems before it's used to create a Lambda function.
    """
    iam_client = boto3.client("iam")
    attempt = 0
    delay_seconds = 5  # Start with 5 seconds delay

    logger.info(f"Waiting for role {role_name} to propagate...")

    while attempt < max_attempts:
        try:
            # Get the role ARN
            response = iam_client.get_role(RoleName=role_name)
            response["Role"]["Arn"]

            # Check if the role exists and has the basic execution policy attached
            attached_policies = iam_client.list_attached_role_policies(
                RoleName=role_name
            )

            # If we can get the role and its policies, wait a bit more to ensure propagation
            logger.info(
                f"Role {role_name} exists with {len(attached_policies.get('AttachedPolicies', []))} policies attached"
            )

            # Exponential backoff with a cap
            wait_time = min(delay_seconds * (2**attempt), 30)
            logger.info(
                f"Waiting {wait_time} seconds for role propagation (attempt {attempt + 1}/{max_attempts})"
            )
            time.sleep(wait_time)

            # After a few attempts, assume the role has propagated enough
            if attempt >= 2:  # After 3rd attempt (0-indexed)
                logger.info(
                    f"Role {role_name} should be sufficiently propagated after {attempt + 1} attempts"
                )
                return

            attempt += 1

        except iam_client.exceptions.NoSuchEntityException:
            logger.error(f"Role {role_name} does not exist")
            raise
        except Exception as e:
            logger.warning(f"Error checking role propagation status: {e}")
            attempt += 1
            time.sleep(delay_seconds)

    logger.warning(
        f"Role propagation check timed out after {max_attempts} attempts, proceeding anyway"
    )


def delete_role(role_name: str) -> None:
    """Delete an IAM role and its attached policies."""
    iam_client = boto3.client("iam")
    try:
        # First delete all inline policies
        try:
            # List all inline policies
            inline_policies = iam_client.list_role_policies(RoleName=role_name)

            # Delete each inline policy
            for policy_name in inline_policies.get("PolicyNames", []):
                logger.info(
                    f"Deleting inline policy {policy_name} from role {role_name}"
                )
                iam_client.delete_role_policy(
                    RoleName=role_name, PolicyName=policy_name
                )
        except Exception as inline_err:
            logger.error(f"Error deleting inline policies: {inline_err}")
            # Continue with other cleanup even if this fails

        # Next detach all managed policies
        paginator = iam_client.get_paginator("list_attached_role_policies")
        for page in paginator.paginate(RoleName=role_name):
            for policy in page["AttachedPolicies"]:
                logger.info(
                    f"Detaching policy {policy['PolicyArn']} from role {role_name}"
                )
                iam_client.detach_role_policy(
                    RoleName=role_name, PolicyArn=policy["PolicyArn"]
                )

        # Finally delete the role
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


def standardize_policy_statement(statement: Dict[str, Any]) -> Dict[str, Any]:
    """
    Standardize a policy statement to ensure correct capitalization and format.

    This function ensures that:
    1. Keys are properly capitalized (Effect, Action, Resource)
    2. Action and Resource are always arrays
    """
    standardized = {}

    # Handle Effect (capitalize)
    if "effect" in statement:
        standardized["Effect"] = statement["effect"]
    elif "Effect" in statement:
        standardized["Effect"] = statement["Effect"]

    # Handle Action (capitalize and ensure it's an array)
    if "actions" in statement:
        actions = statement["actions"]
        standardized["Action"] = actions if isinstance(actions, list) else [actions]
    elif "action" in statement:
        actions = statement["action"]
        standardized["Action"] = actions if isinstance(actions, list) else [actions]
    elif "Action" in statement:
        actions = statement["Action"]
        standardized["Action"] = actions if isinstance(actions, list) else [actions]

    # Handle Resource (capitalize and ensure it's an array)
    if "resources" in statement:
        resources = statement["resources"]
        standardized["Resource"] = (
            resources if isinstance(resources, list) else [resources]
        )
    elif "resource" in statement:
        resources = statement["resource"]
        standardized["Resource"] = (
            resources if isinstance(resources, list) else [resources]
        )
    elif "Resource" in statement:
        resources = statement["Resource"]
        standardized["Resource"] = (
            resources if isinstance(resources, list) else [resources]
        )

    # Copy any other keys as-is
    for key, value in statement.items():
        if key.lower() not in ["effect", "action", "actions", "resource", "resources"]:
            standardized[key] = value

    return standardized


def deduplicate_policy_statements(
    statements: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Deduplicate policy statements to avoid redundancy.

    This function identifies and removes duplicate statements based on their
    Effect, Action, and Resource values.
    """

    # Helper function to create a hashable representation of a statement
    def statement_key(stmt):
        # Convert lists to tuples for hashability
        effect = stmt.get("Effect", "")

        # Sort and convert actions to a tuple
        actions = stmt.get("Action", [])
        if isinstance(actions, str):
            actions = [actions]
        actions = tuple(sorted(actions))

        # Sort and convert resources to a tuple
        resources = stmt.get("Resource", [])
        if isinstance(resources, str):
            resources = [resources]
        resources = tuple(sorted(resources))

        # Handle conditions if present (simplified)
        conditions = stmt.get("Condition", {})
        condition_str = json.dumps(conditions, sort_keys=True) if conditions else ""

        return (effect, actions, resources, condition_str)

    # Use a dictionary to track unique statements
    unique_statements = {}
    for stmt in statements:
        key = statement_key(stmt)
        # Only keep the first occurrence of each unique statement
        if key not in unique_statements:
            unique_statements[key] = stmt

    logger.info(
        f"Deduplicated {len(statements)} statements to {len(unique_statements)} unique statements"
    )
    return list(unique_statements.values())


def standardize_policy_document(policy_document: Dict[str, Any]) -> Dict[str, Any]:
    """
    Standardize an entire policy document to ensure correct format.

    This function processes all statements in a policy document to ensure they
    follow the correct format with proper capitalization and structure.
    """
    if "Statement" not in policy_document:
        return policy_document

    standardized_statements = []
    for statement in policy_document["Statement"]:
        standardized_statements.append(standardize_policy_statement(statement))

    return {
        "Version": policy_document.get("Version", "2012-10-17"),
        "Statement": standardized_statements,
    }


def process_policy_template(template_str: str) -> str:
    """Process a policy template string by replacing environment variables and CloudFormation parameters."""
    # Find all ${VAR} patterns in the template
    var_pattern = r"\${([^}]+)}"
    matches = re.finditer(var_pattern, template_str)

    # Replace each match with the corresponding environment variable value or CloudFormation parameter
    result = template_str
    for match in matches:
        var_name = match.group(1)

        # Handle CloudFormation parameters
        if var_name == "AWS::Region":
            # Get the current AWS region
            region = boto3.session.Session().region_name
            result = result.replace(f"${{{var_name}}}", region)
            logger.info(
                f"Replaced CloudFormation parameter ${{{var_name}}} with region: {region}"
            )
        elif var_name == "AWS::AccountId":
            # Get the current AWS account ID
            sts_client = boto3.client("sts")
            account_id = sts_client.get_caller_identity()["Account"]
            result = result.replace(f"${{{var_name}}}", account_id)
            logger.info(
                f"Replaced CloudFormation parameter ${{{var_name}}} with account ID: {account_id}"
            )
        else:
            # Handle regular environment variables
            var_value = os.environ.get(var_name, "")
            if not var_value:
                # Check if this is a known variable that might be empty
                if var_name in ["EXTERNAL_PAYLOAD_BUCKET"]:
                    # Allow some vars to be empty
                    result = result.replace(f"${{{var_name}}}", var_value)
                elif var_name == "MEDIA_ASSETS_BUCKET_ARN_KMS_KEY":
                    # Special handling for KMS key ARN - use "*" as fallback
                    logger.warning(
                        f"Environment variable {var_name} not set, using '*' as fallback"
                    )
                    result = result.replace(f"${{{var_name}}}", "*")
                else:
                    # For other variables, try to construct them from other environment variables
                    if var_name.endswith("_ARN_KMS_KEY") and var_name.startswith(
                        "MEDIA_"
                    ):
                        # Try to construct KMS key ARN from bucket name
                        bucket_name_var = var_name.replace("_ARN_KMS_KEY", "_NAME")
                        bucket_name = os.environ.get(bucket_name_var, "")
                        if bucket_name:
                            # Construct a generic KMS key ARN pattern for the bucket
                            region = boto3.session.Session().region_name
                            account_id = boto3.client("sts").get_caller_identity()[
                                "Account"
                            ]
                            constructed_arn = f"arn:aws:kms:{region}:{account_id}:key/*"
                            logger.info(
                                f"Constructed KMS key ARN pattern for {var_name}: {constructed_arn}"
                            )
                            result = result.replace(f"${{{var_name}}}", constructed_arn)
                        else:
                            # If we can't construct it, use "*"
                            logger.warning(
                                f"Could not construct ARN for {var_name}, using '*' as fallback"
                            )
                            result = result.replace(f"${{{var_name}}}", "*")
                    else:
                        # For other variables, raise an error
                        raise ValueError(
                            f"Required environment variable {var_name} not set"
                        )
            else:
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
                    f"arn:aws:s3:::{os.environ['IAC_ASSETS_BUCKET']}/*",
                    f"arn:aws:s3:::{os.environ['EXTERNAL_PAYLOAD_BUCKET']}/*",
                ],
            },
            {
                "Effect": "Allow",
                "Action": ["s3:ListBucket"],
                "Resource": [
                    f"arn:aws:s3:::{os.environ['NODE_TEMPLATES_BUCKET']}",
                    f"arn:aws:s3:::{os.environ['IAC_ASSETS_BUCKET']}",
                ],
            },
            {
                "Effect": "Allow",
                "Action": ["dynamodb:GetItem", "dynamodb:PutItem"],
                "Resource": [
                    f"arn:aws:dynamodb:{os.environ.get('AWS_REGION', 'us-east-1')}:{os.environ['ACCOUNT_ID']}:table/{os.environ['NODE_TABLE']}",
                ],
            },
            {
                "Effect": "Allow",
                "Action": ["dynamodb:GetItem"],
                "Resource": [
                    MEDIALAKE_ASSET_TABLE,
                ],
            },
            {
                "Effect": "Allow",
                "Action": ["events:PutEvents"],
                "Resource": [
                    f"arn:aws:events:{os.environ.get('AWS_REGION', 'us-east-1')}:{os.environ['ACCOUNT_ID']}:event-bus/{PIPELINES_EVENT_BUS_NAME}",
                ],
            },
            {
                "Effect": "Allow",
                "Action": [
                    "kms:Decrypt",
                    "kms:GenerateDataKey",
                ],
                "Resource": ["*"],
            },
        ],
    }

    try:
        # Log environment variables for debugging

        # Start with the default policy statements
        policy_statements = default_policy["Statement"].copy()
        logger.info(f"YAML data: {yaml_data}")

        has_iam_policy = (
            yaml_data.get("node", {})
            .get("integration", {})
            .get("config", {})
            .get("lambda", {})
            .get("iam_policy")
        )

        logger.info(f"Has IAM policy in YAML: {has_iam_policy is not None}")

        if has_iam_policy:
            try:
                # statements = yaml_data["node"]["integration"]["config"]["lambda"][
                #     "iam_policy"
                # ]["statements"]

                statements = yaml_data["node"].get("integration", {}).get(
                    "config", {}
                ).get("lambda", {}).get("iam_policy", {}).get(
                    "statements"
                ) or yaml_data[
                    "node"
                ].get(
                    "utility", {}
                ).get(
                    "config", {}
                ).get(
                    "lambda", {}
                ).get(
                    "iam_policy", {}
                ).get(
                    "statements"
                )

                logger.info(f"Found {len(statements)} statements in YAML")

                # Process each statement to replace environment variables
                processed_statements = []
                for i, statement in enumerate(statements):
                    try:
                        # Convert statement to JSON string to process all nested values
                        statement_str = json.dumps(statement)
                        logger.info(f"Statement {i} before processing: {statement_str}")

                        processed_str = process_policy_template(statement_str)
                        logger.info(f"Statement {i} after processing: {processed_str}")

                        processed_statement = json.loads(processed_str)
                        # Standardize the statement to ensure correct format
                        standardized_statement = standardize_policy_statement(
                            processed_statement
                        )
                        processed_statements.append(standardized_statement)
                    except Exception as stmt_err:
                        logger.error(f"Error processing statement {i}: {stmt_err}")
                        raise

                # Add the processed YAML statements to the default policy statements
                policy_statements.extend(processed_statements)
                logger.info(
                    f"Combined {len(processed_statements)} YAML statements with default policy"
                )

                # Deduplicate the combined statements
                deduplicated_statements = deduplicate_policy_statements(
                    policy_statements
                )

                # Create the combined policy document
                policy_document = {
                    "Version": "2012-10-17",
                    "Statement": deduplicated_statements,
                }

                # Log the combined policy document
                logger.info(
                    f"Combined and deduplicated policy document: {json.dumps(policy_document)}"
                )
            except Exception as yaml_err:
                logger.error(f"Error processing YAML IAM policy: {yaml_err}")
                logger.info("Using default policy only")
                policy_document = default_policy
        else:
            # If no YAML policy, use the default policy
            policy_document = default_policy

        # Log the final policy document
        logger.info(f"Final policy document: {json.dumps(policy_document)}")

        # Create inline policy
        policy_name = f"{role_name}ExecutionPolicy"
        try:
            iam.put_role_policy(
                RoleName=role_name,
                PolicyName=policy_name,
                PolicyDocument=json.dumps(policy_document),
            )
            logger.info(
                f"Successfully attached inline policy {policy_name} to role {role_name}"
            )

            # Verify the policy was attached
            try:
                response = iam.get_role_policy(
                    RoleName=role_name, PolicyName=policy_name
                )
                logger.info(f"Verified policy attachment: {response}")
            except Exception as verify_err:
                logger.error(f"Failed to verify policy attachment: {verify_err}")

        except Exception as attach_err:
            logger.error(f"Error attaching policy to role: {attach_err}")
            raise

    except Exception as e:
        logger.error(f"Error creating/attaching policy to role {role_name}: {str(e)}")
        logger.error(f"Exception type: {type(e).__name__}")
        logger.error(f"Exception traceback: {traceback.format_exc()}")
        raise


def create_lambda_role(
    pipeline_name: str,
    node_id: str,
    yaml_data: Dict[str, Any],
    operation_id: str = "",
    lambda_function_name: str = "",
) -> str:
    """Create a Lambda execution role."""
    iam = boto3.client("iam")

    # Use the lambda function name as the role name if provided
    if lambda_function_name:
        role_name = lambda_function_name
        logger.info(f"Using lambda function name as role name: {role_name}")
    else:
        # Fallback to the old naming pattern if lambda_function_name is not provided
        # Create a base role name without the operation_id
        base_role_name = (
            f"{resource_prefix}_{pipeline_name}_{node_id}_lambda_execution_role"
        )

        # If we have an operation_id, we need to ensure we don't exceed the 64-character limit
        if operation_id:
            # Calculate how much space we have left for the operation_id
            # We need to account for the underscore that will be added before the operation_id
            max_base_length = (
                63 - len(operation_id) - 1
            )  # 63 to leave room for the underscore

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
    max_retries = 5  # Increased from 3 to 5
    retry_delay = 3  # Increased from 2 to 3 seconds

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
            logger.info(f"Role {role_name} does not exist, creating new role")

        # Create the role with retries
        logger.info(f"Creating new role: {role_name}")
        for attempt in range(max_retries):
            try:
                response = iam.create_role(
                    RoleName=role_name,
                    AssumeRolePolicyDocument=json.dumps(assume_role_policy_document),
                )

                role_arn = response["Role"]["Arn"]
                logger.info(f"Role created with ARN: {role_arn}")

                # Wait for role to be available with increased delay and max attempts
                waiter = iam.get_waiter("role_exists")
                waiter.wait(
                    RoleName=role_name, WaiterConfig={"Delay": 2, "MaxAttempts": 15}
                )
                logger.info(f"Role {role_name} is now available")

                # Attach the basic execution policy
                logger.info(f"Attaching AWSLambdaBasicExecutionRole to {role_name}")
                iam.attach_role_policy(
                    RoleName=role_name,
                    PolicyArn="arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
                )

                # For embedding_store utility node, also attach VPC access policy and OpenSearch permissions
                if node_id == "embedding_store":
                    logger.info(
                        f"Attaching AWSLambdaVPCAccessExecutionRole to {role_name} for embedding_store"
                    )
                    iam.attach_role_policy(
                        RoleName=role_name,
                        PolicyArn="arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole",
                    )

                    # Add managed OpenSearch permissions
                    opensearch_policy = {
                        "Version": "2012-10-17",
                        "Statement": [
                            {
                                "Effect": "Allow",
                                "Action": [
                                    "es:ESHttpGet",
                                    "es:ESHttpPut",
                                    "es:ESHttpPost",
                                    "es:ESHttpHead",
                                    "es:ESHttpDelete",
                                ],
                                "Resource": "*",
                            }
                        ],
                    }

                    logger.info(
                        f"Adding OpenSearch permissions to {role_name} for embedding_store"
                    )
                    iam.put_role_policy(
                        RoleName=role_name,
                        PolicyName="OpenSearchAccess",
                        PolicyDocument=json.dumps(opensearch_policy),
                    )

                # Create and attach our custom execution policy
                logger.info(
                    f"Creating and attaching custom execution policy for {role_name}"
                )
                try:
                    create_lambda_execution_policy(role_name, yaml_data)
                    logger.info(
                        f"Custom execution policy created and attached successfully for {role_name}"
                    )
                except Exception as policy_error:
                    logger.error(
                        f"Error creating/attaching custom policy: {str(policy_error)}"
                    )
                    raise

                logger.info(
                    f"Role {role_name} created successfully with ARN: {role_arn}"
                )

                # Add a small delay after role creation to allow for propagation
                time.sleep(2)

                # Verify attached policies
                attached_policies = iam.list_attached_role_policies(RoleName=role_name)
                logger.info(f"Attached policies for {role_name}: {attached_policies}")

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
                # More aggressive exponential backoff
                backoff_time = retry_delay * (2**attempt)
                logger.info(f"Waiting {backoff_time} seconds before retry")
                time.sleep(backoff_time)

    except Exception as e:
        logger.error(f"Error creating role: {str(e)}")
        logger.error(f"Exception type: {type(e).__name__}")
        logger.error(f"Exception traceback: {traceback.format_exc()}")
        raise


def create_service_roles_from_yaml(
    pipeline_name: str, node_id: str, yaml_data: Dict[str, Any]
) -> Dict[str, str]:
    """
    Create service roles defined in the YAML file.

    Args:
        pipeline_name: Name of the pipeline
        node_id: ID of the node
        yaml_data: YAML data containing service role definitions

    Returns:
        Dictionary mapping role names to role ARNs
    """
    logger.info(f"Creating service roles for node {node_id} from YAML")

    service_roles = {}

    # Check if the YAML has service_roles section
    if (
        "node" in yaml_data
        and "integration" in yaml_data["node"]
        and "config" in yaml_data["node"]["integration"]
        and "service_roles" in yaml_data["node"]["integration"]["config"]
    ):
        service_roles_config = yaml_data["node"]["integration"]["config"][
            "service_roles"
        ]

        for role_config in service_roles_config:
            try:
                # Get the role name
                role_name = role_config.get("name")
                if not role_name:
                    logger.warning(
                        f"No name defined for role in node {node_id}, skipping"
                    )
                    continue

                # Get the service principal
                service_principal = role_config.get("service")
                if not service_principal:
                    logger.warning(
                        f"No service principal defined for role {role_name}, skipping"
                    )
                    continue

                # Get the policy statements
                policy_statements = []
                for policy in role_config.get("policies", []):
                    policy_statements.extend(policy.get("statements", []))

                if not policy_statements:
                    logger.warning(
                        f"No policy statements defined for role {role_name}, using default"
                    )
                    policy_statements = [
                        {
                            "Effect": "Allow",
                            "Action": ["s3:GetObject", "s3:PutObject", "s3:ListBucket"],
                            "Resource": ["*"],
                        }
                    ]

                # Create a unique role name
                sanitized_pipeline_name = sanitize_role_name(pipeline_name)
                sanitized_role_name = (
                    f"{resource_prefix}_{sanitized_pipeline_name}_{node_id}_{role_name}"
                )

                # Create the role
                iam_client = boto3.client("iam")

                # Check if role exists
                try:
                    iam_client.get_role(RoleName=sanitized_role_name)
                    logger.info(
                        f"Found existing role {sanitized_role_name}, deleting it"
                    )
                    delete_role(sanitized_role_name)
                    wait_for_role_deletion(sanitized_role_name)
                except iam_client.exceptions.NoSuchEntityException:
                    pass

                # Create the trust policy
                trust_policy = {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Effect": "Allow",
                            "Principal": {"Service": service_principal},
                            "Action": "sts:AssumeRole",
                        }
                    ],
                }

                # Create the role
                response = iam_client.create_role(
                    RoleName=sanitized_role_name,
                    AssumeRolePolicyDocument=json.dumps(trust_policy),
                    Description=f"Service role for {node_id} in pipeline {pipeline_name}",
                )

                role_arn = response["Role"]["Arn"]
                logger.info(
                    f"Created service role {sanitized_role_name} with ARN: {role_arn}"
                )

                # Create the policy document
                policy_document = {
                    "Version": "2012-10-17",
                    "Statement": policy_statements,
                }

                # Attach the policy
                policy_name = f"{sanitized_role_name}_policy"

                # Process the policy document to replace any environment variables
                policy_document_str = json.dumps(policy_document)
                try:
                    policy_document_str = process_policy_template(policy_document_str)
                    processed_policy_document = json.loads(policy_document_str)

                    # Log the final processed policy document
                    logger.info(
                        f"Final processed policy document for {role_name}: {json.dumps(processed_policy_document)}"
                    )

                    iam_client.put_role_policy(
                        RoleName=sanitized_role_name,
                        PolicyName=policy_name,
                        PolicyDocument=json.dumps(processed_policy_document),
                    )
                except Exception as process_err:
                    logger.error(
                        f"Error processing policy document for {role_name}: {process_err}"
                    )
                    # If there's an error processing the policy, try with a fallback approach
                    # Replace any remaining ${VAR} with "*" to avoid MalformedPolicyDocument errors
                    policy_document_str = re.sub(
                        r"\${[^}]+}", '"*"', policy_document_str
                    )
                    logger.info(
                        f"Using fallback policy document with wildcards for {role_name}: {policy_document_str}"
                    )

                    iam_client.put_role_policy(
                        RoleName=sanitized_role_name,
                        PolicyName=policy_name,
                        PolicyDocument=policy_document_str,
                    )

                logger.info(
                    f"Attached policy {policy_name} to role {sanitized_role_name}"
                )

                # Add the role to the result
                service_roles[role_name] = role_arn

            except Exception as e:
                logger.error(f"Failed to create service role {role_name}: {e}")
                logger.error(traceback.format_exc())

    return service_roles


def get_events_role_arn(pipeline_name: str) -> str:
    """Get or create an IAM role for EventBridge to invoke Step Functions."""
    iam_client = boto3.client("iam")
    # Sanitize the pipeline name and construct the role name with proper length limits
    sanitized_pipeline_name = sanitize_role_name(pipeline_name)
    base_role_name = f"{resource_prefix}_{sanitized_pipeline_name}_trigger_role"
    role_name = sanitize_role_name(base_role_name)
    try:
        response = iam_client.get_role(RoleName=role_name)
        return response["Role"]["Arn"]
    except iam_client.exceptions.NoSuchEntityException:
        # Create the role
        trust_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"Service": "events.amazonaws.com"},
                    "Action": "sts:AssumeRole",
                }
            ],
        }

        response = iam_client.create_role(
            RoleName=role_name, AssumeRolePolicyDocument=json.dumps(trust_policy)
        )

        # Attach policy to allow invoking Step Functions
        policy_document = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": ["states:StartExecution"],
                    "Resource": ["*"],  # Could be more restrictive
                }
            ],
        }

        # Ensure the policy document is standardized
        policy_document = standardize_policy_document(policy_document)

        iam_client.put_role_policy(
            RoleName=role_name,
            PolicyName=f"{role_name}Policy",
            PolicyDocument=json.dumps(policy_document),
        )

        return response["Role"]["Arn"]


def create_service_role(
    pipeline_name: str,
    node_id: str,
    service_principal: str,
    policy_statements: List[Dict[str, Any]],
    role_name_suffix: str = "service_role",
) -> str:
    """
    Create a service role for AWS services like Transcribe, MediaConvert, etc.

    Args:
        pipeline_name: Name of the pipeline
        node_id: ID of the node
        service_principal: AWS service principal (e.g., "transcribe.amazonaws.com")
        policy_statements: List of policy statements for the role
        role_name_suffix: Suffix to add to the role name

    Returns:
        ARN of the created role
    """
    iam_client = boto3.client("iam")

    # Create a base role name
    base_role_name = f"{resource_prefix}_{pipeline_name}_{node_id}_{role_name_suffix}"
    role_name = sanitize_role_name(base_role_name)

    # Ensure the final role name is within the 64-character limit
    if len(role_name) > 64:
        role_name = role_name[:64]

    # Create trust relationship policy
    trust_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"Service": service_principal},
                "Action": "sts:AssumeRole",
            }
        ],
    }

    try:
        # Check if role exists
        try:
            iam_client.get_role(RoleName=role_name)
            logger.info(f"Found existing service role {role_name}, deleting it")
            delete_role(role_name)
            wait_for_role_deletion(role_name)
        except iam_client.exceptions.NoSuchEntityException:
            logger.info(f"Service role {role_name} does not exist, creating new role")

        # Create the IAM role
        logger.info(f"Creating new service role: {role_name}")
        response = iam_client.create_role(
            RoleName=role_name, AssumeRolePolicyDocument=json.dumps(trust_policy)
        )

        role_arn = response["Role"]["Arn"]
        logger.info(f"Service role created with ARN: {role_arn}")

        # Wait for role to be available
        waiter = iam_client.get_waiter("role_exists")
        waiter.wait(RoleName=role_name, WaiterConfig={"Delay": 2, "MaxAttempts": 15})
        logger.info(f"Service role {role_name} is now available")

        # Create and attach inline policy with the provided statements
        if policy_statements:
            # Standardize and deduplicate policy statements
            standardized_statements = []
            for statement in policy_statements:
                standardized_statements.append(standardize_policy_statement(statement))

            deduplicated_statements = deduplicate_policy_statements(
                standardized_statements
            )

            policy_document = {
                "Version": "2012-10-17",
                "Statement": deduplicated_statements,
            }

            policy_name = f"{role_name}Policy"

            # Process the policy document to replace any remaining environment variables
            policy_document_str = json.dumps(policy_document)
            try:
                policy_document_str = process_policy_template(policy_document_str)
                processed_policy_document = json.loads(policy_document_str)

                # Log the final processed policy document
                logger.info(
                    f"Final processed policy document: {json.dumps(processed_policy_document)}"
                )

                iam_client.put_role_policy(
                    RoleName=role_name,
                    PolicyName=policy_name,
                    PolicyDocument=json.dumps(processed_policy_document),
                )
            except Exception as process_err:
                logger.error(f"Error processing policy document: {process_err}")
                # If there's an error processing the policy, try with a fallback approach
                # Replace any remaining ${VAR} with "*" to avoid MalformedPolicyDocument errors
                policy_document_str = re.sub(r"\${[^}]+}", '"*"', policy_document_str)
                logger.info(
                    f"Using fallback policy document with wildcards: {policy_document_str}"
                )

                iam_client.put_role_policy(
                    RoleName=role_name,
                    PolicyName=policy_name,
                    PolicyDocument=policy_document_str,
                )

            logger.info(f"Attached policy {policy_name} to service role {role_name}")

        # Add a small delay after role creation to allow for propagation
        time.sleep(2)

        return role_arn

    except Exception as e:
        logger.error(f"Error creating service role: {str(e)}")
        logger.error(f"Exception type: {type(e).__name__}")
        logger.error(f"Exception traceback: {traceback.format_exc()}")
        raise
