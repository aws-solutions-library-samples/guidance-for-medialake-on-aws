from dataclasses import dataclass

from aws_cdk import CustomResource, RemovalPolicy, Stack
from aws_cdk import aws_iam as iam
from aws_cdk import custom_resources as cr
from constructs import Construct

from medialake_constructs.shared_constructs.lambda_base import Lambda, LambdaConfig


@dataclass
class PreDeployCleanUpStackProps:
    # No properties needed as this stack is independent
    pass


class PreDeployCleanUpStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        props: PreDeployCleanUpStackProps = None,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Create Lambda function for resource cleanup
        self._clean_up_lambda = Lambda(
            self,
            "MediaLakePreDeployCleanUp",
            config=LambdaConfig(
                name="MediaLakePreDeployCleanUp",
                timeout_minutes=15,
                entry="lambdas/back_end/pre_deploy_cleanup",
                environment_variables={},
            ),
        )

        # Add permissions for resource types
        self._add_permissions()

        # Create custom resource provider
        provider = cr.Provider(
            self,
            "PreDeployCleanUpProvider",
            on_event_handler=self._clean_up_lambda.function,
        )

        # Create custom resource
        self.resource = CustomResource(
            self,
            "PreDeployCleanUpResource",
            service_token=provider.service_token,
            properties={
                "Version": "1.0.0",
            },
            removal_policy=RemovalPolicy.DESTROY,
        )

    def _add_permissions(self):
        # Add permissions for CloudWatch logs
        self._clean_up_lambda.lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "logs:DescribeLogGroups",
                    "logs:ListTagsLogGroup",
                    "logs:DeleteLogGroup",
                ],
                resources=[
                    f"arn:aws:logs:{Stack.of(self).region}:{Stack.of(self).account}:log-group:*"
                ],
            )
        )

        # Add permissions for EventBridge pipes
        self._clean_up_lambda.lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "pipes:DeletePipe",
                    "pipes:DescribePipe",
                    "pipes:ListPipes",
                    "pipes:StopPipe",
                ],
                resources=[
                    f"arn:aws:pipes:{Stack.of(self).region}:{Stack.of(self).account}:pipe/*"
                ],
            )
        )

        # Add permissions for IAM roles
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

        # Add permissions for Lambda functions
        self._clean_up_lambda.lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "lambda:ListFunctions",
                    "lambda:DeleteFunction",
                    "lambda:ListEventSourceMappings",
                    "lambda:DeleteEventSourceMapping",
                ],
                resources=["*"],
            )
        )

        # Add permissions for SQS queues
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
