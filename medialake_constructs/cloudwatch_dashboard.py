from aws_cdk import (
    aws_cloudwatch as cloudwatch,
    Duration,
    Stack,
    aws_cloudwatch_actions as cloudwatch_actions,
    aws_sns as sns,
    aws_sns_subscriptions as subscriptions,
    aws_iam as iam,
    CfnOutput,
)
from constructs import Construct
from typing import Optional


class CloudWatchDashboard(Construct):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        domain_name: str,
        table_name: str,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Create CloudWatch Dashboard
        dashboard = cloudwatch.Dashboard(
            self, "MediaLakeDashboard", dashboard_name="MediaLake-Monitoring-Dashboard"
        )

        # OpenSearch Metrics
        opensearch_metrics = [
            self._create_opensearch_metric(
                "FreeStorageSpace",
                "The amount of free storage space",
                "Bytes",
                domain_name,
            ),
            self._create_opensearch_metric(
                "CPUUtilization", "CPU utilization percentage", "Percent", domain_name
            ),
            self._create_opensearch_metric(
                "JVMMemoryPressure", "JVM memory pressure", "Percent", domain_name
            ),
            self._create_opensearch_metric(
                "ClusterStatus.green",
                "Cluster health status (green)",
                "Count",
                domain_name,
            ),
            self._create_opensearch_metric(
                "ClusterStatus.yellow",
                "Cluster health status (yellow)",
                "Count",
                domain_name,
            ),
            self._create_opensearch_metric(
                "ClusterStatus.red", "Cluster health status (red)", "Count", domain_name
            ),
        ]

        # DynamoDB Metrics
        dynamodb_metrics = [
            self._create_dynamodb_metric(
                "ConsumedReadCapacityUnits",
                "Read capacity units consumed",
                "Count",
                table_name,
            ),
            self._create_dynamodb_metric(
                "ConsumedWriteCapacityUnits",
                "Write capacity units consumed",
                "Count",
                table_name,
            ),
            self._create_dynamodb_metric(
                "ReadThrottleEvents", "Read throttle events", "Count", table_name
            ),
            self._create_dynamodb_metric(
                "WriteThrottleEvents", "Write throttle events", "Count", table_name
            ),
            self._create_dynamodb_metric(
                "SystemErrors", "System errors", "Count", table_name
            ),
            self._create_dynamodb_metric(
                "UserErrors", "User errors", "Count", table_name
            ),
        ]

        # Add widgets to dashboard
        dashboard.add_widgets(
            # OpenSearch Widgets
            cloudwatch.GraphWidget(
                title="OpenSearch - Storage and CPU",
                left=[opensearch_metrics[0]],  # FreeStorageSpace
                right=[opensearch_metrics[1]],  # CPUUtilization
                width=12,
            ),
            cloudwatch.GraphWidget(
                title="OpenSearch - Memory and Health",
                left=[opensearch_metrics[2]],  # JVMMemoryPressure
                right=[
                    opensearch_metrics[3],  # ClusterStatus.green
                    opensearch_metrics[4],  # ClusterStatus.yellow
                    opensearch_metrics[5],  # ClusterStatus.red
                ],
                width=12,
            ),
            # DynamoDB Widgets
            cloudwatch.GraphWidget(
                title="DynamoDB - Capacity Units",
                left=[dynamodb_metrics[0]],  # ConsumedReadCapacityUnits
                right=[dynamodb_metrics[1]],  # ConsumedWriteCapacityUnits
                width=12,
            ),
            cloudwatch.GraphWidget(
                title="DynamoDB - Throttling",
                left=[dynamodb_metrics[2]],  # ReadThrottleEvents
                right=[dynamodb_metrics[3]],  # WriteThrottleEvents
                width=12,
            ),
            cloudwatch.GraphWidget(
                title="DynamoDB - Errors",
                left=[dynamodb_metrics[4]],  # SystemErrors
                right=[dynamodb_metrics[5]],  # UserErrors
                width=12,
            ),
        )

    def _create_opensearch_metric(
        self,
        metric_name: str,
        label: str,
        unit: str,
        domain_name: str,
    ) -> cloudwatch.Metric:
        """Create an OpenSearch metric."""
        return cloudwatch.Metric(
            namespace="AWS/ES",
            metric_name=metric_name,
            dimensions={"DomainName": domain_name},
            period=Duration.minutes(5),
            statistic="Average",
            label=label,
            unit=cloudwatch.Unit.BYTES,
        )

    def _create_dynamodb_metric(
        self,
        metric_name: str,
        label: str,
        unit: str,
        table_name: str,
    ) -> cloudwatch.Metric:
        """Create a DynamoDB metric."""
        return cloudwatch.Metric(
            namespace="AWS/DynamoDB",
            metric_name=metric_name,
            dimensions={"TableName": table_name},
            period=Duration.minutes(5),
            statistic="Sum",
            label=label,
            unit=getattr(cloudwatch.Unit, unit).upper(),
        )
