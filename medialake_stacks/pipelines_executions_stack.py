from dataclasses import dataclass

from aws_cdk import Duration, RemovalPolicy, Stack
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_events as events
from aws_cdk import aws_events_targets as targets
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_lambda_event_sources as lambda_event_sources
from aws_cdk import aws_secretsmanager as secretsmanager
from constructs import Construct

from config import config
from medialake_constructs.shared_constructs.dynamodb import DynamoDB, DynamoDBProps

# Local imports
from medialake_constructs.shared_constructs.eventbridge import EventBus, EventBusConfig
from medialake_constructs.shared_constructs.lambda_base import Lambda, LambdaConfig
from medialake_constructs.sqs import SQSConstruct, SQSProps


@dataclass
class PipelinesExecutionsStackProps:
    x_origin_verify_secret: secretsmanager.Secret
    asset_table: dynamodb.ITable
    pipelines_event_bus: events.IEventBus


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
                bus_name=f"{config.resource_prefix}-pipelines-executions-{config.environment}",
                log_all=True,
            ),
        )

        _ = events.Rule(
            self,
            "StepFunctionsRule",
            rule_name=f"{config.resource_prefix}-step-functions-events-rule-{config.environment}",
            event_pattern=events.EventPattern(
                source=["aws.states"],
                detail_type=[
                    "Step Functions Execution Status Change",
                    "Step Functions State Machine Status Change",
                ],
                detail={"stateMachineArn": [{"suffix": "_pipeline"}]},
            ),
            event_bus=events.EventBus.from_event_bus_name(
                self, "DefaultEventBus", event_bus_name="default"
            ),
            targets=[targets.EventBus(self._pipelines_executions_event_bus.event_bus)],
        )

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

        # ────────────────────────────────────────────────────────────────
        # Pipeline execution groups table
        #
        # Tracks batches of executions submitted together from the bin with
        # a shared group key so their output artifacts can be packaged into
        # a single downloadable zip when the last execution finishes.
        #
        # Item shapes (mirrors the upload-session store pattern):
        #   PK=GROUP#{groupId} SK=META           — counters + status + package config
        #   PK=GROUP#{groupId} SK=EXEC#{execId}  — one item per member execution
        #   PK=GROUP#{groupId} SK=COLLECTED#{assetId}#{repId}
        #                                        — one item per collected artifact,
        #                                          written by the Download
        #                                          Collector node
        #
        # The stream drives the group finalizer lambda, which claims the
        # OPEN → terminal transition (at-most-once) and kicks off packaging.
        #
        # executionId-index lets a pipeline node resolve its own group from the
        # Step Functions execution id the middleware threads through every step.
        # Only EXEC# items carry executionId, so the index is sparse and a hit
        # is unambiguous.
        # ────────────────────────────────────────────────────────────────
        groups_dynamodb_table = DynamoDB(
            self,
            "PipelineGroupsTable",
            props=DynamoDBProps(
                name=f"{config.resource_prefix}-pipelines-groups-{config.environment}",
                partition_key_name="PK",
                partition_key_type=dynamodb.AttributeType.STRING,
                sort_key_name="SK",
                sort_key_type=dynamodb.AttributeType.STRING,
                stream=dynamodb.StreamViewType.NEW_AND_OLD_IMAGES,
                ttl_attribute="ttl",
                global_secondary_indexes=[
                    dynamodb.GlobalSecondaryIndexPropsV2(
                        index_name="executionId-index",
                        partition_key=dynamodb.Attribute(
                            name="executionId",
                            type=dynamodb.AttributeType.STRING,
                        ),
                        projection_type=dynamodb.ProjectionType.INCLUDE,
                        non_key_attributes=[
                            "groupId",
                            "inventoryId",
                            "baselineRepIds",
                            "status",
                        ],
                    ),
                ],
            ),
        )
        self._pipeline_groups_table = groups_dynamodb_table.table

        self._pipeline_executions_event_processor = Lambda(
            self,
            "PipelinesExecutionsEventProcessor",
            config=LambdaConfig(
                name="pipelines_executions_event_processor",
                timeout_minutes=5,
                entry="lambdas/back_end/pipelines_executions_event_processor",
                environment_variables={
                    "PIPELINES_EXECUTIONS_TABLE_NAME": self._pipelnes_executions_table.table_arn,
                    "PIPELINE_GROUPS_TABLE_NAME": self._pipeline_groups_table.table_name,
                },
            ),
        )

        self._pipelnes_executions_table.grant_full_access(
            self._pipeline_executions_event_processor.function
        )

        self._pipeline_groups_table.grant_read_write_data(
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

        # ────────────────────────────────────────────────────────────────
        # Pipeline group finalizer
        #
        # Consumes the groups table stream. When a group META item makes its
        # OPEN → terminal transition, the finalizer claims the emission
        # (conditional write, at-most-once), publishes a "Pipeline Group
        # Completed" event to the pipelines bus, resolves the output
        # artifacts each member execution produced (new derived
        # representations), and starts a standard bulk-download job so the
        # artifacts are zipped and delivered through the existing
        # notification flow.
        # ────────────────────────────────────────────────────────────────
        # The bulk-download workflow and the users table live in the assets
        # API stack; both have deterministic names, so reference them by
        # name/ARN rather than importing cross-stack objects (matches the
        # precedent in api_gateway_assets.py which wires the users table by
        # its conventional name).
        users_table_name = f"{config.resource_prefix}-user-{config.environment}"
        users_table_arn = (
            f"arn:aws:dynamodb:{self.region}:{self.account}:table/{users_table_name}"
        )
        bulk_download_state_machine_arn = (
            f"arn:aws:states:{self.region}:{self.account}:stateMachine:"
            f"{config.resource_prefix}_Asset-Bulk-Download_{config.environment}"
        )

        self._group_finalizer_dlq = SQSConstruct(
            self,
            "PipelineGroupFinalizerDLQ",
            props=SQSProps(
                queue_name="pipeline-group-finalizer-dlq",
                visibility_timeout=Duration.minutes(2),
                retention_period=Duration.days(14),
                encryption=False,
                enforce_ssl=True,
                max_receive_count=0,
                removal_policy=RemovalPolicy.DESTROY,
            ),
        )

        self._pipeline_group_finalizer = Lambda(
            self,
            "PipelineGroupFinalizer",
            config=LambdaConfig(
                name="pipeline_group_finalizer",
                entry="lambdas/back_end/pipeline_group_finalizer",
                memory_size=256,
                timeout_minutes=5,
                snap_start=False,
                environment_variables={
                    "PIPELINE_GROUPS_TABLE_NAME": self._pipeline_groups_table.table_name,
                    "MEDIALAKE_ASSET_TABLE": props.asset_table.table_name,
                    "USER_TABLE_NAME": users_table_name,
                    "BULK_DOWNLOAD_STATE_MACHINE_ARN": bulk_download_state_machine_arn,
                    "PIPELINES_EVENT_BUS_NAME": props.pipelines_event_bus.event_bus_name,
                },
            ),
        )

        self._pipeline_group_finalizer.function.add_event_source(
            lambda_event_sources.DynamoEventSource(
                self._pipeline_groups_table,
                starting_position=lambda_.StartingPosition.LATEST,
                batch_size=10,
                max_batching_window=Duration.seconds(5),
                retry_attempts=3,
                bisect_batch_on_error=True,
                report_batch_item_failures=True,
                on_failure=lambda_event_sources.SqsDlq(self._group_finalizer_dlq.queue),
            )
        )

        # Same-stack grants become identity policies on the Lambda role.
        self._pipeline_groups_table.grant_stream_read(
            self._pipeline_group_finalizer.function
        )
        self._pipeline_groups_table.grant_read_write_data(
            self._pipeline_group_finalizer.function
        )

        # The asset table belongs to the base-infrastructure stack. Grant it
        # explicitly rather than with grant_read_data(): for a cross-stack
        # grantee, TableV2.grant_*() attaches a resource policy to the shared
        # table naming this role, which both mutates a table this stack does
        # not own and fails with "Invalid principal in policy document" when
        # the role does not exist yet.
        self._pipeline_group_finalizer.function.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["dynamodb:GetItem", "dynamodb:BatchGetItem"],
                resources=[props.asset_table.table_arn],
            )
        )

        # Users table (bulk-download job records) — referenced by conventional name
        self._pipeline_group_finalizer.function.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "dynamodb:GetItem",
                    "dynamodb:PutItem",
                    "dynamodb:UpdateItem",
                    "dynamodb:Query",
                ],
                resources=[users_table_arn, f"{users_table_arn}/index/*"],
            )
        )

        # Start the bulk-download packaging workflow
        self._pipeline_group_finalizer.function.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["states:StartExecution"],
                resources=[bulk_download_state_machine_arn],
            )
        )

        # Publish "Pipeline Group Completed" to the pipelines bus
        self._pipeline_group_finalizer.function.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["events:PutEvents"],
                resources=[props.pipelines_event_bus.event_bus_arn],
            )
        )

        # ────────────────────────────────────────────────────────────────
        # Pipeline group sweeper
        #
        # Safety net for groups whose member executions never emit a
        # terminal event (lost events, manual aborts outside Step
        # Functions). Periodically transitions stale OPEN groups to a
        # terminal status so the finalizer still packages whatever
        # completed.
        # ────────────────────────────────────────────────────────────────
        self._pipeline_group_sweeper = Lambda(
            self,
            "PipelineGroupSweeper",
            config=LambdaConfig(
                name="pipeline_group_sweeper",
                entry="lambdas/back_end/pipeline_group_sweeper",
                memory_size=256,
                timeout_minutes=5,
                snap_start=False,
                environment_variables={
                    "PIPELINE_GROUPS_TABLE_NAME": self._pipeline_groups_table.table_name,
                    "GROUP_TIMEOUT_HOURS": "24",
                },
            ),
        )

        _ = events.Rule(
            self,
            "PipelineGroupSweeperScheduleRule",
            schedule=events.Schedule.rate(Duration.minutes(30)),
            targets=[targets.LambdaFunction(self._pipeline_group_sweeper.function)],
            description="Periodically times out stale OPEN pipeline execution groups.",
        )

        self._pipeline_groups_table.grant_read_write_data(
            self._pipeline_group_sweeper.function
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
    def pipeline_groups_table(self) -> dynamodb.ITable:
        return self._pipeline_groups_table

    @property
    def pipelines_executions_event_bus(self) -> events.EventBus:
        return self._pipelines_executions_event_bus.event_bus

    @property
    def get_pipelines_executions_lambda(self) -> lambda_.IFunction:
        return self._get_pipelines_executions_lambda.function

    @property
    def post_retry_pipelines_executions_lambda(self) -> lambda_.IFunction:
        return self._post_retry_pipelines_executions_lambda.function
