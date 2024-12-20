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

        self._clean_up_lambda = Lambda(
            self,
            "MediaLakeCleanUp",
            config=LambdaConfig(
                name="MediaLakeCleanUp",
                timeout_minutes=15,
                entry="lambdas/back_end/provisioned_resource_cleanup",
                environment_variables={
                    "CONNECTOR_TABLE": props.connector_table.table_name,
                    "PIPELINE_TABLE": props.pipeline_table.table_name,
                },
            ),
        )

        props.connector_table.grant_read_write_data(self._clean_up_lambda.function)
        props.pipeline_table.grant_read_write_data(self._clean_up_lambda.function)

        self._clean_up_lambda.lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "lambda:ListEventSourceMappings",
                    "lambda:DeleteEventSourceMapping",
                ],
                resources=[
                    f"arn:aws:lambda:{Stack.of(self).region}:{Stack.of(self).account}:event-source-mapping:*"
                ],
            )
        )

        self._clean_up_lambda.lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["lambda:DeleteFunction"],
                resources=[
                    f"arn:aws:lambda:{Stack.of(self).region}:{Stack.of(self).account}:function:*"
                ],  # TODO add resource prefix i.e. medialake
            )
        )

        self._clean_up_lambda.lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["states:DeleteStateMachine"],
                resources=[
                    f"arn:aws:lambda:{Stack.of(self).region}:{Stack.of(self).account}:stateMachine:*"
                ],  # TODO add resource prefix i.e. medialake
            )
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

        self._clean_up_lambda.lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "sqs:DeleteQueue",
                    "sqs:GetQueueAttributes",
                    "sqs:ListQueues",
                    "sqs:ListQueueTags",
                ],
                resources=[f"arn:aws:sqs:*:{Stack.of(self).account}:*"],
            )
        )

        self._clean_up_lambda.lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "s3:GetBucketNotification",
                    "s3:PutBucketNotification",
                ],
                resources=["arn:aws:s3:::*"],
            )
        )

        self._clean_up_lambda.lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "iam:GetRole",
                    "iam:ListRoles",
                    "iam:DeleteRole",
                    "iam:ListRolePolicies",
                    "iam:ListAttachedRolePolicies",
                    "iam:DetachRolePolicy",
                    "iam:DeleteRolePolicy",
                ],
                resources=[f"arn:aws:iam::{Stack.of(self).account}:role/*"],
            )
        )

        self.provider = cr.Provider(
            self, "CleanupProvider", on_event_handler=self._clean_up_lambda.function
        )

        self.resource = CustomResource(
            self,
            "CleanupResource",
            service_token=self.provider.service_token,
            properties={
                "Version": "1.0.0",
            },
            removal_policy=RemovalPolicy.RETAIN,
        )
