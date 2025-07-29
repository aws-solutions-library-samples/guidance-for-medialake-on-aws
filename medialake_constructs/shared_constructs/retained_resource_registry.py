from typing import Any, Dict, Optional

from aws_cdk import Stack
from aws_cdk import aws_iam as iam
from aws_cdk import custom_resources as cr
from constructs import Construct

from config import config


class RetainedResourceRegistry(Construct):
    """
    A construct that maintains a registry of retained resources using SSM Parameters.

    This registry tracks resources that are retained when a stack is destroyed
    and provides mechanisms to reconnect to these resources in subsequent deployments.
    """

    def __init__(self, scope: Construct, id: str) -> None:
        super().__init__(scope, id)
        self.stack = Stack.of(self)
        self.resources = {}

    def register_resource(
        self,
        resource_type: str,
        resource_id: str,
        resource_arn: str,
        additional_data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Register a resource to be tracked.

        Args:
            resource_type: The type of resource (e.g., 'dynamodb-table', 's3-bucket')
            resource_id: The ID of the resource
            resource_arn: The ARN of the resource
            additional_data: Additional data to store with the resource
        """
        if config.environment != "prod":
            # Only track resources in production
            return

        # Create a unique key for the resource
        key = f"{resource_type}-{resource_id}"

        # Store resource information
        self.resources[key] = {
            "type": resource_type,
            "id": resource_id,
            "arn": resource_arn,
            "data": additional_data or {},
        }

        # Use a custom resource to store resource information
        # This avoids issues with unresolved tokens in parameter names

        # Create a unique ID for the custom resource that doesn't include tokens
        import uuid

        unique_id = str(uuid.uuid4())

        # Create a custom resource that will store the resource information in SSM parameters
        # during deployment time, when all tokens are resolved
        cr.AwsCustomResource(
            self,
            f"RetainedResource-{unique_id}",
            on_create=cr.AwsSdkCall(
                service="SSM",
                action="putParameter",
                parameters={
                    "Name": f"/medialake/{config.environment}/retained-resources/{resource_type}/{resource_id}/arn",
                    "Value": resource_arn,
                    "Type": "String",
                    "Overwrite": True,
                    "Description": f"ARN of retained {resource_type} {resource_id}",
                },
                physical_resource_id=cr.PhysicalResourceId.of(
                    f"resource-arn-{unique_id}"
                ),
            ),
            on_update=cr.AwsSdkCall(
                service="SSM",
                action="putParameter",
                parameters={
                    "Name": f"/medialake/{config.environment}/retained-resources/{resource_type}/{resource_id}/arn",
                    "Value": resource_arn,
                    "Type": "String",
                    "Overwrite": True,
                    "Description": f"ARN of retained {resource_type} {resource_id}",
                },
                physical_resource_id=cr.PhysicalResourceId.of(
                    f"{resource_type}-{resource_id}-arn"
                ),
            ),
            policy=cr.AwsCustomResourcePolicy.from_statements(
                [
                    iam.PolicyStatement(
                        actions=["ssm:PutParameter"],
                        resources=["*"],
                    ),
                ]
            ),
        )

        # Store additional data in SSM parameters
        if additional_data:
            for data_key, value in additional_data.items():
                if isinstance(value, str):
                    # Create a unique ID for each additional data item
                    data_unique_id = str(uuid.uuid4())
                    cr.AwsCustomResource(
                        self,
                        f"RetainedResource-{data_unique_id}",
                        on_create=cr.AwsSdkCall(
                            service="SSM",
                            action="putParameter",
                            parameters={
                                "Name": f"/medialake/{config.environment}/retained-resources/{resource_type}/{resource_id}/{data_key}",
                                "Value": value,
                                "Type": "String",
                                "Overwrite": True,
                                "Description": f"{data_key} of retained {resource_type} {resource_id}",
                            },
                            physical_resource_id=cr.PhysicalResourceId.of(
                                f"resource-{data_key}-{data_unique_id}"
                            ),
                        ),
                        on_update=cr.AwsSdkCall(
                            service="SSM",
                            action="putParameter",
                            parameters={
                                "Name": f"/medialake/{config.environment}/retained-resources/{resource_type}/{resource_id}/{data_key}",
                                "Value": value,
                                "Type": "String",
                                "Overwrite": True,
                                "Description": f"{data_key} of retained {resource_type} {resource_id}",
                            },
                            physical_resource_id=cr.PhysicalResourceId.of(
                                f"resource-{data_key}-{data_unique_id}"
                            ),
                        ),
                        policy=cr.AwsCustomResourcePolicy.from_statements(
                            [
                                iam.PolicyStatement(
                                    actions=["ssm:PutParameter"],
                                    resources=["*"],
                                ),
                            ]
                        ),
                    )

    @staticmethod
    def get_resource_parameter_name(
        resource_type: str, resource_id: str, attribute: str = "arn"
    ) -> str:
        """
        Get the SSM parameter name for a resource attribute.

        Args:
            resource_type: The type of resource
            resource_id: The ID of the resource
            attribute: The attribute to retrieve (default: 'arn')

        Returns:
            The SSM parameter name
        """
        return f"/medialake/{config.environment}/retained-resources/{resource_type}/{resource_id}/{attribute}"
