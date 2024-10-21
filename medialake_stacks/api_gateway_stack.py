from aws_cdk import (
    Stack,
    aws_apigateway as apigateway,
    aws_lambda as lambda_,
    aws_logs as logs,
    aws_iam as iam,
    aws_dynamodb as dynamodb,
    aws_secretsmanager as secretsmanager,
    RemovalPolicy,
    Duration,
)
from aws_cdk.aws_lambda_python_alpha import PythonFunction
from constructs import Construct


class ApiGatewayStack(Stack):
    def __init__(
        self, scope: Construct, id: str, user_pool, distribution, **kwargs
    ) -> None:
        super().__init__(scope, id, **kwargs)

        # DynamoDB table
        jobs_table = dynamodb.Table(
            self,
            "Jobs",
            partition_key=dynamodb.Attribute(
                name="jobId", type=dynamodb.AttributeType.STRING
            ),
            stream=dynamodb.StreamViewType.NEW_IMAGE,
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            encryption=dynamodb.TableEncryption.AWS_MANAGED,
            removal_policy=RemovalPolicy.DESTROY,
        )

        # Secret for X-Origin-Verify
        x_origin_verify_secret = secretsmanager.Secret(
            self,
            "X-Origin-Verify-Secret",
            removal_policy=RemovalPolicy.DESTROY,
            generate_secret_string=secretsmanager.SecretStringGenerator(
                exclude_punctuation=True,
                generate_string_key="headerValue",
                secret_string_template="{}",
            ),
        )

        # Create multiple Lambda functions
        v1_handler = self.create_lambda_function("V1Handler", "lambdas/v1_handler")
        app_handler = self.create_lambda_function("AppHandler", "lambdas/app_handler")

        # API Gateway
        rest_api_log_group = logs.LogGroup(
            self,
            "IntelligentQCRestAPI",
            removal_policy=RemovalPolicy.DESTROY,
        )

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
                stage_name="api",
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

        cognito_authorizer = apigateway.CognitoUserPoolsAuthorizer(
            self,
            "ApiGatewayCognitoAuthorizer",
            identity_source="method.request.header.Authorization",
            cognito_user_pools=[user_pool],
        )

        # API resources and methods
        v1_resource = rest_api.root.add_resource("v1")
        api_resource = rest_api.root.add_resource("app")

        v1_proxy_resource = v1_resource.add_proxy(
            default_method_options=apigateway.MethodOptions(
                authorization_type=apigateway.AuthorizationType.COGNITO,
                authorizer=cognito_authorizer,
            ),
            any_method=False,
        )

        api_proxy_resource = api_resource.add_proxy(
            default_method_options=apigateway.MethodOptions(api_key_required=True),
            any_method=False,
        )

        v1_proxy_resource.add_method(
            "ANY",
            apigateway.LambdaIntegration(v1_handler, proxy=True),
        )

        api_proxy_resource.add_method(
            "ANY",
            apigateway.LambdaIntegration(app_handler, proxy=True),
        )

    def create_lambda_function(
        self, function_name: str, entry_path: str
    ) -> PythonFunction:
        handler_role = iam.Role(
            self,
            f"{function_name}ExecutionRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
        )

        handler_log_group = logs.LogGroup(
            self, f"{function_name}LogGroup", removal_policy=RemovalPolicy.DESTROY
        )

        handler_role.add_to_principal_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["logs:CreateLogStream", "logs:PutLogEvents"],
                resources=[handler_log_group.log_group_arn],
            )
        )

        handler = PythonFunction(
            self,
            function_name,
            entry=entry_path,
            handler="handler",
            role=handler_role,
            log_group=handler_log_group,
            runtime=lambda_.Runtime.PYTHON_3_11,
            timeout=Duration.minutes(5),
            memory_size=128,
            tracing=lambda_.Tracing.ACTIVE,
            environment={
                "X_ORIGIN_VERIFY_SECRET_ARN": x_origin_verify_secret.secret_arn,
            },
        )

        x_origin_verify_secret.grant_read(handler)
        jobs_table.grant_read_write_data(handler)

        return handler
