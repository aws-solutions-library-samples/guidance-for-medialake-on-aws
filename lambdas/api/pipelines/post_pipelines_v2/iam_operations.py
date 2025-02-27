import json
import os
import re
import time
from typing import Dict, Any
import boto3

from aws_lambda_powertools import Logger

from config import (
    MEDIA_ASSETS_BUCKET_NAME,
    MEDIA_ASSETS_BUCKET_NAME_KMS_KEY,
    MEDIALAKE_ASSET_TABLE,
)

# Initialize logger
logger = Logger()


def create_iam_lambda_s3_dynamo_rw_policy():
    """Create a policy document for Lambda to access S3 and DynamoDB."""
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
                "Resource": [f"{MEDIALAKE_ASSET_TABLE}"],
            },
            {
                "Effect": "Allow",
                "Action": ["s3:GetObject", "s3:PutObject", "s3:PutObjectAcl"],
                "Resource": [
                    f"arn:aws:s3:::{MEDIA_ASSETS_BUCKET_NAME}/*",
                    f"arn:aws:s3:::{MEDIA_ASSETS_BUCKET_NAME}",
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
                    MEDIA_ASSETS_BUCKET_NAME_KMS_KEY,
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
            role_arn = response["Role"]["Arn"]

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

                # Wait for role to be available with increased delay and max attempts
                waiter = iam.get_waiter("role_exists")
                waiter.wait(
                    RoleName=role_name, WaiterConfig={"Delay": 2, "MaxAttempts": 15}
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

                # Add a small delay after role creation to allow for propagation
                time.sleep(2)

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
        raise


def get_events_role_arn() -> str:
    """Get or create an IAM role for EventBridge to invoke Step Functions."""
    iam_client = boto3.client("iam")
    role_name = "MediaLakeEventBridgeToStepFunctionsRole"

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

        iam_client.put_role_policy(
            RoleName=role_name,
            PolicyName=f"{role_name}Policy",
            PolicyDocument=json.dumps(policy_document),
        )

        return response["Role"]["Arn"]
