import json
from typing import List

from aws_cdk import Stack
from aws_cdk import aws_lambda as lambda_
from constructs import Construct

from config import config
from medialake_constructs.cloudwatch_dashboard import CloudWatchDashboard


class MonitoringStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Load configuration
        resource_prefix = config.resource_prefix

        if not resource_prefix:
            raise ValueError("Resource prefix not found in config.json")

        # Create the CloudWatch Dashboard
        self.dashboard = CloudWatchDashboard(
            self,
            "LambdaMonitoringDashboard",
            dashboard_name=f"{resource_prefix}-Lambda-Monitoring",
        )

        # Get all Lambda functions with the resource prefix
        lambda_functions = self._get_lambda_functions_with_prefix(resource_prefix)

        if not lambda_functions:
            print(f"Warning: No Lambda functions found with prefix '{resource_prefix}'")
            return

        # Create Lambda metrics for each function
        for function_name in lambda_functions:
            # Create metrics for errors
            error_metric = self.dashboard.create_lambda_metric(
                metric_name="Errors",
                label=f"{function_name} Errors",
                unit="Count",
                function_name=function_name,
            )

            # Create metrics for throttles
            throttle_metric = self.dashboard.create_lambda_metric(
                metric_name="Throttles",
                label=f"{function_name} Throttles",
                unit="Count",
                function_name=function_name,
            )

            # Create metrics for duration
            duration_metric = self.dashboard.create_lambda_metric(
                metric_name="Duration",
                label=f"{function_name} Duration",
                unit="Milliseconds",
                function_name=function_name,
                statistic="Average",
            )

            # Create metrics for invocations
            invocation_metric = self.dashboard.create_lambda_metric(
                metric_name="Invocations",
                label=f"{function_name} Invocations",
                unit="Count",
                function_name=function_name,
            )

            # Add widgets for this Lambda function
            self.dashboard.add_graph_widget(
                title=f"{function_name} - Errors and Throttles",
                left_metrics=[error_metric],
                right_metrics=[throttle_metric],
                width=12,
            )

            self.dashboard.add_graph_widget(
                title=f"{function_name} - Duration and Invocations",
                left_metrics=[duration_metric],
                right_metrics=[invocation_metric],
                width=12,
            )

        # Add a summary widget showing all errors across functions
        if len(lambda_functions) > 1:
            all_error_metrics = [
                self.dashboard.create_lambda_metric(
                    metric_name="Errors",
                    label=f"{function_name} Errors",
                    unit="Count",
                    function_name=function_name,
                )
                for function_name in lambda_functions
            ]

            self.dashboard.add_graph_widget(
                title="All Lambda Functions - Errors",
                left_metrics=all_error_metrics,
                width=24,
            )

            # Add a summary widget for throttles
            all_throttle_metrics = [
                self.dashboard.create_lambda_metric(
                    metric_name="Throttles",
                    label=f"{function_name} Throttles",
                    unit="Count",
                    function_name=function_name,
                )
                for function_name in lambda_functions
            ]

            self.dashboard.add_graph_widget(
                title="All Lambda Functions - Throttles",
                left_metrics=all_throttle_metrics,
                width=24,
            )

    def _load_config(self, config_path: str) -> dict:
        """Load configuration from the specified JSON file."""
        try:
            with open(config_path, "r") as f:
                return json.load(f)
        except FileNotFoundError:
            raise FileNotFoundError(f"Config file not found at {config_path}")
        except json.JSONDecodeError:
            raise ValueError(f"Invalid JSON in config file {config_path}")

    def _get_lambda_functions_with_prefix(self, resource_prefix: str) -> List[str]:
        """
        Get all Lambda functions that start with the given resource prefix.

        In a real deployment, this would query AWS for existing functions.
        For CDK, we need to reference functions created in other stacks.
        """
        # Option 1: If Lambda functions are defined in other stacks and exported
        # We can use Fn.import_value to get them

        # Option 2: If we're deploying this stack after Lambda functions are created,
        # we can use a custom resource to query AWS for Lambda functions with the prefix

        # For this example, we'll use a simpler approach - looking for Lambda functions
        # defined in the same CDK app that have been passed to this stack

        # Get all Lambda functions from the stack's scope
        lambda_functions = []

        # Find all Lambda functions in the stack's scope
        for construct in self.node.scoped_children:
            if isinstance(
                construct, lambda_.Function
            ) and construct.function_name.startswith(resource_prefix):
                lambda_functions.append(construct.function_name)

        # If we couldn't find any in the current stack, we'll need to use cross-stack references
        # or a custom resource to query AWS
        if not lambda_functions:
            # For demonstration, we'll create a placeholder that would be replaced
            # with actual implementation based on your specific setup
            print(
                "No Lambda functions found in current stack. In a real implementation, "
                "you would query AWS or use cross-stack references."
            )

            # This is where you would implement the logic to get Lambda functions
            # from AWS or from other stacks

            # For now, we'll return a placeholder
            lambda_functions = [
                f"{resource_prefix}-function1",
                f"{resource_prefix}-function2",
            ]

        return lambda_functions
