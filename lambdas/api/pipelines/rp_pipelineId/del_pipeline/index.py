import os
import json
import boto3
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.event_handler import (
    APIGatewayRestResolver,
    Response,
    content_types,
)
from botocore.exceptions import ClientError

tracer = Tracer()
logger = Logger()
app = APIGatewayRestResolver()

# Initialize AWS clients
dynamodb = boto3.resource("dynamodb")
lambda_client = boto3.client("lambda")
iam_client = boto3.client("iam")
sqs_client = boto3.client("sqs")
sfn_client = boto3.client("stepfunctions")
events_client = boto3.client("events")


def delete_lambda_function(function_arn: str):
    """Delete Lambda function"""
    try:
        # Delete any event source mappings first
        try:
            mappings = lambda_client.list_event_source_mappings(
                FunctionName=function_arn
            )
            for mapping in mappings.get("EventSourceMappings", []):
                try:
                    lambda_client.delete_event_source_mapping(UUID=mapping["UUID"])
                    logger.info(
                        f"Successfully deleted event source mapping {mapping['UUID']}"
                    )
                except ClientError as e:
                    if e.response["Error"]["Code"] != "ResourceNotFoundException":
                        raise
                    logger.warning(
                        f"Event source mapping {mapping['UUID']} already deleted"
                    )
        except ClientError as e:
            if e.response["Error"]["Code"] != "ResourceNotFoundException":
                raise
            logger.warning("No event source mappings found")

        # Delete the function
        lambda_client.delete_function(FunctionName=function_arn)
    except ClientError as e:
        if e.response["Error"]["Code"] != "ResourceNotFoundException":
            raise
        logger.warning(f"Lambda function {function_arn} already deleted")


def delete_state_machine(state_machine_arn: str):
    """Delete Step Functions state machine"""
    try:
        sfn_client.delete_state_machine(stateMachineArn=state_machine_arn)
        logger.info(
            f"Successfully deleted Step Functions state machine {state_machine_arn}"
        )
    except ClientError as e:
        if e.response["Error"]["Code"] != "ResourceNotFoundException":
            raise
        logger.warning(f"State machine {state_machine_arn} already deleted")


def delete_sqs_queue(queue_url: str):
    """Delete SQS queue"""
    try:
        sqs_client.delete_queue(QueueUrl=queue_url)
        logger.info(f"Successfully deleted SQS queue {queue_url}")
    except ClientError as e:
        if e.response["Error"]["Code"] != "AWS.SimpleQueueService.NonExistentQueue":
            raise
        logger.warning(f"Queue {queue_url} already deleted")


def delete_eventbridge_rule(rule_arn: str, event_bus_name: str):
    """Delete EventBridge rule"""
    try:
        # Extract rule name from ARN: arn:aws:events:region:account:rule/rulename
        rule_name = rule_arn.split("/")[-1]

        try:
            # List and remove all targets first
            targets = events_client.list_targets_by_rule(
                Rule=rule_name, EventBusName=event_bus_name
            )

            if targets.get("Targets"):
                target_ids = [target["Id"] for target in targets["Targets"]]
                events_client.remove_targets(
                    Rule=rule_name,
                    EventBusName=event_bus_name,
                    Ids=target_ids,
                    Force=True,
                )
                logger.info(f"Removed {len(target_ids)} targets from rule {rule_name}")

        except ClientError as e:
            if e.response["Error"]["Code"] != "ResourceNotFoundException":
                logger.error(f"Error removing targets: {str(e)}")
                raise
            logger.warning(f"Rule {rule_name} not found when removing targets")

        try:
            # Delete the rule itself
            events_client.delete_rule(
                Name=rule_name, EventBusName=event_bus_name, Force=True
            )
            logger.info(f"Successfully deleted rule {rule_name}")

        except ClientError as e:
            if e.response["Error"]["Code"] != "ResourceNotFoundException":
                logger.error(f"Error deleting rule: {str(e)}")
                raise
            logger.warning(f"Rule {rule_name} not found when deleting")

    except Exception as e:
        if (
            isinstance(e, ClientError)
            and e.response["Error"]["Code"] == "ResourceNotFoundException"
        ):
            logger.warning(f"EventBridge rule {rule_arn} already deleted")
            return
        logger.error(f"Error deleting EventBridge rule {rule_arn}: {str(e)}")
        raise


