from aws_lambda_powertools import Logger, Tracer, Metrics
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.utilities.data_classes import event_source
from aws_lambda_powertools.metrics import MetricUnit
from boto3.dynamodb.conditions import Attr
import boto3
import os
from typing import Dict, List
import json
from botocore.exceptions import ClientError

# Initialize Power Tools
logger = Logger(service="provisioned-resource-cleanup")
tracer = Tracer(service="provisioned-resource-cleanup")
metrics = Metrics(namespace="ProvisionedResourceCleanup")

# Initialize AWS clients with X-Ray tracing
session = boto3.Session()
dynamodb = session.resource("dynamodb")
sts = session.client("sts")


@tracer.capture_method
def get_aws_account_id() -> str:
    """Get current AWS account ID."""
    return sts.get_caller_identity()["Account"]


@tracer.capture_method
def parse_arn(arn: str) -> Dict:
    """Parse an ARN into its components."""
    parts = arn.split(":")
    service = parts[2]
    region = parts[3]
    account = parts[4]
    resource_type = parts[5].split("/")[0] if "/" in parts[5] else parts[5]
    resource_id = "/".join(parts[5].split("/")[1:]) if "/" in parts[5] else ""

    return {
        "service": service,
        "region": region,
        "account": account,
        "resource_type": resource_type,
        "resource_id": resource_id,
    }


@tracer.capture_method
def delete_resource(arn: str) -> bool:
    """Delete a resource based on its ARN."""
    try:
        arn_parts = parse_arn(arn)
        service = arn_parts["service"]

        # Get the appropriate client for the service
        client = session.client(service, region_name=arn_parts["region"])

        # Handle different resource types
        if service == "s3":
            client.delete_bucket(Bucket=arn_parts["resource_id"])
        elif service == "dynamodb":
            client.delete_table(TableName=arn_parts["resource_id"])
        # Add more service-specific deletion logic as needed

        logger.info(f"Successfully deleted resource: {arn}")
        metrics.add_metric(
            name="ResourceDeletionSuccess", unit=MetricUnit.Count, value=1
        )
        return True

    except ClientError as e:
        logger.error(f"Failed to delete resource {arn}: {str(e)}")
        metrics.add_metric(
            name="ResourceDeletionFailure", unit=MetricUnit.Count, value=1
        )
        return False


@tracer.capture_method
def get_resources_to_delete() -> List[str]:
    """Retrieve resources to delete from DynamoDB."""
    table = dynamodb.Table(os.environ["RESOURCE_TABLE"])

    try:
        response = table.scan(FilterExpression=Attr("status").eq("PENDING_DELETION"))
        return [item["resourceArn"] for item in response.get("Items", [])]
    except ClientError as e:
        logger.error(f"Failed to scan DynamoDB table: {str(e)}")
        raise


@logger.inject_lambda_context(log_event=True)
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: Dict, context: LambdaContext) -> Dict:
    """
    Main Lambda handler for resource cleanup.

    Args:
        event: Lambda event
        context: Lambda context

    Returns:
        Dict containing execution results
    """
    try:
        # Get account ID for cross-account validation
        account_id = get_aws_account_id()

        # Get resources to delete
        resources = get_resources_to_delete()
        logger.info(f"Found {len(resources)} resources to delete")

        results = {"successful_deletions": [], "failed_deletions": []}

        # Process each resource
        for arn in resources:
            try:
                # Validate resource belongs to current account
                arn_parts = parse_arn(arn)
                if arn_parts["account"] != account_id:
                    logger.warning(
                        f"Skipping resource {arn} - belongs to different account"
                    )
                    results["failed_deletions"].append(
                        {"arn": arn, "reason": "Resource belongs to different account"}
                    )
                    continue

                # Delete the resource
                if delete_resource(arn):
                    results["successful_deletions"].append(arn)
                else:
                    results["failed_deletions"].append(
                        {"arn": arn, "reason": "Deletion failed"}
                    )

            except Exception as e:
                logger.error(f"Error processing resource {arn}: {str(e)}")
                results["failed_deletions"].append({"arn": arn, "reason": str(e)})

        # Log summary metrics
        metrics.add_metric(
            name="TotalResourcesProcessed", unit=MetricUnit.Count, value=len(resources)
        )

        return {"statusCode": 200, "body": json.dumps(results)}

    except Exception as e:
        logger.exception("Failed to process resource cleanup")
        raise
