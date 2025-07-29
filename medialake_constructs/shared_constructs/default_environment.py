from dataclasses import dataclass
from datetime import datetime

from aws_cdk import CustomResource, RemovalPolicy
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import custom_resources as cr
from constructs import Construct

from config import config
from medialake_constructs.shared_constructs.lambda_base import Lambda, LambdaConfig


@dataclass
class DefaultEnvironmentProps:
    """Properties for the DefaultEnvironment construct."""

    environments_table: dynamodb.TableV2


class DefaultEnvironment(Construct):
    """
    A construct that creates a default environment entry in the environments table
    during CloudFormation deployment.
    """

    def __init__(
        self,
        scope: Construct,
        id: str,
        props: DefaultEnvironmentProps,
    ) -> None:
        super().__init__(scope, id)

        # Create the Lambda function that will add the default environment
        default_env_lambda = Lambda(
            self,
            "DefaultEnvironmentLambda",
            config=LambdaConfig(
                name=f"{config.resource_prefix}-default-environment",
                entry="lambdas/custom_resources/default_environment",
                environment_variables={
                    "ENVIRONMENTS_TABLE": props.environments_table.table_name,
                    "METRICS_NAMESPACE": config.resource_prefix,
                },
            ),
        )

        # Grant the Lambda function write permissions to the environments table
        props.environments_table.grant_read_write_data(default_env_lambda.function)

        # Create a custom resource provider using the Lambda function
        default_env_provider = cr.Provider(
            self,
            "DefaultEnvironmentProvider",
            on_event_handler=default_env_lambda.function,
        )

        # Create the custom resource
        default_env_resource = CustomResource(
            self,
            "DefaultEnvironmentResource",
            service_token=default_env_provider.service_token,
            removal_policy=RemovalPolicy.RETAIN,
            properties={
                # Add a timestamp to ensure the resource is updated on each deployment
                "UpdateTimestamp": datetime.now().isoformat(),
            },
        )

        # Ensure the custom resource depends on the environments table
        default_env_resource.node.add_dependency(props.environments_table)
