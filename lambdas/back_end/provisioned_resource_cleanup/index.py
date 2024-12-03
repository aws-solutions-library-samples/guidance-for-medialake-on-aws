import os
from typing import Dict, Any, List
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.utilities.typing import LambdaContext
from pydantic import BaseModel, Field
from boto3.session import Session
from botocore.exceptions import ClientError

# Initialize AWS X-Ray tracer
tracer = Tracer()

# Initialize metrics with namespace and service name
metrics = Metrics(namespace="EventBridgeCleanup", service="EventManagement")

# Initialize logger with custom log levels based on environment variable
log_level = os.getenv("LOG_LEVEL", "WARNING").upper()
logger = Logger(
    service="EventManagement",
    level=log_level,
    json_serializer=lambda x: x,  # Use raw JSON output
)


class CleanupRequest(BaseModel):
    """Pydantic model for request validation"""

    dry_run: bool = Field(
        default=False, description="If true, only list rules without deleting"
    )
    region: str = Field(default="us-east-1", description="AWS region to scan")


class EventBridgeCleaner:
    def __init__(self, region: str):
        self.session = Session()
        self.client = self.session.client("events", region_name=region)

    @tracer.capture_method
    def list_event_buses(self) -> List[str]:
        """List all non-default event buses"""
        try:
            paginator = self.client.get_paginator("list_event_buses")
            event_buses = []

            for page in paginator.paginate():
                for bus in page["EventBuses"]:
                    if bus["Name"] != "default":
                        event_buses.append(bus["Name"])

            logger.debug(
                {
                    "message": "Retrieved event buses",
                    "count": len(event_buses),
                    "event_buses": event_buses,
                }
            )
            return event_buses
        except ClientError as e:
            logger.error({"message": "Failed to list event buses", "error": str(e)})
            raise

    @tracer.capture_method
    def list_rules_for_bus(self, bus_name: str) -> List[Dict[str, Any]]:
        """List all rules for a given event bus"""
        try:
            paginator = self.client.get_paginator("list_rules")
            rules = []

            for page in paginator.paginate(EventBusName=bus_name):
                rules.extend(page["Rules"])

            logger.debug(
                {
                    "message": "Retrieved rules for event bus",
                    "bus_name": bus_name,
                    "rule_count": len(rules),
                }
            )
            return rules
        except ClientError as e:
            logger.error(
                {
                    "message": "Failed to list rules for event bus",
                    "bus_name": bus_name,
                    "error": str(e),
                }
            )
            raise

    @tracer.capture_method
    def delete_rule(self, bus_name: str, rule_name: str) -> None:
        """Delete a specific rule from an event bus"""
        try:
            # First, remove all targets associated with the rule
            targets = self.client.list_targets_by_rule(
                Rule=rule_name, EventBusName=bus_name
            )["Targets"]

            if targets:
                target_ids = [target["Id"] for target in targets]
                self.client.remove_targets(
                    Rule=rule_name, EventBusName=bus_name, Ids=target_ids
                )

            # Then delete the rule
            self.client.delete_rule(Name=rule_name, EventBusName=bus_name)

            logger.info(
                {
                    "message": "Successfully deleted rule",
                    "bus_name": bus_name,
                    "rule_name": rule_name,
                    "target_count": len(targets),
                }
            )

            # Record metric for successful deletion
            metrics.add_metric(name="RulesDeleted", value=1, unit="Count")

        except ClientError as e:
            logger.error(
                {
                    "message": "Failed to delete rule",
                    "bus_name": bus_name,
                    "rule_name": rule_name,
                    "error": str(e),
                }
            )
            metrics.add_metric(name="RuleDeletionFailures", value=1, unit="Count")
            raise


@tracer.capture_lambda_handler
@metrics.log_metrics
@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    try:
    #     Parse and validate request
    #     if isinstance(event, dict) and "body" in event:
    #         body = event["body"]
    #     else:
    #         body = event
        

        # request = CleanupRequest(**body)

        # Initialize cleaner
        cleaner = EventBridgeCleaner(request.region)

        # Get all non-default event buses
        event_buses = cleaner.list_event_buses()

        deleted_rules_count = 0
        failed_deletions_count = 0

        # Process each event bus
        for bus_name in event_buses:
            rules = cleaner.list_rules_for_bus(bus_name)

            for rule in rules:
                if not request.dry_run:
                    try:
                        cleaner.delete_rule(bus_name, rule["Name"])
                        deleted_rules_count += 1
                    except ClientError:
                        failed_deletions_count += 1
                        continue

        # Add summary metrics
        metrics.add_metric(
            name="TotalRulesProcessed",
            value=deleted_rules_count + failed_deletions_count,
            unit="Count",
        )

        response = {
            "statusCode": 200,
            "body": {
                "message": "EventBridge cleanup completed",
                "dry_run": request.dry_run,
                "deleted_rules": deleted_rules_count,
                "failed_deletions": failed_deletions_count,
            },
        }

        logger.info(
            {
                "message": "Lambda execution completed successfully",
                "details": response["body"],
            }
        )

        return response

    except Exception as e:
        logger.error({"message": "Lambda execution failed", "error": str(e)})

        return {
            "statusCode": 500,
            "body": {"message": "Internal server error", "error": str(e)},
        }
