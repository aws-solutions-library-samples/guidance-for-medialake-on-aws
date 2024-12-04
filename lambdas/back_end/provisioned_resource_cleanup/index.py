import os
from typing import Dict, Any, List
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.utilities.typing import LambdaContext
from boto3.session import Session
from botocore.exceptions import ClientError

tracer = Tracer()
metrics = Metrics(namespace="EventBridgeCleanup", service="EventManagement")
log_level = os.getenv("LOG_LEVEL", "WARNING").upper()
logger = Logger(
    service="EventManagement",
    level=log_level,
    json_serializer=lambda x: x,
)


class EventBridgeCleaner:
    def __init__(self, region: str):
        self.session = Session()
        self.client = self.session.client("events", region_name=region)

    @tracer.capture_method
    def list_event_buses(self) -> List[str]:
        """List all non-default event buses"""
        try:
            response = self.client.list_event_buses()
            event_buses = [
                bus["Name"]
                for bus in response["EventBuses"]
                if bus["Name"] != "default"
            ]

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
        try:
            targets = self.client.list_targets_by_rule(
                Rule=rule_name, EventBusName=bus_name
            )["Targets"]

            if targets:
                target_ids = [target["Id"] for target in targets]
                self.client.remove_targets(
                    Rule=rule_name, EventBusName=bus_name, Ids=target_ids
                )

            self.client.delete_rule(Name=rule_name, EventBusName=bus_name)

            logger.info(
                {
                    "message": "Successfully deleted rule",
                    "bus_name": bus_name,
                    "rule_name": rule_name,
                    "target_count": len(targets),
                }
            )

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
        if isinstance(event, dict) and "body" in event:
            request = event["body"]
        else:
            request = event

        dry_run = request.get("dry_run", False)
        region = request.get("region", "us-east-1")

        cleaner = EventBridgeCleaner(region)
        event_buses = cleaner.list_event_buses()

        deleted_rules_count = 0
        failed_deletions_count = 0

        for bus_name in event_buses:
            rules = cleaner.list_rules_for_bus(bus_name)

            for rule in rules:
                if not dry_run:
                    try:
                        cleaner.delete_rule(bus_name, rule["Name"])
                        deleted_rules_count += 1
                    except ClientError:
                        failed_deletions_count += 1
                        continue

        metrics.add_metric(
            name="TotalRulesProcessed",
            value=deleted_rules_count + failed_deletions_count,
            unit="Count",
        )

        response = {
            "statusCode": 200,
            "body": {
                "message": "EventBridge cleanup completed",
                "dry_run": dry_run,
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
