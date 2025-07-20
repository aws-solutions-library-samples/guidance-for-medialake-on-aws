from dataclasses import dataclass
from typing import Optional

from aws_cdk import Duration, Stack
from aws_cdk import aws_apigateway as apigateway
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_events as events
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_secretsmanager as secretsmanager
from aws_cdk import aws_stepfunctions as sfn
from aws_cdk import aws_stepfunctions_tasks as tasks
from constructs import Construct

from config import config
from medialake_constructs.api_gateway.api_gateway_utils import add_cors_options_method
from medialake_constructs.shared_constructs.lambda_base import Lambda, LambdaConfig
from medialake_constructs.shared_constructs.lambda_layers import (
    CommonLibrariesLayer,
    PowertoolsLayer,
    PowertoolsLayerConfig,
    PyamlLayer,
    ShortuuidLayer,
)
from medialake_constructs.shared_constructs.s3bucket import S3Bucket


@dataclass
class ApiGatewayPipelinesProps:
    """Configuration for Lambda function creation."""

    asset_table: dynamodb.TableV2
    connector_table: dynamodb.TableV2
    node_table: dynamodb.TableV2
    pipeline_table: dynamodb.TableV2
    integrations_table: dynamodb.TableV2
    iac_assets_bucket: s3.IBucket
    external_payload_bucket: s3.IBucket
    pipelines_nodes_templates_bucket: s3.IBucket
    open_search_endpoint: str
    api_resource: apigateway.IResource
    pipelines_event_bus: events.EventBus
    iac_assets_bucket: s3.IBucket
    media_assets_bucket: S3Bucket
    x_origin_verify_secret: secretsmanager.Secret
    cognito_authorizer: apigateway.IAuthorizer
    get_pipelines_executions_lambda: lambda_.IFunction
    post_retry_pipelines_executions_lambda: lambda_.IFunction
    mediaconvert_queue_arn: str = None
    mediaconvert_role_arn: str = None
    vpc: Optional[ec2.IVpc] = None
    security_group: Optional[ec2.SecurityGroup] = None
    # S3 Vector configuration
    s3_vector_bucket_name: str = None
    s3_vector_index_name: str = "media-vectors"
    s3_vector_dimension: int = 1024


