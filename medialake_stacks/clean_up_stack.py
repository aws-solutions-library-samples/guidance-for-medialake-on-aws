from dataclasses import dataclass
from constructs import Construct
from aws_cdk import (
    Stack,
    CustomResource,
    RemovalPolicy,
    aws_iam as iam,
    aws_events as events,
    aws_dynamodb as dynamodb,
    custom_resources as cr,
)
from medialake_constructs.shared_constructs.dynamodb import DynamoDB, DynamoDBProps
from medialake_constructs.shared_constructs.lambda_base import Lambda, LambdaConfig


@dataclass
class CleanupStackProps:
    ingest_event_bus: events.EventBus
    pipeline_table: dynamodb.TableV2
    connector_table: dynamodb.TableV2


class CleanupStack(Stack):
    def __init__(
        self, scope: Construct, construct_id: str, props: CleanupStackProps, **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self._resource_table = DynamoDB(
            self,
            "MediaLakeAssetResourcesTable",
            props=DynamoDBProps(
                name="medialake-provisioned-resources-table",
                partition_key_name="ARN",
                partition_key_type=dynamodb.AttributeType.STRING,
                sort_key_name="type",
                sort_key_type=dynamodb.AttributeType.STRING,
            ),
        )

        self._clean_up_lambda = Lambda(
            self,
            "MediaLakeProvisionedResourceCleanUpLambda",
            config=LambdaConfig(
                name="test",
                timeout_minutes=15,
                entry="lambdas/back_end/provisioned_resource_cleanup",
                environment_variables={
                    "CONNECTOR_TABLE": props.connector_table.table_name,
                    "PIPELINE_TABLE": props.pipeline_table.table_name,
                },
            ),
        )

        self._clean_up_lambda.lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "events:ListEventBuses",
                    "events:ListRules",
                    "events:ListTargetsByRule",
                    "events:RemoveTargets",
                    "events:DeleteRule",
                ],
                resources=["*"],
            )
        )

        self._resource_table.table.grant_read_write_data(self._clean_up_lambda.function)

        self.provider = cr.Provider(
            self, "CleanupProvider", on_event_handler=self._clean_up_lambda.function
        )

        self.resource = CustomResource(
            self,
            "CleanupResource",
            service_token=self.provider.service_token,
            properties={
                "TableName": self._resource_table.table_name,
                "Version": "1.0.0",
            },
            removal_policy=RemovalPolicy.RETAIN,
        )

    @property
    def resource_table(self) -> dynamodb.Table:
        return self._resource_table.table
