from typing import List

from aws_cdk import CfnOutput, Duration
from aws_cdk import aws_cloudwatch as cloudwatch
from constructs import Construct


class CloudWatchDashboard(Construct):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        dashboard_name: str = "MediaLake-Monitoring-Dashboard",
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Create CloudWatch Dashboard
        self.dashboard = cloudwatch.Dashboard(
            self, "Dashboard", dashboard_name=dashboard_name
        )

        # Export the dashboard ARN and name
        CfnOutput(
            self,
            "DashboardArn",
            value=self.dashboard.dashboard_arn,
            description="ARN of the CloudWatch Dashboard",
        )

        CfnOutput(
            self,
            "DashboardName",
            value=self.dashboard.dashboard_name,
            description="Name of the CloudWatch Dashboard",
        )

    def create_opensearch_metric(
        self,
        metric_name: str,
        label: str,
        unit: str,
        domain_name: str,
        period: Duration = Duration.minutes(5),
        statistic: str = "Average",
    ) -> cloudwatch.Metric:
        """Create an OpenSearch metric.

        Args:
            metric_name: The name of the metric
            label: Human-readable label for the metric
            unit: The unit of measurement
            domain_name: The OpenSearch domain name
            period: The period for the metric (default: 5 minutes)
            statistic: The statistic to use (default: Average)

        Returns:
            A CloudWatch metric for OpenSearch
        """
        return cloudwatch.Metric(
            namespace="AWS/ES",
            metric_name=metric_name,
            dimensions={"DomainName": domain_name},
            period=period,
            statistic=statistic,
            label=label,
            unit=self._get_cloudwatch_unit(unit),
        )

    def create_dynamodb_metric(
        self,
        metric_name: str,
        label: str,
        unit: str,
        table_name: str,
        period: Duration = Duration.minutes(5),
        statistic: str = "Sum",
    ) -> cloudwatch.Metric:
        """Create a DynamoDB metric.

        Args:
            metric_name: The name of the metric
            label: Human-readable label for the metric
            unit: The unit of measurement
            table_name: The DynamoDB table name
            period: The period for the metric (default: 5 minutes)
            statistic: The statistic to use (default: Sum)

        Returns:
            A CloudWatch metric for DynamoDB
        """
        return cloudwatch.Metric(
            namespace="AWS/DynamoDB",
            metric_name=metric_name,
            dimensions={"TableName": table_name},
            period=period,
            statistic=statistic,
            label=label,
            unit=self._get_cloudwatch_unit(unit),
        )

    def create_lambda_metric(
        self,
        metric_name: str,
        label: str,
        unit: str,
        function_name: str,
        period: Duration = Duration.minutes(5),
        statistic: str = "Sum",
    ) -> cloudwatch.Metric:
        """Create a Lambda metric.

        Args:
            metric_name: The name of the metric
            label: Human-readable label for the metric
            unit: The unit of measurement
            function_name: The Lambda function name
            period: The period for the metric (default: 5 minutes)
            statistic: The statistic to use (default: Sum)

        Returns:
            A CloudWatch metric for Lambda
        """
        return cloudwatch.Metric(
            namespace="AWS/Lambda",
            metric_name=metric_name,
            dimensions={"FunctionName": function_name},
            period=period,
            statistic=statistic,
            label=label,
            unit=self._get_cloudwatch_unit(unit),
        )

    def add_graph_widget(
        self,
        title: str,
        left_metrics: List[cloudwatch.Metric] = None,
        right_metrics: List[cloudwatch.Metric] = None,
        width: int = 12,
        height: int = 6,
    ) -> None:
        """Add a graph widget to the dashboard.

        Args:
            title: The title of the widget
            left_metrics: Metrics to display on the left Y-axis
            right_metrics: Metrics to display on the right Y-axis
            width: The width of the widget (default: 12)
            height: The height of the widget (default: 6)
        """
        self.dashboard.add_widgets(
            cloudwatch.GraphWidget(
                title=title,
                left=left_metrics or [],
                right=right_metrics or [],
                width=width,
                height=height,
            )
        )

    def add_log_widget(
        self,
        title: str,
        log_group_names: List[str],
        query_string: str,
        width: int = 24,
        height: int = 6,
    ) -> None:
        """Add a log query widget to the dashboard.

        Args:
            title: The title of the widget
            log_group_names: List of log group names to query
            query_string: The query string to execute
            width: The width of the widget (default: 24)
            height: The height of the widget (default: 6)
        """
        self.dashboard.add_widgets(
            cloudwatch.LogQueryWidget(
                title=title,
                log_group_names=log_group_names,
                query_string=query_string,
                width=width,
                height=height,
            )
        )

    def add_alarm_widget(
        self,
        title: str,
        alarms: List[cloudwatch.Alarm],
        width: int = 24,
        height: int = 6,
    ) -> None:
        """Add an alarm status widget to the dashboard.

        Args:
            title: The title of the widget
            alarms: List of CloudWatch alarms to display
            width: The width of the widget (default: 24)
            height: The height of the widget (default: 6)
        """
        self.dashboard.add_widgets(
            cloudwatch.AlarmStatusWidget(
                title=title,
                alarms=alarms,
                width=width,
                height=height,
            )
        )

    def _get_cloudwatch_unit(self, unit: str) -> cloudwatch.Unit:
        """Convert a string unit to a CloudWatch Unit.

        Args:
            unit: The unit as a string (e.g., 'Count', 'Bytes', 'Percent')

        Returns:
            The corresponding CloudWatch Unit
        """
        try:
            return getattr(cloudwatch.Unit, unit.upper())
        except AttributeError:
            # Default to None if the unit doesn't exist
            return cloudwatch.Unit.NONE
