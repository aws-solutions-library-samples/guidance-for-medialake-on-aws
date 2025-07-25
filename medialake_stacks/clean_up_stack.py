from dataclasses import dataclass

from aws_cdk import CustomResource, RemovalPolicy, Stack
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_events as events
from aws_cdk import aws_iam as iam
from aws_cdk import custom_resources as cr
from constructs import Construct

from medialake_constructs.shared_constructs.lambda_base import Lambda, LambdaConfig


@dataclass
class CleanupStackProps:
    pipelines_event_bus: events.EventBus
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
                # log_removal_policy=RemovalPolicy.RETAIN,  # Enable to debug
                environment_variables={
                    "CONNECTOR_TABLE": props.connector_table.table_name,
                    "PIPELINE_TABLE": props.pipeline_table.table_name,
                    "VECTOR_BUCKET_NAME": f"medialake-vectors-{Stack.of(self).region}-{Stack.of(self).node.try_get_context('environment') or 'dev'}",
                },
            ),
        )

        props.connector_table.grant_read_write_data(self._clean_up_lambda.function)
        props.pipeline_table.grant_read_write_data(self._clean_up_lambda.function)

        # Add EventBridge Pipes permissions
        # ListPipes requires * resource - AWS API limitation for list operations
        self._clean_up_lambda.lambda_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "pipes:ListPipes",
                ],
                resources=[
                    "*"
                ],  # Required by AWS API - cannot be scoped to specific pipes
            )
        )

        self._clean_up_lambda.lambda_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "pipes:DeletePipe",
                    "pipes:DescribePipe",
                    "pipes:StopPipe",
                    "pipes:UntagResource",
                    "pipes:ListTagsForResource",
                ],
                resources=[
                    f"arn:aws:pipes:{Stack.of(self).region}:{Stack.of(self).account}:pipe/*"
                ],
            )
        )

        # Ensure IAM permissions for role deletion are complete
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

        # ListEventSourceMappings requires * resource - AWS API limitation
        self._clean_up_lambda.lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "lambda:ListEventSourceMappings",
                ],
                resources=[
                    "*"
                ],  # Required by AWS API - cannot be scoped to specific resources
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
                    f"arn:aws:states:{Stack.of(self).region}:{Stack.of(self).account}:stateMachine:*"
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
                    "logs:DescribeLogGroups",
                    "logs:ListTagsLogGroup",
                    "logs:DeleteLogGroup",
                    "logs:PutRetentionPolicy",
                    "logs:DeleteRetentionPolicy",
                    "logs:TagLogGroup",
                    "logs:UntagLogGroup",
                ],
                resources=[
                    f"arn:aws:logs:{Stack.of(self).region}:{Stack.of(self).account}:log-group:*"
                ],
            )
        )

        # Add Secrets Manager permissions
        # ListSecrets requires * resource - AWS API limitation for list operations
        self._clean_up_lambda.lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "secretsmanager:ListSecrets",
                ],
                resources=[
                    "*"
                ],  # Required by AWS API - cannot be scoped to specific secrets
            )
        )

        self._clean_up_lambda.lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "secretsmanager:DeleteSecret",
                    "secretsmanager:DescribeSecret",
                ],
                resources=[
                    f"arn:aws:secretsmanager:{Stack.of(self).region}:{Stack.of(self).account}:secret:integration/*",
                    f"arn:aws:secretsmanager:{Stack.of(self).region}:{Stack.of(self).account}:secret:medialake/search/provider/*",
                ],
            )
        )

        # Add Step Functions permissions
        self._clean_up_lambda.lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "states:ListExecutions",
                    "states:StopExecution",
                ],
                resources=[
                    f"arn:aws:states:{Stack.of(self).region}:{Stack.of(self).account}:stateMachine:*",
                    f"arn:aws:states:{Stack.of(self).region}:{Stack.of(self).account}:execution:*",
                ],
            )
        )

        # Add S3 Vector Store permissions for cleanup - List operations require * resource
        self._clean_up_lambda.lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "s3vectors:ListVectorBuckets",
                    "s3vectors:ListIndexes",
                ],
                resources=[
                    "*"
                ],  # List operations require * resource per AWS API limitations
            )
        )

        # Add S3 Vector Store permissions for specific MediaLake resources
        self._clean_up_lambda.lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "s3vectors:GetVectorBucket",
                    "s3vectors:DeleteVectorBucket",
                    "s3vectors:GetIndex",
                    "s3vectors:DeleteIndex",
                ],
                resources=[
                    f"arn:aws:s3vectors:{Stack.of(self).region}:{Stack.of(self).account}:bucket/medialake-vectors-*",
                    f"arn:aws:s3vectors:{Stack.of(self).region}:{Stack.of(self).account}:bucket/medialake-vectors-*/index/*",
                ],
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
            removal_policy=RemovalPolicy.DESTROY,
        )