def delete_iam_role(role_arn: str):
    """Delete IAM role and its attached policies"""
    try:
        role_name = role_arn.split("/")[-1]

        # Detach managed policies
        try:
            attached_policies = iam_client.list_attached_role_policies(
                RoleName=role_name
            )
            for policy in attached_policies.get("AttachedPolicies", []):
                try:
                    iam_client.detach_role_policy(
                        RoleName=role_name, PolicyArn=policy["PolicyArn"]
                    )
                    logger.info(
                        f"Successfully detached managed policy {policy['PolicyArn']} from role {role_name}"
                    )
                except ClientError as e:
                    if e.response["Error"]["Code"] != "NoSuchEntity":
                        raise
                    logger.warning(f"Policy {policy['PolicyArn']} already detached")
        except ClientError as e:
            if e.response["Error"]["Code"] != "NoSuchEntity":
                raise
            logger.warning(f"Role {role_name} not found when listing policies")

        # Delete inline policies
        try:
            inline_policies = iam_client.list_role_policies(RoleName=role_name)
            for policy_name in inline_policies.get("PolicyNames", []):
                try:
                    iam_client.delete_role_policy(
                        RoleName=role_name, PolicyName=policy_name
                    )
                    logger.info(
                        f"Successfully deleted inline policy {policy_name} from role {role_name}"
                    )
                except ClientError as e:
                    if e.response["Error"]["Code"] != "NoSuchEntity":
                        raise
                    logger.warning(f"Inline policy {policy_name} already deleted")
        except ClientError as e:
            if e.response["Error"]["Code"] != "NoSuchEntity":
                raise
            logger.warning(f"Role {role_name} not found when listing inline policies")

        # Delete the role
        iam_client.delete_role(RoleName=role_name)
        logger.info(f"Successfully deleted IAM role {role_arn}")
    except ClientError as e:
        if e.response["Error"]["Code"] != "NoSuchEntity":
            raise
        logger.warning(f"IAM role {role_arn} already deleted")


@app.delete("/pipelines/<pipeline_id>")
def delete_pipeline(pipeline_id: str):
    try:
        # Get pipeline details from DynamoDB
        table_name = os.environ.get("PIPELINES_TABLE_NAME")
        if not table_name:
            raise ValueError("PIPELINES_TABLE_NAME environment variable not set")

        table = dynamodb.Table(table_name)
        response = table.get_item(Key={"id": pipeline_id})

        if "Item" not in response:
            return Response(
                status_code=404,
                content_type=content_types.APPLICATION_JSON,
                body={
                    "status": "404",
                    "message": f"Pipeline with ID {pipeline_id} not found",
                    "data": {},
                },
            )

        pipeline = response["Item"]

        # Delete all resources, continuing even if some fail
        deletion_errors = []

        # Delete Lambda functions
        if "triggerLambdaArn" in pipeline:
            try:
                delete_lambda_function(pipeline["triggerLambdaArn"])
            except Exception as e:
                if (
                    not isinstance(e, ClientError)
                    or e.response["Error"]["Code"] != "ResourceNotFoundException"
                ):
                    deletion_errors.append(f"Failed to delete trigger Lambda: {str(e)}")

        # Delete Step Functions state machine
        if "stateMachineArn" in pipeline:
            try:
                delete_state_machine(pipeline["stateMachineArn"])
            except Exception as e:
                if (
                    not isinstance(e, ClientError)
                    or e.response["Error"]["Code"] != "ResourceNotFoundException"
                ):
                    deletion_errors.append(f"Failed to delete state machine: {str(e)}")

        # Delete SQS queue
        if "queueUrl" in pipeline:
            try:
                delete_sqs_queue(pipeline["queueUrl"])
            except Exception as e:
                if (
                    not isinstance(e, ClientError)
                    or e.response["Error"]["Code"]
                    != "AWS.SimpleQueueService.NonExistentQueue"
                ):
                    deletion_errors.append(f"Failed to delete SQS queue: {str(e)}")

        # Delete EventBridge rule
        if (
            "eventBridgeDetails" in pipeline
            and "eventBridgeRuleArn" in pipeline["eventBridgeDetails"]
        ):
            try:
                delete_eventbridge_rule(
                    pipeline["eventBridgeDetails"]["eventBridgeRuleArn"],
                    pipeline["eventBridgeDetails"].get("parentEventBusName", "default"),
                )
            except Exception as e:
                if (
                    not isinstance(e, ClientError)
                    or e.response["Error"]["Code"] != "ResourceNotFoundException"
                ):
                    deletion_errors.append(
                        f"Failed to delete EventBridge rule: {str(e)}"
                    )

        # Delete IAM role
        if "roleArn" in pipeline:
            try:
                delete_iam_role(pipeline["roleArn"])
            except Exception as e:
                if (
                    not isinstance(e, ClientError)
                    or e.response["Error"]["Code"] != "NoSuchEntity"
                ):
                    deletion_errors.append(f"Failed to delete IAM role: {str(e)}")

        # Delete pipeline record from DynamoDB
        try:
            table.delete_item(Key={"id": pipeline_id})
        except Exception as e:
            deletion_errors.append(f"Failed to delete DynamoDB record: {str(e)}")

        if deletion_errors:
            logger.warning(
                f"Pipeline deletion completed with errors: {deletion_errors}"
            )
            return Response(
                status_code=207,
                content_type=content_types.APPLICATION_JSON,
                body={
                    "status": "207",
                    "message": "Pipeline deleted with some errors",
                    "data": {"pipelineId": pipeline_id, "errors": deletion_errors},
                },
            )

        logger.info(f"Successfully deleted pipeline {pipeline_id}")
        return {
            "status": "200",
            "message": "Pipeline deleted successfully",
            "data": {"pipelineId": pipeline_id},
        }

    except Exception as e:
        logger.exception(f"Failed to delete pipeline: {str(e)}")
        return Response(
            status_code=500,
            content_type=content_types.APPLICATION_JSON,
            body={
                "status": "500",
                "message": f"Failed to delete pipeline: {str(e)}",
                "data": {},
            },
        )


@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_HTTP)
@tracer.capture_lambda_handler
def lambda_handler(event: dict, context: LambdaContext) -> dict:
    return app.resolve(event, context)
