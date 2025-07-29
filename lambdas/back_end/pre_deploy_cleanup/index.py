import concurrent.futures
import time
from typing import Dict, List

import boto3
import cfnresponse
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.middleware_factory import lambda_handler_decorator
from botocore.exceptions import ClientError

# Initialize logger and tracer
logger = Logger()
tracer = Tracer()

# Initialize AWS clients
logs_client = boto3.client("logs")
# Create a dedicated logs client for us-east-1 region
logs_client_us_east_1 = boto3.client("logs", region_name="us-east-1")
pipes_client = boto3.client("pipes")
iam_client = boto3.client("iam")
lambda_client = boto3.client("lambda")
sqs_client = boto3.client("sqs")

# Resource prefixes to match
RESOURCE_PREFIXES = ["medialake", "mlake"]


def resource_matches_prefix(name: str) -> bool:
    """Check if a resource name matches any of the prefixes."""
    name_lower = name.lower()
    return any(prefix in name_lower for prefix in RESOURCE_PREFIXES)


@tracer.capture_method
def delete_log_groups_in_region(client, region_name: str) -> List[str]:
    """Delete CloudWatch log groups with matching prefixes in the specified region."""
    deleted_resources = []

    try:
        paginator = client.get_paginator("describe_log_groups")
        for page in paginator.paginate():
            for log_group in page["logGroups"]:
                log_group_name = log_group["logGroupName"]

                if resource_matches_prefix(log_group_name):
                    try:
                        client.delete_log_group(logGroupName=log_group_name)
                        logger.info(
                            f"Deleted CloudWatch log group: {log_group_name} in region {region_name}"
                        )
                        deleted_resources.append(f"{region_name}:{log_group_name}")
                    except ClientError as e:
                        logger.error(
                            f"Error deleting log group {log_group_name} in region {region_name}: {str(e)}"
                        )
    except Exception as e:
        logger.error(
            f"Error listing CloudWatch log groups in region {region_name}: {str(e)}"
        )

    return deleted_resources


@tracer.capture_method
def delete_cloudwatch_log_groups() -> List[str]:
    """Delete CloudWatch log groups with matching prefixes in both default region and us-east-1."""
    deleted_resources = []

    # Get current region for logging purposes
    current_region = boto3.session.Session().region_name

    # Delete log groups in current region
    current_region_resources = delete_log_groups_in_region(logs_client, current_region)
    deleted_resources.extend(current_region_resources)

    # Delete log groups in us-east-1 if not already in that region
    if current_region != "us-east-1":
        us_east_1_resources = delete_log_groups_in_region(
            logs_client_us_east_1, "us-east-1"
        )
        deleted_resources.extend(us_east_1_resources)

    return deleted_resources


@tracer.capture_method
def delete_eventbridge_pipes() -> List[str]:
    """Delete EventBridge pipes with matching prefixes."""
    deleted_resources = []

    try:
        paginator = pipes_client.get_paginator("list_pipes")
        for page in paginator.paginate():
            for pipe in page.get("Pipes", []):
                pipe_name = pipe["Name"]
                pipe_arn = pipe["Arn"]

                if resource_matches_prefix(pipe_name):
                    try:
                        # Check pipe state and stop if running
                        pipe_info = pipes_client.describe_pipe(Name=pipe_name)
                        if pipe_info.get("CurrentState") == "RUNNING":
                            pipes_client.stop_pipe(Name=pipe_name)
                            logger.info(f"Stopped EventBridge pipe: {pipe_name}")

                            # Wait for pipe to stop
                            max_retries = 10
                            for i in range(max_retries):
                                time.sleep(2)
                                pipe_info = pipes_client.describe_pipe(Name=pipe_name)
                                if pipe_info.get("CurrentState") != "RUNNING":
                                    break

                        # Delete the pipe
                        pipes_client.delete_pipe(Name=pipe_name)
                        logger.info(f"Deleted EventBridge pipe: {pipe_name}")
                        deleted_resources.append(pipe_arn)
                    except ClientError as e:
                        logger.error(f"Error deleting pipe {pipe_name}: {str(e)}")
    except Exception as e:
        logger.error(f"Error listing EventBridge pipes: {str(e)}")

    return deleted_resources


@tracer.capture_method
def delete_iam_roles() -> List[str]:
    """Delete IAM roles with matching prefixes."""
    deleted_resources = []

    try:
        paginator = iam_client.get_paginator("list_roles")
        for page in paginator.paginate():
            for role in page["Roles"]:
                role_name = role["RoleName"]
                role_arn = role["Arn"]

                if resource_matches_prefix(role_name):
                    try:
                        # Detach managed policies
                        attached_policies = iam_client.list_attached_role_policies(
                            RoleName=role_name
                        )["AttachedPolicies"]
                        for policy in attached_policies:
                            iam_client.detach_role_policy(
                                RoleName=role_name, PolicyArn=policy["PolicyArn"]
                            )
                            logger.info(
                                f"Detached policy {policy['PolicyArn']} from role {role_name}"
                            )

                        # Delete inline policies
                        inline_policies = iam_client.list_role_policies(
                            RoleName=role_name
                        )["PolicyNames"]
                        for policy_name in inline_policies:
                            iam_client.delete_role_policy(
                                RoleName=role_name, PolicyName=policy_name
                            )
                            logger.info(
                                f"Deleted inline policy {policy_name} from role {role_name}"
                            )

                        # Delete the role
                        iam_client.delete_role(RoleName=role_name)
                        logger.info(f"Deleted IAM role: {role_name}")
                        deleted_resources.append(role_arn)
                    except ClientError as e:
                        logger.error(f"Error deleting role {role_name}: {str(e)}")
    except Exception as e:
        logger.error(f"Error listing IAM roles: {str(e)}")

    return deleted_resources


