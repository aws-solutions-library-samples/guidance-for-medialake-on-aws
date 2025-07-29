from dataclasses import dataclass

from aws_cdk import Stack
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_events as events
from aws_cdk import aws_events_targets as targets
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_secretsmanager as secretsmanager
from constructs import Construct

from config import config
from medialake_constructs.shared_constructs.dynamodb import DynamoDB, DynamoDBProps

# Local imports
from medialake_constructs.shared_constructs.eventbridge import EventBus, EventBusConfig
from medialake_constructs.shared_constructs.lambda_base import Lambda, LambdaConfig


@dataclass
class PipelinesExecutionsStackProps:
    x_origin_verify_secret: secretsmanager.Secret


class PipelinesExecutionsStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        props: PipelinesExecutionsStackProps,
        **kwargs,
    ):
        super().__init__(scope, construct_id, **kwargs)

        # Create Pipeline Executions EventBus
        self._pipelines_executions_event_bus = EventBus(
            self,
            "PipelineExecutionsEventBus",
            props=EventBusConfig(
                bus_name=f"{config.resource_prefix}-pipelines-executions",
                log_all=True,
            ),
        )

        _ = events.Rule(
            self,
            "StepFunctionsRule",
            rule_name="step-functions-events-rule",
            event_pattern=events.EventPattern(
                source=["aws.states"],
                detail_type=[
                    "Step Functions Execution Status Change",
                    "Step Functions State Machine Status Change",
                ],
            ),
            event_bus=events.EventBus.from_event_bus_name(
                self, "DefaultEventBus", event_bus_name="default"
            ),
            targets=[targets.EventBus(self._pipelines_executions_event_bus.event_bus)],
        )

        if config.db.use_existing_tables:
            self._pipelnes_executions_table = dynamodb.Table.from_table_arn(
                self,
                "ImportedPipelinesExecutionsTable",
                config.db.pipelines_executions_arn,
            )
        else:

            dynamodb_table = DynamoDB(
                self,
                "PipelinesExecutionsTable",
                props=DynamoDBProps(
                    name=f"{config.resource_prefix}-pipelines-executions-{config.environment}",
                    partition_key_name="execution_id",
                    partition_key_type=dynamodb.AttributeType.STRING,
                    sort_key_name="start_time",
                    sort_key_type=dynamodb.AttributeType.NUMBER,
                ),
            )
            self._pipelnes_executions_table = dynamodb_table.table

        self._pipeline_executions_event_processor = Lambda(
            self,
            "PipelinesExecutionsEventProcessor",
            config=LambdaConfig(
                name="pipelines_executions_event_processor",
                timeout_minutes=5,
                entry="lambdas/back_end/pipelines_executions_event_processor",
                environment_variables={
                    "PIPELINES_EXECUTIONS_TABLE_NAME": self._pipelnes_executions_table.table_arn,
                },
            ),
        )

        self._pipelnes_executions_table.grant_full_access(
            self._pipeline_executions_event_processor.function
        )

        _ = events.Rule(
            self,
            "PipelinesExecutionsLambdaRule",
            rule_name=f"{config.resource_prefix}-pipelines-executions-lambda-trigger-{config.environment}",
            event_pattern=events.EventPattern(
                source=["aws.states"],
                detail_type=[
                    "Step Functions Execution Status Change",
                    "Step Functions State Machine Status Change",
                ],
            ),
            event_bus=self._pipelines_executions_event_bus.event_bus,
            targets=[
                targets.LambdaFunction(
                    self._pipeline_executions_event_processor.function
                )
            ],
        )

        # GET /pipelines/executions/
        self._get_pipelines_executions_lambda = Lambda(
            self,
            "GetPipelinesExecutionsHandler",
            config=LambdaConfig(
                name="get_executions",
                entry="lambdas/api/pipelines/executions/get_executions",
                environment_variables={
                    # "X_ORIGIN_VERIFY_SECRET_ARN": props.x_origin_verify_secret.secret_arn,
                    "PIPELINES_EXECUTIONS_TABLE_NAME": self._pipelnes_executions_table.table_arn,
                },
            ),
        )

        self._pipelnes_executions_table.grant_full_access(
            self._get_pipelines_executions_lambda.function
        )

        # GET /api/pipelines/executions/{executionId}
        self._get_pipelines_executions_execution_id_lambda = Lambda(
            self,
            "GetPipelinesExecutionsExecutionIdHandler",
            config=LambdaConfig(
                name="get_executions_executionid",
                entry="lambdas/api/pipelines/executions/rp_executionId/get_execution",
                environment_variables={
                    # "X_ORIGIN_VERIFY_SECRET_ARN": props.x_origin_verify_secret.secret_arn,
                    "PIPELINES_EXECUTIONS_TABLE_NAME": self._pipelnes_executions_table.table_arn,
                },
            ),
        )

        self._pipelnes_executions_table.grant_full_access(
            self._get_pipelines_executions_lambda.function
        )
        # POST /api/pipelines/executions/{executionId}/retry/
        self._post_retry_pipelines_executions_lambda = Lambda(
            self,
            "PostPipelinesExecutionsRetryHandler",
            config=LambdaConfig(
                name="post_executionId_retry",
                entry="lambdas/api/pipelines/executions/rp_executionId/retry/post_retry",
                environment_variables={
                    # "X_ORIGIN_VERIFY_SECRET_ARN": props.x_origin_verify_secret.secret_arn,
                    "PIPELINES_EXECUTIONS_TABLE_NAME": self._pipelnes_executions_table.table_name,
                },
            ),
        )

        self._pipelnes_executions_table.grant_read_data(
            self._post_retry_pipelines_executions_lambda.function
        )

        # Grant Step Functions permissions for retry operations
        self._post_retry_pipelines_executions_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "states:DescribeExecution",
                    "states:RedriveExecution",
                    "states:StartExecution",
                ],
                resources=["*"],  # Allow access to all state machines and executions
            )
        )

    @property
    def pipelnes_executions_table(self) -> dynamodb.TableV2:
        return self._pipelnes_executions_table

    @property
    def pipelines_executions_event_bus(self) -> events.EventBus:
        return self._pipelines_executions_event_bus.event_bus

    @property
    def get_pipelines_executions_lambda(self) -> lambda_.IFunction:
        return self._get_pipelines_executions_lambda.function

    @property
    def post_retry_pipelines_executions_lambda(self) -> lambda_.IFunction:
        return self._post_retry_pipelines_executions_lambda.function
