from aws_cdk import Stack
from constructs import Construct
from medialake_constructs.cloudwatch_dashboard import CloudWatchDashboard
from config import config


class MediaLakeMonitoringStack(Stack):
    """
    Stack for MediaLake monitoring resources including CloudWatch dashboards.

    Creates and configures monitoring resources for the MediaLake application
    including CloudWatch dashboards for visualizing metrics from various services.

    Args:
        scope (Construct): CDK construct scope
        construct_id (str): Unique identifier for the stack
        domain_name (str): Name of the OpenSearch domain to monitor
        table_name (str): Name of the DynamoDB table to monitor
        **kwargs: Additional arguments passed to Stack
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        domain_name: str,
        table_name: str,
        **kwargs
    ):
        super().__init__(scope, construct_id, **kwargs)

        # Create CloudWatch Dashboard
        self._dashboard = CloudWatchDashboard(
            self,
            "MediaLakeMonitoring",
            domain_name=domain_name,
            table_name=table_name,
        )

    @property
    def dashboard(self) -> CloudWatchDashboard:
        """
        Returns the CloudWatch dashboard construct.

        Returns:
            CloudWatchDashboard: The configured CloudWatch dashboard
        """
        return self._dashboard