@tracer.capture_method
def delete_lambda_functions() -> List[str]:
    """Delete Lambda functions with matching prefixes."""
    deleted_resources = []

    try:
        paginator = lambda_client.get_paginator("list_functions")
        for page in paginator.paginate():
            for function in page["Functions"]:
                function_name = function["FunctionName"]
                function_arn = function["FunctionArn"]

                if resource_matches_prefix(function_name):
                    try:
                        # Delete event source mappings
                        mappings = lambda_client.list_event_source_mappings(
                            FunctionName=function_name
                        )
                        for mapping in mappings.get("EventSourceMappings", []):
                            try:
                                lambda_client.delete_event_source_mapping(
                                    UUID=mapping["UUID"]
                                )
                                logger.info(
                                    f"Deleted event source mapping {mapping['UUID']}"
                                )
                            except ClientError as e:
                                if (
                                    e.response["Error"]["Code"]
                                    != "ResourceNotFoundException"
                                ):
                                    logger.error(
                                        f"Error deleting event source mapping {mapping['UUID']}: {str(e)}"
                                    )

                        # Delete the function
                        lambda_client.delete_function(FunctionName=function_name)
                        logger.info(f"Deleted Lambda function: {function_name}")
                        deleted_resources.append(function_arn)
                    except ClientError as e:
                        logger.error(
                            f"Error deleting function {function_name}: {str(e)}"
                        )
    except Exception as e:
        logger.error(f"Error listing Lambda functions: {str(e)}")

    return deleted_resources


@tracer.capture_method
def delete_sqs_queues() -> List[str]:
    """Delete SQS queues with matching prefixes."""
    deleted_resources = []

    try:
        response = sqs_client.list_queues()
        queues = response.get("QueueUrls", [])

        for queue_url in queues:
            # Extract queue name from URL
            queue_name = queue_url.split("/")[-1]

            if resource_matches_prefix(queue_name):
                try:
                    sqs_client.delete_queue(QueueUrl=queue_url)
                    logger.info(f"Deleted SQS queue: {queue_url}")
                    deleted_resources.append(queue_url)
                except ClientError as e:
                    logger.error(f"Error deleting queue {queue_url}: {str(e)}")
    except Exception as e:
        logger.error(f"Error listing SQS queues: {str(e)}")

    return deleted_resources


@tracer.capture_method
def delete_resources_in_parallel() -> Dict[str, List[str]]:
    """Delete all resources in parallel."""
    results = {}

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        # Submit all deletion tasks
        future_to_resource = {
            executor.submit(delete_cloudwatch_log_groups): "cloudwatch_logs",
            executor.submit(delete_eventbridge_pipes): "eventbridge_pipes",
            executor.submit(delete_iam_roles): "iam_roles",
            executor.submit(delete_lambda_functions): "lambda_functions",
            executor.submit(delete_sqs_queues): "sqs_queues",
        }

        # Process results as they complete
        for future in concurrent.futures.as_completed(future_to_resource):
            resource_type = future_to_resource[future]
            try:
                deleted_resources = future.result()
                results[resource_type] = deleted_resources
                logger.info(f"Deleted {len(deleted_resources)} {resource_type}")
            except Exception as e:
                logger.error(f"Error deleting {resource_type}: {str(e)}")
                results[resource_type] = []

    return results


@lambda_handler_decorator
def lambda_handler(event):
    """Lambda handler function."""
    logger.info(f"Received event: {event}")

    # Access the context object from the decorator
    import inspect

    frame = inspect.currentframe()
    ctx = None
    try:
        ctx = frame.f_back.f_locals.get("ctx")
    finally:
        del frame  # Avoid reference cycles

    request_type = event["RequestType"]
    response_data = {}

    try:
        if request_type in ["Create", "Delete"]:
            logger.info(f"Processing {request_type} request")

            # Delete resources
            results = delete_resources_in_parallel()

            # Count deleted resources
            total_deleted = sum(len(resources) for resources in results.values())
            logger.info(f"Total resources deleted: {total_deleted}")

            # Add results to response data
            for resource_type, deleted_resources in results.items():
                response_data[resource_type] = len(deleted_resources)

            response_data["total_deleted"] = total_deleted

            cfnresponse.send(event, ctx, cfnresponse.SUCCESS, response_data)
        elif request_type == "Update":
            # Skip resource deletion on update
            logger.info("Skipping resource deletion on update")
            cfnresponse.send(event, ctx, cfnresponse.SUCCESS, response_data)
        else:
            logger.error(f"Unknown request type: {request_type}")
            cfnresponse.send(event, ctx, cfnresponse.FAILED, response_data)
    except Exception as e:
        logger.error(f"Error processing request: {str(e)}", exc_info=True)
        cfnresponse.send(event, ctx, cfnresponse.FAILED, {"Error": str(e)})

    return response_data
