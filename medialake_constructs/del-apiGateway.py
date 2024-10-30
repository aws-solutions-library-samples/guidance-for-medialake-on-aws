from aws_cdk import (
    aws_apigateway as apigateway,
    aws_lambda as _lambda,
    aws_logs as logs,
    aws_iam as iam,
    aws_dynamodb as ddb,
    aws_secretsmanager as secretsmanager,
    Duration,
    RemovalPolicy,
    SecretValue,
)
from dataclasses import dataclass
from constructs import Construct
from typing import Optional


@dataclass
class ApiGatewayProps:
    collection_endpoint: str = ""


class ApiGatewayConstruct(Construct):

    def __init__(
        self,
        scope: Construct,
        id: str,
        user_pool,
        props: Optional[ApiGatewayProps] = None,
    ) -> None:
        super().__init__(scope, id)

        self.props = props or ApiGatewayProps()

        # Create the Log Group
        rest_api_log_group = logs.LogGroup(
            self,
            "RestAPILogGroup",
            removal_policy=RemovalPolicy.DESTROY,
        )

        # Create the Rest API
        rest_api = apigateway.RestApi(
            self,
            "RestApi",
            endpoint_types=[apigateway.EndpointType.REGIONAL],
            cloud_watch_role=True,
            default_cors_preflight_options=apigateway.CorsOptions(
                allow_origins=apigateway.Cors.ALL_ORIGINS,
                allow_methods=apigateway.Cors.ALL_METHODS,
                allow_headers=[
                    "x-api-key",
                    "Content-Type",
                    "Authorization",
                    "X-Amz-Date",
                    "X-Amz-Security-Token",
                    "X-Origin-Verify",
                ],
                max_age=Duration.minutes(1),
            ),
            deploy=True,
            deploy_options=apigateway.StageOptions(
                stage_name="prod",
                tracing_enabled=True,
                metrics_enabled=True,
                throttling_rate_limit=2500,
                logging_level=apigateway.MethodLoggingLevel.INFO,
                data_trace_enabled=True,
                access_log_destination=apigateway.LogGroupLogDestination(
                    rest_api_log_group
                ),
            ),
        )

        # Cognito Authorizer
        cognito_authorizer = apigateway.CognitoUserPoolsAuthorizer(
            self,
            "CognitoAuthorizer",
            identity_source="method.request.header.Authorization",
            cognito_user_pools=[user_pool],
        )

        api_handler_log_group = logs.LogGroup(
            self, "ApiHandlerLogGroup", removal_policy=RemovalPolicy.DESTROY
        )

        lambda_architecture = _lambda.Architecture.X86_64

        x_origin_verify_secret = secretsmanager.Secret(
            self,
            "XOriginVerifySecret",
            removal_policy=RemovalPolicy.DESTROY,
            generate_secret_string=secretsmanager.SecretStringGenerator(
                exclude_punctuation=True,
                generate_string_key="headerValue",
                secret_string_template="{}",
            ),
        )

        # Create IAM role for Lambda function
        lambda_execution_role = iam.Role(
            self, "LambdaRole", assumed_by=iam.ServicePrincipal("lambda.amazonaws.com")
        )

        # Attach policies to the IAM role
        lambda_execution_role.add_to_principal_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["logs:CreateLogStream", "logs:PutLogEvents"],
                resources=[api_handler_log_group.log_group_arn],
            )
        )
        lambda_execution_role.add_to_principal_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["bedrock:InvokeModel"],
                resources=[
                    "arn:aws:bedrock:us-east-1::foundation-model/amazon.titan-embed-text-v2:0"
                ],
            )
        )

        twelve_labs_api_key = secretsmanager.Secret(
            self,
            "TwelveLabsApiKei",
            secret_name="twelve_labs_api_key_secret",
            description="Twelve Labs API Key Secret",
            secret_object_value={"key": SecretValue.unsafe_plain_text("TEMP")},
        )

        lambda_execution_role.add_to_principal_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["secretsmanager:GetSecretValue"],
                resources=[twelve_labs_api_key.secret_arn],
            )
        )

        lambda_execution_role.add_to_principal_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["es:ESHttpPut", "es:*", "aoss:APIAccessAll", "aoss:*"],
                resources=["*"],
            )
        )

        # API resources
        api_resource = rest_api.root.add_resource("api")

        # Add connectors resource and s3list sub-resource
        connectors_resource = api_resource.add_resource("connectors")
        s3list_resource = connectors_resource.add_resource("s3list")
        s3_resource = connectors_resource.add_resource("s3")

        # Create S3 list Lambda function
        s3list_handler = _lambda.Function(
            self,
            "S3ListHandler",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="index.handler",
            architecture=lambda_architecture,
            code=_lambda.Code.from_asset("lambdas/api/connectors/s3list"),
            log_group=api_handler_log_group,
            role=lambda_execution_role,
            timeout=Duration.seconds(30),
            environment={
                "X_ORIGIN_VERIFY_SECRET_ARN": x_origin_verify_secret.secret_arn,
            },
        )

        post_s3_handler = _lambda.Function(
            self,
            "PostS3Handler",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="index.handler",
            architecture=lambda_architecture,
            code=_lambda.Code.from_asset("lambdas/api/connectors/s3/post_s3"),
            log_group=api_handler_log_group,
            role=lambda_execution_role,
            timeout=Duration.seconds(30),
            environment={
                "X_ORIGIN_VERIFY_SECRET_ARN": x_origin_verify_secret.secret_arn,
            },
        )

        # Add S3 list permissions to Lambda role
        lambda_execution_role.add_to_principal_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["s3:ListAllMyBuckets"],
                resources=["*"],
            )
        )

        # Add GET method to s3list resource
        s3list_resource.add_method(
            "GET",
            apigateway.LambdaIntegration(s3list_handler),
            authorization_type=apigateway.AuthorizationType.COGNITO,
            authorizer=cognito_authorizer,
        )

        # Add POST method to post_s3 resource
        s3_resource.add_method(
            "POST",
            apigateway.LambdaIntegration(post_s3_handler),
            authorization_type=apigateway.AuthorizationType.COGNITO,
            authorizer=cognito_authorizer,
        )

        # Add pipelines resources
        # The `pipelines_resource` is creating a resource named "pipelines" under the main API
        # resource "api". This resource represents a collection of pipelines and is used to define
        # endpoints related to pipelines within the API Gateway. It allows for organizing and grouping
        # API endpoints related to pipelines under a common path.
        pipelines_resource = api_resource.add_resource("pipelines")

        # GET /api/pipelines
        get_pipelines_handler = _lambda.Function(
            self,
            "GetPipelinesHandler",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="index.handler",
            architecture=lambda_architecture,
            code=_lambda.Code.from_asset("lambdas/api/pipelines/get_pipelines"),
            log_group=api_handler_log_group,
            role=lambda_execution_role,
            timeout=Duration.seconds(30),
            environment={
                "X_ORIGIN_VERIFY_SECRET_ARN": x_origin_verify_secret.secret_arn,
            },
        )

        pipelines_resource.add_method(
            "GET",
            apigateway.LambdaIntegration(get_pipelines_handler),
            authorization_type=apigateway.AuthorizationType.COGNITO,
            authorizer=cognito_authorizer,
        )

        # POST /api/pipelines
        post_pipelines_handler = _lambda.Function(
            self,
            "PostPipelinesHandler",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="index.handler",
            architecture=lambda_architecture,
            code=_lambda.Code.from_asset("lambdas/api/pipelines/post_pipelines"),
            log_group=api_handler_log_group,
            role=lambda_execution_role,
            timeout=Duration.seconds(30),
            environment={
                "X_ORIGIN_VERIFY_SECRET_ARN": x_origin_verify_secret.secret_arn,
            },
        )

        pipelines_resource.add_method(
            "POST",
            apigateway.LambdaIntegration(post_pipelines_handler),
            authorization_type=apigateway.AuthorizationType.COGNITO,
            authorizer=cognito_authorizer,
        )

        # Pipeline ID specific endpoints
        pipeline_id_resource = pipelines_resource.add_resource("{pipelineId}")

        # GET /api/pipelines/{pipelineId}
        get_pipeline_id_handler = _lambda.Function(
            self,
            "GetPipelineIdHandler",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="index.handler",
            architecture=lambda_architecture,
            code=_lambda.Code.from_asset(
                "lambdas/api/pipelines/rp_pipeline_id/get_pipeline_id"
            ),
            log_group=api_handler_log_group,
            role=lambda_execution_role,
            timeout=Duration.seconds(30),
            environment={
                "X_ORIGIN_VERIFY_SECRET_ARN": x_origin_verify_secret.secret_arn,
            },
        )

        pipeline_id_resource.add_method(
            "GET",
            apigateway.LambdaIntegration(get_pipeline_id_handler),
            authorization_type=apigateway.AuthorizationType.COGNITO,
            authorizer=cognito_authorizer,
        )

        # PUT /api/pipelines/{pipelineId}
        put_pipeline_id_handler = _lambda.Function(
            self,
            "PutPipelineIdHandler",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="index.handler",
            architecture=lambda_architecture,
            code=_lambda.Code.from_asset(
                "lambdas/api/pipelines/rp_pipeline_id/put_pipeline_id"
            ),
            log_group=api_handler_log_group,
            role=lambda_execution_role,
            timeout=Duration.seconds(30),
            environment={
                "X_ORIGIN_VERIFY_SECRET_ARN": x_origin_verify_secret.secret_arn,
            },
        )

        pipeline_id_resource.add_method(
            "PUT",
            apigateway.LambdaIntegration(put_pipeline_id_handler),
            authorization_type=apigateway.AuthorizationType.COGNITO,
            authorizer=cognito_authorizer,
        )

        # DELETE /api/pipelines/{pipelineId}
        del_pipeline_id_handler = _lambda.Function(
            self,
            "DeletePipelineIdHandler",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="index.handler",
            architecture=lambda_architecture,
            code=_lambda.Code.from_asset(
                "lambdas/api/pipelines/rp_pipeline_id/del_pipeline_id"
            ),
            log_group=api_handler_log_group,
            role=lambda_execution_role,
            timeout=Duration.seconds(30),
            environment={
                "X_ORIGIN_VERIFY_SECRET_ARN": x_origin_verify_secret.secret_arn,
            },
        )

        pipeline_id_resource.add_method(
            "DELETE",
            apigateway.LambdaIntegration(del_pipeline_id_handler),
            authorization_type=apigateway.AuthorizationType.COGNITO,
            authorizer=cognito_authorizer,
        )

        self.rest_api_id = rest_api.rest_api_id
