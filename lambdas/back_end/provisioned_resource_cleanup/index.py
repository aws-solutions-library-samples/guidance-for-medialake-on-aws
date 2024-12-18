import boto3
import cfnresponse
import logging
from botocore.exceptions import ClientError
from aws_lambda_powertools import Logger, Tracer
import os

# Initialize AWS Lambda Powertools
logger = Logger()
tracer = Tracer()

# Initialize AWS clients
dynamodb = boto3.resource("dynamodb")
lambda_client = boto3.client("lambda")
iam = boto3.client("iam")
s3 = boto3.client("s3")
sqs = boto3.client("sqs")


def delete_lambda_function(function_arn: str):
    """Delete Lambda function and its event source mappings"""
    try:
        # Delete event source mappings first
        try:
            mappings = lambda_client.list_event_source_mappings(
                FunctionName=function_arn
            )
            for mapping in mappings.get("EventSourceMappings", []):
                try:
                    lambda_client.delete_event_source_mapping(UUID=mapping["UUID"])
                    logger.info(f"Deleted event source mapping {mapping['UUID']}")
                except ClientError as e:
                    if e.response["Error"]["Code"] != "ResourceNotFoundException":
                        raise
        except ClientError as e:
            if e.response["Error"]["Code"] != "ResourceNotFoundException":
                raise

        # Delete the function
        lambda_client.delete_function(FunctionName=function_arn.split(":")[-1])
        logger.info(f"Deleted Lambda function {function_arn}")
    except ClientError as e:
        if e.response["Error"]["Code"] != "ResourceNotFoundException":
            raise
        logger.warning(f"Lambda function {function_arn} already deleted")


def delete_iam_role(role_arn: str):
    """Delete IAM role and its policies"""
    try:
        role_name = role_arn.split("/")[-1]

        # Detach managed policies
        attached_policies = iam.list_attached_role_policies(RoleName=role_name)[
            "AttachedPolicies"
        ]
        for policy in attached_policies:
            iam.detach_role_policy(RoleName=role_name, PolicyArn=policy["PolicyArn"])
            logger.info(f"Detached policy {policy['PolicyArn']} from role {role_name}")

        # Delete inline policies
        inline_policies = iam.list_role_policies(RoleName=role_name)["PolicyNames"]
        for policy_name in inline_policies:
            iam.delete_role_policy(RoleName=role_name, PolicyName=policy_name)
            logger.info(f"Deleted inline policy {policy_name} from role {role_name}")

        # Delete the role
        iam.delete_role(RoleName=role_name)
        logger.info(f"Deleted IAM role {role_name}")
    except ClientError as e:
        if e.response["Error"]["Code"] != "NoSuchEntity":
            raise
        logger.warning(f"IAM role {role_name} already deleted")


@tracer.capture_lambda_handler
def lambda_handler(event, context):
    try:
        logger.info("Received event: %s", event)
        request_type = event["RequestType"]

        if request_type == "Delete":
            table_name = os.environ["CONNECTOR_TABLE"]
            table = dynamodb.Table(table_name)

            # Scan the table to get all connectors
            response = table.scan()
            items = response["Items"]

            while "LastEvaluatedKey" in response:
                response = table.scan(ExclusiveStartKey=response["LastEvaluatedKey"])
                items.extend(response["Items"])

            # Process each connector for cleanup
            for item in items:
                try:
                    logger.info("Cleaning up connector: %s", item["id"])

                    # Delete Lambda function
                    if "lambdaArn" in item:
                        delete_lambda_function(item["lambdaArn"])

                    # Delete IAM role
                    if "iamRoleArn" in item:
                        delete_iam_role(item["iamRoleArn"])

                    # Delete SQS queue
                    if "queueUrl" in item:
                        try:
                            sqs.delete_queue(QueueUrl=item["queueUrl"])
                            logger.info(f"Deleted SQS queue {item['queueUrl']}")
                        except ClientError as e:
                            if (
                                e.response["Error"]["Code"]
                                != "AWS.SimpleQueueService.NonExistentQueue"
                            ):
                                raise

                    # Remove S3 bucket notification
                    if "storageIdentifier" in item:
                        try:
                            s3.put_bucket_notification_configuration(
                                Bucket=item["storageIdentifier"],
                                NotificationConfiguration={},
                            )
                            logger.info(
                                f"Removed notifications from bucket {item['storageIdentifier']}"
                            )
                        except ClientError as e:
                            if e.response["Error"]["Code"] != "NoSuchBucket":
                                raise

                    # Delete the connector record
                    table.delete_item(Key={"id": item["id"]})
                    logger.info(f"Deleted connector record {item['id']}")

                except Exception as e:
                    logger.error(
                        "Error cleaning up connector %s: %s", item["id"], str(e)
                    )
                    continue

            logger.info("Cleanup completed successfully")
            cfnresponse.send(event, context, cfnresponse.SUCCESS, {})
        else:
            # For Create/Update events, just respond success
            cfnresponse.send(event, context, cfnresponse.SUCCESS, {})

    except Exception as e:
        logger.error("Error during cleanup: %s", str(e))
        cfnresponse.send(event, context, cfnresponse.FAILED, {})
