from dataclasses import dataclass
from aws_cdk import (
    aws_apigateway as apigateway,
    aws_iam as iam,
    aws_s3 as s3,
    aws_events as events,
    aws_dynamodb as dynamodb,
    aws_secretsmanager as secretsmanager,
    aws_lambda as lambda_,
)
from constructs import Construct
from config import config
from medialake_constructs.shared_constructs.dynamodb import (
    DynamoDB,
    DynamoDBProps,
)
from medialake_constructs.shared_constructs.lam_deployment import LambdaDeployment
from medialake_constructs.shared_constructs.lambda_base import (
    Lambda,
    LambdaConfig,
)


@dataclass
class ApiGatewayPipelinesProps:
    """Configuration for Lambda function creation."""

    asset_table: dynamodb.TableV2
    connector_table: dynamodb.TableV2
    pipeline_table: dynamodb.TableV2
    iac_assets_bucket: s3.Bucket
    image_proxy_lambda: lambda_.IFunction
    image_metadata_extractor_lambda: lambda_.IFunction
    get_pipelines_executions_lambda: lambda_.IFunction
    post_retry_pipelines_executions_lambda: lambda_.IFunction


class ApiGatewayPipelinesConstruct(Construct):
    def __init__(
        self,
        scope: Construct,
        id: str,
        api_resource: apigateway.IResource,
        cognito_authorizer: apigateway.IAuthorizer,
        ingest_event_bus: events.EventBus,
        iac_assets_bucket: s3.Bucket,
        media_assets_bucket: s3.Bucket,
        x_origin_verify_secret: secretsmanager.Secret,
        props: ApiGatewayPipelinesProps,
    ) -> None:
        super().__init__(scope, id)

        self.pipeline_trigger_lambda_deployment = LambdaDeployment(
            self,
            "PipelineTriggerLambdaDeployment",
            destination_bucket=iac_assets_bucket.bucket,
            code_path=["lambdas", "pipelines", "pipeline_trigger"],
        )

        # Create pipelines resource
        pipelines_resource = api_resource.root.add_resource("pipelines")

        get_pipelines_handler = Lambda(
            self,
            "GetPipelinesHandler",
            config=LambdaConfig(
                name="GetPipelinesHandler",
                entry="lambdas/api/pipelines/get_pipelines",
                environment_variables={
                    "X_ORIGIN_VERIFY_SECRET_ARN": x_origin_verify_secret.secret_arn,
                    "PIPELINES_TABLE_NAME": props.pipeline_table.table_arn,
                },
            ),
        )

        get_pipelines_handler.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=["dynamodb:GetItem", "dynamodb:Scan"],
                resources=[props.pipeline_table.table_arn],
            )
        )

        pipelines_resource.add_method(
            "GET",
            apigateway.LambdaIntegration(get_pipelines_handler.function),
            authorization_type=apigateway.AuthorizationType.COGNITO,
            authorizer=cognito_authorizer,
        )

        # POST /api/pipelines
        post_pipelines_lambda_config = LambdaConfig(
            name="PostPipelinesHandler",
            timeout_minutes=10,
            entry="lambdas/api/pipelines/post_pipelines",
            environment_variables={
                "X_ORIGIN_VERIFY_SECRET_ARN": x_origin_verify_secret.secret_arn,
                "MEDIA_ASSETS_BUCKET_NAME": media_assets_bucket.bucket.bucket_name,
                "MEDIA_ASSETS_BUCKET_NAME_KMS_KEY": media_assets_bucket.kms_key.key_arn,
                "PIPELINES_TABLE_NAME": props.pipeline_table.table_arn,
                "MEDIALAKE_ASSET_TABLE": props.asset_table.table_arn,
                "IMAGE_PROXY_LAMBDA_ARN": props.image_proxy_lambda.function_arn,
                "IMAGE_METADATA_EXTRACTOR_LAMBDA_ARN": props.image_metadata_extractor_lambda.function_arn,
                # "IMAGE_METADATA_EXTRACTOR_LAMBDA": self.image_metadata_extractor_lambda_deployment.deployment_key,
                # "IMAGE_PROXY_LAMBDA": self.image_proxy_lambda_deployment.deployment_key,
                "PIPELINE_TRIGGER_LAMBDA": self.pipeline_trigger_lambda_deployment.deployment_key,
                "IAC_ASSETS_BUCKET": iac_assets_bucket.bucket.bucket_name,
                "INGEST_EVENT_BUS": ingest_event_bus.event_bus_name,
                "CONNECTOR_TABLE": props.connector_table.table_arn,
                "AWS_ACCOUNT_ID": scope.account,
                "GLOBAL_PREFIX": config.global_prefix,
            },
        )
        post_pipelines_handler = Lambda(
            self,
            "PostPipelinesHandler",
            config=post_pipelines_lambda_config,
        )

        post_pipelines_handler.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "sqs:CreateQueue",
                    "sqs:GetQueueAttributes",
                    "sqs:TagQueue",
                    "sqs:setqueueattributes",
                    "sqs:DeleteQueue",
                ],
                resources=["*"],
            )
        )

        post_pipelines_handler.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "iam:TagRole",
                    "iam:CreateRole",
                    "iam:AttachRolePolicy",
                    "iam:ListAttachedRolePolicies",
                    "iam:PassRole",
                    "iam:PutRolePolicy",
                    "iam:GetRole",
                    "iam:ListRolePolicies",  # for rollback
                    "iam:DetachRolePolicy",  # for rollback
                    "iam:DeleteRolePolicy",  # for rollback
                    "iam:DeleteRole",  # for rollback
                ],
                resources=["*"],
            )
        )

        post_pipelines_handler.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "lambda:CreateFunction",
                    "lambda:TagResource",
                    "lambda:GetLayerVersion",
                    "lambda:GetFunction",
                    "lambda:CreateEventSourceMapping",
                    "lambda:UpdateFunctionConfiguration",
                    "lambda:DeleteFunction",  # For rollback
                ],
                resources=["*"],
            )
        )

        post_pipelines_handler.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "states:CreateStateMachine",
                    "states:TagResource",
                    "states:DescribeStateMachine",
                    "states:DeleteStateMachine",  # For rollback
                ],
                resources=["*"],
            )
        )

        post_pipelines_handler.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=["dynamodb:PutItem", "dynamodb:Scan"],
                resources=[props.pipeline_table.table_arn],
            )
        )

        post_pipelines_handler.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=["dynamodb:Scan"],
                resources=[props.connector_table.table_arn],
            )
        )

        post_pipelines_handler.function.add_to_role_policy(
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

        post_pipelines_handler.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=["s3:PutBucketPolicy", "s3:GetBucketPolicy"],
                resources=["*"],
            )
        )

        iac_assets_bucket.bucket.grant_read_write(post_pipelines_handler.function)

        pipelines_resource.add_method(
            "POST",
            apigateway.LambdaIntegration(post_pipelines_handler.function),
            authorization_type=apigateway.AuthorizationType.COGNITO,
            authorizer=cognito_authorizer,
        )

        # Pipeline ID specific endpoints
        pipeline_id_resource = pipelines_resource.add_resource("{pipelineId}")

        # GET /api/pipelines/{pipelineId}
        get_pipeline_id_lambda_config = LambdaConfig(
            name="GetPipelineIdHandler",
            entry=("lambdas/api/pipelines/rp_pipelineId/get_pipeline"),
            environment_variables={
                "X_ORIGIN_VERIFY_SECRET_ARN": x_origin_verify_secret.secret_arn,
                "PIPELINES_TABLE_NAME": props.pipeline_table.table_arn,
            },
        )
        get_pipeline_id_handler = Lambda(
            self,
            "GetPipelineIdHandler",
            config=get_pipeline_id_lambda_config,
        )

        pipeline_id_resource.add_method(
            "GET",
            apigateway.LambdaIntegration(get_pipeline_id_handler.function),
            authorization_type=apigateway.AuthorizationType.COGNITO,
            authorizer=cognito_authorizer,
        )

        # PUT /api/pipelines/{pipelineId}
        put_pipeline_id_lambda_config = LambdaConfig(
            name="PutPipelineIdHandler",
            entry=("lambdas/api/pipelines/rp_pipelineId/put_pipeline"),
            environment_variables={
                "X_ORIGIN_VERIFY_SECRET_ARN": x_origin_verify_secret.secret_arn,
                "PIPELINES_TABLE_NAME": props.pipeline_table.table_arn,
            },
        )
        put_pipeline_id_handler = Lambda(
            self,
            "PutPipelineIdHandler",
            config=put_pipeline_id_lambda_config,
        )

        pipeline_id_resource.add_method(
            "PUT",
            apigateway.LambdaIntegration(put_pipeline_id_handler.function),
            authorization_type=apigateway.AuthorizationType.COGNITO,
            authorizer=cognito_authorizer,
        )

        # DELETE /api/pipelines/{pipelineId}
        del_pipeline_id_lambda_config = LambdaConfig(
            name="DeletePipelineIdHandler",
            entry=("lambdas/api/pipelines/rp_pipelineId/del_pipeline"),
            environment_variables={
                "X_ORIGIN_VERIFY_SECRET_ARN": x_origin_verify_secret.secret_arn,
                "PIPELINES_TABLE_NAME": props.pipeline_table.table_arn,
            },
        )
        del_pipeline_id_handler = Lambda(
            self,
            "DeletePipelineIdHandler",
            config=del_pipeline_id_lambda_config,
        )

        # Add Lambda function deletion permissions
        del_pipeline_id_handler.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "lambda:DeleteFunction",
                    "lambda:ListEventSourceMappings",
                    "lambda:DeleteEventSourceMapping",
                ],
                resources=["*"],
            )
        )

        # Add Step Functions deletion permissions
        del_pipeline_id_handler.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=["states:DeleteStateMachine"],
                resources=["*"],
            )
        )

        # Add SQS deletion permissions
        del_pipeline_id_handler.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=["sqs:DeleteQueue", "sqs:setqueueattributes"],
                resources=["*"],
            )
        )

        # Add EventBridge permissions
        del_pipeline_id_handler.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "events:RemoveTargets",
                    "events:DeleteRule",
                    "events:DescribeRule",
                    "events:ListTargetsByRule",
                ],
                resources=["*"],
            )
        )

        # Add IAM role and policy deletion permissions
        del_pipeline_id_handler.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "iam:DeleteRole",
                    "iam:DeleteRolePolicy",
                    "iam:DetachRolePolicy",
                    "iam:ListAttachedRolePolicies",
                    "iam:ListRolePolicies",
                    "iam:GetRole",
                ],
                resources=["*"],
            )
        )

        # Add DynamoDB delete permission
        del_pipeline_id_handler.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=["dynamodb:DeleteItem", "dynamodb:GetItem"],
                resources=[props.pipeline_table.table.table_arn],
            )
        )

        pipeline_id_resource.add_method(
            "DELETE",
            apigateway.LambdaIntegration(del_pipeline_id_handler.function),
            authorization_type=apigateway.AuthorizationType.COGNITO,
            authorizer=cognito_authorizer,
        )

        pipelines_executions_resource = pipelines_resource.add_resource("executions")

        # GET /api/pipelines/executions/ - responds with all pipeline executions
        pipelines_executions_resource.add_method(
            "GET",
            apigateway.LambdaIntegration(props.get_pipelines_executions_lambda),
            authorization_type=apigateway.AuthorizationType.COGNITO,
            authorizer=cognito_authorizer,
        )

        # Add new execution ID resource and retry endpoint
        execution_id_resource = pipelines_executions_resource.add_resource(
            "{executionId}"
        )
        retry_resource = execution_id_resource.add_resource("retry")

        # POST /api/pipelines/executions/{executionId}/retry

        # retry_resource.add_method(
        #     "POST",
        #     apigateway.LambdaIntegration(props.post_retry_pipelines_executions_lambda),
        #     authorization_type=apigateway.AuthorizationType.COGNITO,
        #     authorizer=cognito_authorizer,
        # )
