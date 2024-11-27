from aws_cdk import (
    Stack,
    Environment,
    aws_events as events,
    aws_dynamodb as dynamodb,
    aws_lambda as lambda_,
    aws_iam as iam,
    aws_events_targets as targets,
    aws_s3_notifications as s3n,
    aws_s3 as s3,
    aws_secretsmanager as secretsmanager,
)
from aws_cdk import aws_lambda_event_sources as eventsources
from constructs import Construct
from dataclasses import dataclass

# Local imports
from config import GLOBAL_PREFIX, generate_short_uid, config
from medialake_constructs.shared_constructs.s3bucket import S3Bucket, S3Config
from medialake_constructs.shared_constructs.eventbridge import EventBus, EventBusConfig
from medialake_constructs.vpc import CustomVpc, CustomVpcProps
from medialake_constructs.shared_constructs.opensearch_managed_cluster import (
    OpenSearchCluster,
    OpenSearchClusterProps,
)
from medialake_constructs.shared_constructs.opensearch_serverless import (
    OpenSearchServerlessConstruct,
    OpenSearchServerlessProps,
)
from medialake_constructs.shared_constructs.lambda_layers import (
    SearchLayer,
    PynamoDbLambdaLayer,
)
from medialake_constructs.shared_constructs.dynamodb import DynamoDB, DynamoDBProps
from medialake_constructs.shared_constructs.lambda_base import (
    Lambda,
    LambdaConfig,
)


@dataclass
class PipelinesExecutionsStackProps:
    # x_origin_verify_secret: secretsmanager.Secret
    test: str


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
                bus_name="medialake-pipelines-executions",
                log_all=True,
            ),
        )

        step_functions_rule = events.Rule(
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

        self._pipelnes_executions_table = DynamoDB(
            self,
            "PipelinesExecutionsTable",
            props=DynamoDBProps(
                name="medialake_pipelines_executions_table",
                partition_key_name="execution_id",
                partition_key_type=dynamodb.AttributeType.STRING,
                sort_key_name="event_start_time",
                sort_key_type=dynamodb.AttributeType.NUMBER,
            ),
        )

        self._pipeline_executions_event_processor = Lambda(
            self,
            "PipelinesExecutionsEventProcessor",
            config=LambdaConfig(
                name="pipelines-executions",
                timeout_minutes=15,
                entry="lambdas/back_end/pipelines_executions_event_processor",
                environment_variables={
                    "PIPELINES_EXECUTIONS_TABLE_NAME": self._pipelnes_executions_table.table_arn,
                },
            ),
        )

        self._pipelnes_executions_table.table.grant_full_access(
            self._pipeline_executions_event_processor.function
        )

        pipelines_executions_lambda_rule = events.Rule(
            self,
            "PipelinesExecutionsLambdaRule",
            rule_name="pipelines-executions-lambda-rule",
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

        # GET /api/pipelines/executions/
        self._get_pipelines_executions_lambda = Lambda(
            self,
            "GetPipelinesExecutionsHandler",
            config=LambdaConfig(
                name="getexecutions",
                entry="lambdas/api/pipelines/executions/get_executions",
                environment_variables={
                    # "X_ORIGIN_VERIFY_SECRET_ARN": props.x_origin_verify_secret.secret_arn,
                    "PIPELINES_EXECUTIONS_TABLE_NAME": self._pipelnes_executions_table.table_arn,
                },
            ),
        )

        self._pipelnes_executions_table.table.grant_full_access(
            self._get_pipelines_executions_lambda.function
        )

        # GET /api/pipelines/executions/{executionId}
        self._get_pipelines_executions_execution_id_lambda = Lambda(
            self,
            "GetPipelinesExecutionsExecutionIdHandler",
            config=LambdaConfig(
                name="geid",
                entry="lambdas/api/pipelines/executions/rp_executionId/get_execution",
                environment_variables={
                    # "X_ORIGIN_VERIFY_SECRET_ARN": props.x_origin_verify_secret.secret_arn,
                    "PIPELINES_EXECUTIONS_TABLE_NAME": self._pipelnes_executions_table.table_arn,
                },
            ),
        )

        self._pipelnes_executions_table.table.grant_full_access(
            self._get_pipelines_executions_lambda.function
        )
        # POST /api/pipelines/executions/{executionId}/retry/
        self._post_retry_pipelines_executions_lambda = Lambda(
            self,
            "PostPipelinesExecutionsRetryHandler",
            config=LambdaConfig(
                name="executionretry",
                entry="lambdas/api/pipelines/executions/rp_executionId/retry/post_retry",
                environment_variables={
                    # "X_ORIGIN_VERIFY_SECRET_ARN": props.x_origin_verify_secret.secret_arn,
                    "PIPELINES_EXECUTIONS_TABLE_NAME": self._pipelnes_executions_table.table_arn,
                },
            ),
        )

        self._pipelnes_executions_table.table.grant_read_data(
            self._post_retry_pipelines_executions_lambda.function
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