class ApiGatewayPipelinesConstruct(Construct):

    def __init__(
        self,
        scope: Construct,
        id: str,
        props: ApiGatewayPipelinesProps,
    ) -> None:
        super().__init__(scope, id)

        # Determine the current stack
        stack = Stack.of(self)

        # Get the region and account ID
        self.region = stack.region
        self.account_id = stack.account

        del_lambda_iam_boundary_policy = iam.ManagedPolicy(
            self,
            "DelPipelineServiceBoundaryPolicy",
            statements=[
                # Broad Allow for non-IAM actions
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "lambda:*",
                        "s3:*",
                        "sqs:*",
                        "sns:*",
                        "dynamodb:*",
                        "events:*",
                        "states:*",
                        "logs:*",
                    ],
                    resources=["*"],
                ),
                # Unconditional Allow for specific IAM read-only actions
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "iam:GetRole",
                        "iam:ListRoles",
                        "iam:GetRolePolicy",
                        "iam:ListRolePolicies",
                        "iam:ListAttachedRolePolicies",
                        "iam:DeleteRole",
                        "iam:PutRolePolicy",
                        "iam:DeleteRolePolicy",
                        "iam:AttachRolePolicy",
                        "iam:DetachRolePolicy",
                        "iam:PassRole",
                    ],
                    resources=["*"],
                ),
            ],
        )

        post_lambda_iam_boundary_policy = iam.ManagedPolicy(
            self,
            "PostPipelineServiceBoundaryPolicy",
            statements=[
                # Broad Allow for non-IAM actions
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "lambda:*",
                        "s3:*",
                        "sqs:*",
                        "sns:*",
                        "dynamodb:*",
                        "events:*",
                        "states:*",
                        "logs:*",
                    ],
                    resources=["*"],
                ),
                # Unconditional Allow for specific IAM read-only actions
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "iam:CreateRole",
                        "iam:GetRole",
                        "iam:ListRoles",
                        "iam:GetRolePolicy",
                        "iam:ListRolePolicies",
                        "iam:ListAttachedRolePolicies",
                        "iam:DeleteRole",
                        "iam:PutRolePolicy",
                        "iam:DeleteRolePolicy",
                        "iam:AttachRolePolicy",
                        "iam:DetachRolePolicy",
                        "iam:UpdateRole",
                        "iam:UpdateRoleDescription",
                        "iam:TagRole",
                        "iam:UntagRole",
                        "iam:PassRole",
                    ],
                    resources=["*"],
                ),
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "kms:Decrypt",
                    ],
                    resources=["*"],
                ),
                # Add EC2 permissions needed for VPC Lambda functions
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "ec2:DescribeVpcs",
                        "ec2:DescribeSubnets",
                        "ec2:DescribeSecurityGroups",
                    ],
                    resources=["*"],
                ),
            ],
        )

        self._pipeline_trigger_lambda = Lambda(
            self,
            "PipelineTriggerLambda",
            config=LambdaConfig(
                name="PipelineTrigger",
                entry="lambdas/pipelines/pipeline_trigger",
                reserved_concurrent_executions=40,
                timeout_minutes=5,
                memory_size=256,
                environment_variables={
                    "PIPELINES_TABLE_NAME": props.pipeline_table.table_name,
                },
            ),
        )

        # Add permissions to list and describe Step Functions and their executions
        self._pipeline_trigger_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "states:ListStateMachines",
                    "states:ListExecutions",
                    "states:DescribeExecution",
                    "states:DescribeStateMachine",
                    "states:GetExecutionHistory",
                ],
                resources=["*"],
            )
        )

        # Create pipelines resource
        pipelines_resource = props.api_resource.add_resource("pipelines")

        self._get_pipelines_handler = Lambda(
            self,
            "GetPipelinesHandler",
            config=LambdaConfig(
                name="GetPipelinesHandler",
                entry="lambdas/api/pipelines/get_pipelines",
                environment_variables={
                    "X_ORIGIN_VERIFY_SECRET_ARN": props.x_origin_verify_secret.secret_arn,
                    "PIPELINES_TABLE_NAME": props.pipeline_table.table_arn,
                },
            ),
        )

        self._get_pipelines_handler.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=["dynamodb:GetItem", "dynamodb:Scan"],
                resources=[props.pipeline_table.table_arn],
            )
        )

        pipelines_resource.add_method(
            "GET",
            apigateway.LambdaIntegration(self._get_pipelines_handler.function),
            authorization_type=apigateway.AuthorizationType.COGNITO,
            authorizer=props.cognito_authorizer,
        )

        ## Pipelines
        pyaml_layer = PyamlLayer(self, "PyamlLayer")
        shortuuid_layer = ShortuuidLayer(self, "ShortuuidLayer")
        common_libraries_layer = CommonLibrariesLayer(self, "CommonLibrariesLayer")
        powertools_layer_config = PowertoolsLayerConfig()
        powertools_layer = PowertoolsLayer(
            self, "PowertoolsLayer", config=powertools_layer_config
        )

        # POST /api/pipelines
        post_pipelines_lambda_config = LambdaConfig(
            name="pipeline_post",
            timeout_minutes=15,
            entry="lambdas/api/pipelines/post_pipelines",
            layers=[pyaml_layer.layer, shortuuid_layer.layer],
            iam_role_boundary_policy=post_lambda_iam_boundary_policy,
            environment_variables={
                "MEDIA_ASSETS_BUCKET_NAME": props.media_assets_bucket.bucket_name,
                "MEDIA_ASSETS_BUCKET_ARN_KMS_KEY": props.media_assets_bucket.key_arn,
                "PIPELINES_TABLE": props.pipeline_table.table_arn,
                "MEDIALAKE_ASSET_TABLE": props.asset_table.table_arn,
                "INTEGRATIONS_TABLE": props.integrations_table.table_arn,
                "IAC_ASSETS_BUCKET": props.iac_assets_bucket.bucket.bucket_name,
                "EXTERNAL_PAYLOAD_BUCKET": props.external_payload_bucket.bucket_name,
                "NODE_TEMPLATES_BUCKET": props.pipelines_nodes_templates_bucket.bucket_name,
                "PIPELINES_EVENT_BUS_NAME": props.pipelines_event_bus.event_bus_name,
                "RESOURCE_PREFIX": config.resource_prefix,
                "MEDIACONVERT_QUEUE_ARN": props.mediaconvert_queue_arn,
                "MEDIACONVERT_ROLE_ARN": props.mediaconvert_role_arn,
                "NODE_TABLE": props.node_table.table_arn,
                "OPENSEARCH_ENDPOINT": props.open_search_endpoint,
                "OPENSEARCH_VPC_SUBNET_IDS": ",".join(
                    [subnet.subnet_id for subnet in props.vpc.private_subnets]
                ),
                "OPENSEARCH_SECURITY_GROUP_ID": props.security_group.security_group_id,
                "ACCOUNT_ID": self.account_id,
                "POWERTOOLS_LAYER_ARN": powertools_layer.layer.layer_version_arn,
                "COMMON_LIBRARIES_LAYER_ARN": common_libraries_layer.layer.layer_version_arn,
                # S3 Vector configuration
                "VECTOR_BUCKET_NAME": props.s3_vector_bucket_name,
                "INDEX_NAME": props.s3_vector_index_name,
                "VECTOR_DIMENSION": str(props.s3_vector_dimension),
            },
        )

        self._post_pipelines_handler = Lambda(
            self,
            "PostPipelinesHandler",
            config=post_pipelines_lambda_config,
        )

        self._post_pipelines_handler.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "ec2:DescribeVpcs",
                    "ec2:DescribeSubnets",
                    "ec2:DescribeSecurityGroups",
                ],
                resources=["*"],
            )
        )

        self._post_pipelines_handler.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "sqs:CreateQueue",
                    "sqs:GetQueueAttributes",
                    "sqs:TagQueue",
                    "sqs:setqueueattributes",
                    "sqs:DeleteQueue",
                    "sqs:listqueues",
                ],
                resources=["*"],
            )
        )

        self._post_pipelines_handler.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=["s3:ListBucket", "s3:GetObject"],
                resources=[
                    props.pipelines_nodes_templates_bucket.bucket_arn,
                    f"{props.pipelines_nodes_templates_bucket.bucket_arn}/*",
                ],
            )
        )

        self._post_pipelines_handler.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "iam:TagRole",
                    "iam:CreateRole",
                    "iam:AttachRolePolicy",
                    "iam:ListAttachedRolePolicies",
                    "iam:PassRole",
                    "iam:PutRolePolicy",
                    "iam:GetRolePolicy",
                    "iam:GetRole",
                    "iam:ListRolePolicies",  # for rollback
                    "iam:DetachRolePolicy",  # for rollback
                    "iam:DeleteRolePolicy",  # for rollback
                    "iam:DeleteRole",  # for rollback
                ],
                resources=["*"],
            )
        )

        self._post_pipelines_handler.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "lambda:CreateFunction",
                    "lambda:TagResource",
                    "lambda:GetLayerVersion",
                    "lambda:GetFunction",
                    "lambda:CreateEventSourceMapping",
                    "lambda:UpdateFunctionConfiguration",
                    "lambda:GetFunctionConfiguration",
                    "lambda:ListEventSourceMappings",
                    "lambda:DeleteFunction",  # For rollback
                ],
                resources=["*"],
            )
        )

        self._post_pipelines_handler.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "states:CreateStateMachine",
                    "states:TagResource",
                    "states:UpdateStateMachine",
                    "states:DescribeStateMachine",
                    "states:ListStateMachines",  # For check if exists
                    "states:DeleteStateMachine",  # For rollback
                ],
                resources=["*"],
            )
        )

        self._post_pipelines_handler.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=["dynamodb:GetItem"],
                resources=[props.node_table.table_arn],
            )
        )

        self._post_pipelines_handler.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "dynamodb:GetItem",
                    "dynamodb:PutItem",
                    "dynamodb:Scan",
                    "dynamodb:UpdateItem",
                ],
                resources=[props.pipeline_table.table_arn],
            )
        )

        self._post_pipelines_handler.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=["dynamodb:Scan"],
                resources=[props.connector_table.table_arn],
            )
        )

        self._post_pipelines_handler.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=["dynamodb:GetItem", "dynamodb:Query"],
                resources=[props.integrations_table.table_arn],
            )
        )

        self._post_pipelines_handler.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "events:TagResource",
                    "events:PutRule",
                    "events:PutTargets",
                    "events:DescribeRule",
                    "events:DeleteRule",
                ],
                resources=["*"],
            )
        )

        self._post_pipelines_handler.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=["s3:PutBucketPolicy", "s3:GetBucketPolicy"],
                resources=["*"],
            )
        )

        self._post_pipelines_handler.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=["kms:Decrypt"],
                resources=["*"],
            )
        )

        self._post_pipelines_handler.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "logs:CreateLogStream",
                    "logs:PutLogEvents",
                ],
                resources=["*"],
            )
        )

        props.iac_assets_bucket.bucket.grant_read_write(
            self._post_pipelines_handler.function
        )

        # Create a simple Step Function that just invokes the pipeline Lambda
        pipeline_worker_task = tasks.LambdaInvoke(
            self,
            "PipelineWorkerTask",
            lambda_function=self._post_pipelines_handler.function,
            output_path="$",
            retry_on_service_exceptions=True,
            payload_response_only=True,
        )

        # Define the success state
        success_state = sfn.Succeed(self, "SuccessState")

        # Create a simple state machine definition
        definition = pipeline_worker_task.next(success_state)

        # Create the state machine
        self._pipeline_creation_state_machine = sfn.StateMachine(
            self,
            "PipelineCreationStateMachine",
            state_machine_name=f"{config.resource_prefix}_Pipeline_Creator",
            definition=definition,
            timeout=Duration.minutes(300),
        )

        # Create the front-end Lambda
        self._post_pipelines_async_handler = Lambda(
            self,
            "PostPipelinesAsyncHandler",
            config=LambdaConfig(
                name="pipeline_post_async",
                entry="lambdas/api/pipelines/post_pipelines_async",
                layers=[pyaml_layer.layer, shortuuid_layer.layer],
                iam_role_boundary_policy=post_lambda_iam_boundary_policy,
                environment_variables={
                    "PIPELINE_CREATION_STATE_MACHINE_ARN": self._pipeline_creation_state_machine.state_machine_arn,
                    "PIPELINES_TABLE": props.pipeline_table.table_name,
                },
            ),
        )

        # Grant the front-end Lambda permission to start the Step Function
        self._pipeline_creation_state_machine.grant_start_execution(
            self._post_pipelines_async_handler.function
        )

        # Grant the front-end Lambda permission to access the DynamoDB table
        self._post_pipelines_async_handler.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "dynamodb:GetItem",
                    "dynamodb:PutItem",
                    "dynamodb:UpdateItem",
                    "dynamodb:Scan",
                ],
                resources=[props.pipeline_table.table_arn],
            )
        )

        # Grant the front-end Lambda permission to describe Step Functions executions
        self._post_pipelines_async_handler.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "states:DescribeExecution",
                ],
                resources=["*"],
            )
        )

        pipelines_resource.add_method(
            "POST",
            apigateway.LambdaIntegration(self._post_pipelines_async_handler.function),
            authorization_type=apigateway.AuthorizationType.COGNITO,
            authorizer=props.cognito_authorizer,
        )

        # Add status endpoint
        pipelines_status_resource = pipelines_resource.add_resource("status")
        pipelines_status_resource.add_resource("{executionArn}").add_method(
            "GET",
            apigateway.LambdaIntegration(self._post_pipelines_async_handler.function),
            authorization_type=apigateway.AuthorizationType.COGNITO,
            authorizer=props.cognito_authorizer,
        )

        # Add get pipeline by ID endpoint - use a different name to avoid conflicts
        pipelines_resource.add_resource("pipeline").add_resource(
            "{pipelineId}"
        ).add_method(
            "GET",
            apigateway.LambdaIntegration(self._post_pipelines_async_handler.function),
            authorization_type=apigateway.AuthorizationType.COGNITO,
            authorizer=props.cognito_authorizer,
        )

        # DELETE /api/pipelines - now handled by the comprehensive del_pipelinesId handler
        # This endpoint is removed as we're consolidating to use only the {pipelineId} endpoint

        # POST /api/pipelines
        post_pipelines_lambda_config = LambdaConfig(
            name="pipeline_post",
            timeout_minutes=15,
            entry="lambdas/api/pipelines/post_pipelines",
            iam_role_boundary_policy=post_lambda_iam_boundary_policy,
            environment_variables={
                "X_ORIGIN_VERIFY_SECRET_ARN": props.x_origin_verify_secret.secret_arn,
                "MEDIA_ASSETS_BUCKET_NAME": props.media_assets_bucket.bucket_name,
                "MEDIA_ASSETS_BUCKET_ARN_KMS_KEY": props.media_assets_bucket.key_arn,
                "PIPELINES_TABLE_NAME": props.pipeline_table.table_arn,
                "MEDIALAKE_ASSET_TABLE": props.asset_table.table_arn,
                # "IMAGE_PROXY_LAMBDA_ARN": props.image_proxy_lambda.function_arn,
                # "IMAGE_METADATA_EXTRACTOR_LAMBDA_ARN": props.image_metadata_extractor_lambda.function_arn,
                # "IMAGE_METADATA_EXTRACTOR_LAMBDA": self.image_metadata_extractor_lambda_deployment.deployment_key,
                # "IMAGE_PROXY_LAMBDA": self.image_proxy_lambda_deployment.deployment_key,
                "PIPELINE_TRIGGER_LAMBDA_ARN": self._pipeline_trigger_lambda.function_arn,
                "IAC_ASSETS_BUCKET": props.iac_assets_bucket.bucket.bucket_name,
                "PIPELINES_EVENT_BUS": props.pipelines_event_bus.event_bus_name,
                "CONNECTOR_TABLE": props.connector_table.table_arn,
                "AWS_ACCOUNT_ID": scope.account,
                "GLOBAL_PREFIX": config.resource_prefix,
            },
        )

        # Pipeline ID specific endpoints - create only one {pipelineId} resource
        pipeline_id_resource = pipelines_resource.add_resource("{pipelineId}")

        # Comment out duplicate resource creation to avoid conflicts
        # # Add a resource for pipeline ID specific operations
        # pipeline_id_resource = pipelines_resource.add_resource("{pipelineId}")

        # # Add the DELETE method to the pipeline_id_resource
        # pipeline_id_resource.add_method(
        #     "DELETE",
        #     apigateway.LambdaIntegration(self._delete_pipelines_handler.function),
        #     authorization_type=apigateway.AuthorizationType.COGNITO,
        #     authorizer=props.cognito_authorizer,
        # )

        # GET /api/pipelines/{pipelineId}
        get_pipeline_id_lambda_config = LambdaConfig(
            name="pipeline_get",
            entry=("lambdas/api/pipelines/rp_pipelinesId/get_pipelinesId"),
            environment_variables={
                "X_ORIGIN_VERIFY_SECRET_ARN": props.x_origin_verify_secret.secret_arn,
                "PIPELINES_TABLE_NAME": props.pipeline_table.table_arn,
            },
        )

        self._get_pipeline_id_handler = Lambda(
            self,
            "GetPipelineIdHandler",
            config=get_pipeline_id_lambda_config,
        )

        self._get_pipeline_id_handler.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=["dynamodb:GetItem", "dynamodb:Scan"],
                resources=[props.pipeline_table.table_arn],
            )
        )

        pipeline_id_resource.add_method(
            "GET",
            apigateway.LambdaIntegration(self._get_pipeline_id_handler.function),
            authorization_type=apigateway.AuthorizationType.COGNITO,
            authorizer=props.cognito_authorizer,
        )

        # PUT /api/pipelines/{pipelineId}
        put_pipeline_id_lambda_config = LambdaConfig(
            name="pipeline_put",
            entry=("lambdas/api/pipelines/rp_pipelinesId/put_pipelinesId"),
            iam_role_boundary_policy=post_lambda_iam_boundary_policy,
            environment_variables={
                "X_ORIGIN_VERIFY_SECRET_ARN": props.x_origin_verify_secret.secret_arn,
                "PIPELINES_TABLE_NAME": props.pipeline_table.table_name,
                "PIPELINES_EVENT_BUS_NAME": props.pipelines_event_bus.event_bus_name,
            },
        )

        self._put_pipeline_id_handler = Lambda(
            self,
            "PutPipelineIdHandler",
            config=put_pipeline_id_lambda_config,
        )

        self._put_pipeline_id_handler.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=["dynamodb:GetItem", "dynamodb:UpdateItem"],
                resources=[props.pipeline_table.table_arn],
            )
        )

        self._put_pipeline_id_handler.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=["events:DisableRule", "events:EnableRule"],
                resources=[f"arn:aws:events:{self.region}:{self.account_id}:rule/*"],
            )
        )

        pipeline_id_resource.add_method(
            "PUT",
            apigateway.LambdaIntegration(self._put_pipeline_id_handler.function),
            authorization_type=apigateway.AuthorizationType.COGNITO,
            authorizer=props.cognito_authorizer,
        )

        # DELETE /pipelines/{pipelineId}
        del_pipeline_id_lambda_config = LambdaConfig(
            name="pipeline_del",
            timeout_minutes=15,
            entry=("lambdas/api/pipelines/rp_pipelinesId/del_pipelinesId"),
            layers=[pyaml_layer.layer, shortuuid_layer.layer],
            iam_role_boundary_policy=del_lambda_iam_boundary_policy,
            environment_variables={
                "PIPELINES_TABLE": props.pipeline_table.table_arn,
                "NODE_TABLE": props.node_table.table_arn,
                "ACCOUNT_ID": scope.account,
                "MEDIALAKE_ASSET_TABLE": props.asset_table.table_arn,
                "IAC_ASSETS_BUCKET": props.iac_assets_bucket.bucket.bucket_name,
                "NODE_TEMPLATES_BUCKET": props.pipelines_nodes_templates_bucket.bucket_name,
                "PIPELINES_EVENT_BUS_NAME": props.pipelines_event_bus.event_bus_name,
                "MEDIA_ASSETS_BUCKET_NAME": props.media_assets_bucket.bucket_name,
                "MEDIA_ASSETS_BUCKET_ARN_KMS_KEY": props.media_assets_bucket.key_arn,
            },
        )

        self._del_pipeline_id_handler = Lambda(
            self,
            "DeletePipelineIdHandler",
            config=del_pipeline_id_lambda_config,
        )

        # Add Lambda function deletion permissions
        # Lambda function deletion permissions
        self._del_pipeline_id_handler.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "lambda:DeleteFunction",
                ],
                resources=[
                    f"arn:aws:lambda:{self.region}:{self.account_id}:function:{config.resource_prefix}*",
                ],
            )
        )

        # Lambda event source mapping permissions - scoped to region/account
        self._del_pipeline_id_handler.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "lambda:ListEventSourceMappings",
                    "lambda:DeleteEventSourceMapping",
                ],
                resources=[
                    f"arn:aws:lambda:{self.region}:{self.account_id}:event-source-mapping:*",
                    f"arn:aws:lambda:{self.region}:{self.account_id}:function:*",
                ],
            )
        )

        # GetEventSourceMapping requires wildcard access due to AWS Lambda service internals
        self._del_pipeline_id_handler.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "lambda:GetEventSourceMapping",
                ],
                resources=["*"],
            )
        )

        # Add Step Functions deletion permissions
        self._del_pipeline_id_handler.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=["states:DeleteStateMachine"],
                resources=[
                    f"arn:aws:states:{self.region}:{self.account_id}:stateMachine:{config.resource_prefix}*"
                ],
            )
        )

        # Add SQS deletion permissions
        self._del_pipeline_id_handler.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=["sqs:DeleteQueue", "sqs:GetQueueAttributes"],
                resources=[
                    f"arn:aws:sqs:{self.region}:{self.account_id}:{config.resource_prefix}*"
                ],
            )
        )

        # Add EventBridge permissions
        self._del_pipeline_id_handler.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "events:RemoveTargets",
                    "events:DeleteRule",
                    "events:DescribeRule",
                    "events:ListTargetsByRule",
                ],
                resources=[f"arn:aws:events:{self.region}:{self.account_id}:rule/*"],
            )
        )

        # Add IAM role and policy deletion permissions
        self._del_pipeline_id_handler.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "iam:DeleteRole",
                    "iam:DeleteRolePolicy",
                    "iam:DetachRolePolicy",
                    "iam:ListAttachedRolePolicies",
                    "iam:ListRolePolicies",
                    "iam:GetRole",
                ],
                resources=[f"arn:aws:iam::{self.account_id}:role/*"],
            )
        )

        # Add DynamoDB delete permission
        self._del_pipeline_id_handler.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=["dynamodb:DeleteItem", "dynamodb:GetItem", "dynamodb:Scan"],
                resources=[props.pipeline_table.table_arn],
            )
        )

        pipeline_id_resource.add_method(
            "DELETE",
            apigateway.LambdaIntegration(self._del_pipeline_id_handler.function),
            authorization_type=apigateway.AuthorizationType.COGNITO,
            authorizer=props.cognito_authorizer,
        )

        pipelines_executions_resource = pipelines_resource.add_resource("executions")

        # GET /pipelines/executions/ - responds with all pipeline executions
        pipelines_executions_resource.add_method(
            "GET",
            apigateway.LambdaIntegration(props.get_pipelines_executions_lambda),
            authorization_type=apigateway.AuthorizationType.COGNITO,
            authorizer=props.cognito_authorizer,
        )

        # Add new execution ID resource and retry endpoint
        execution_id_resource = pipelines_executions_resource.add_resource(
            "{executionId}"
        )

        retry_resource = execution_id_resource.add_resource("retry")

        # POST /pipelines/executions/{executionId}/retry - retry execution
        retry_resource.add_method(
            "POST",
            apigateway.LambdaIntegration(props.post_retry_pipelines_executions_lambda),
            authorization_type=apigateway.AuthorizationType.COGNITO,
            authorizer=props.cognito_authorizer,
        )

        # Add CORS support to all pipeline API resources
        add_cors_options_method(pipelines_resource)
        add_cors_options_method(pipelines_executions_resource)
        add_cors_options_method(pipeline_id_resource)
        add_cors_options_method(execution_id_resource)
        add_cors_options_method(retry_resource)

    @property
    def post_pipelines_async_handler(self) -> Lambda:
        return self._post_pipelines_async_handler

    @property
    def post_pipelines_handler(self) -> lambda_.Function:
        return self._post_pipelines_handler.function

    @property
    def get_pipelines_handler(self) -> Lambda:
        return self._get_pipelines_handler

    @property
    def get_pipeline_id_handler(self) -> Lambda:
        return self._get_pipeline_id_handler

    @property
    def put_pipeline_id_handler(self) -> Lambda:
        return self._put_pipeline_id_handler

    @property
    def del_pipeline_id_handler(self) -> Lambda:
        return self._del_pipeline_id_handler

    @property
    def pipeline_trigger_lambda(self) -> Lambda:
        return self._pipeline_trigger_lambda
