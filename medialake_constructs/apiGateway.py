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

# from workflowConstructs.lambdaLayers import PowertoolsLayer
# from workflowConstructs.customLambdaLayer import CustomLambdaLayerConstruct
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

        # API handler
        api_handler_role = iam.Role(
            self,
            "CreateJobExecutionRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
        )

        api_handler_role.add_to_principal_policy(
            iam.PolicyStatement(
                actions=["states:StartExecution"],
                resources=["*"],
                effect=iam.Effect.ALLOW,
            )
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

        api_handler = _lambda.Function(
            self,
            "ApiHandler",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="index.handler",
            architecture=lambda_architecture,
            code=_lambda.Code.from_asset("lambdas/api_handler"),
            log_group=api_handler_log_group,
            role=lambda_execution_role,
            timeout=Duration.seconds(30),
            layers=[
                # powertools_layer.layer,
                # opensearchpy_layer.layer,
                # requests_aws4auth_layer.layer,
            ],
            environment={
                "X_ORIGIN_VERIFY_SECRET_ARN": x_origin_verify_secret.secret_arn,
                # "OPENSEARCH_COLLECTION_ENDPOINT": self.props.collection_endpoint,
                "REVIEW_TABLE_NAME": "asset-review",
            },
        )

        # set ddb permissions
        ddb.Table.from_table_name(
            self, "AssetReviewTable", "asset-review"
        ).grant_read_write_data(api_handler)

        # API resources
        api_resource = rest_api.root.add_resource("api")

        # Add new connectors resource and s3list sub-resource
        connectors_resource = api_resource.add_resource("connectors")
        s3list_resource = connectors_resource.add_resource("s3list")

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

        # Create specific route resources instead of using proxy
        reviews_resource = api_resource.add_resource("reviews")
        search_resource = api_resource.add_resource("search")

        # Create separate Lambda functions for different routes
        reviews_handler = _lambda.Function(
            self,
            "ReviewsHandler",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="index.handler",
            architecture=lambda_architecture,
            code=_lambda.Code.from_asset("lambdas/reviews_handler"),
            log_group=api_handler_log_group,
            role=lambda_execution_role,
            timeout=Duration.seconds(30),
            environment={
                "X_ORIGIN_VERIFY_SECRET_ARN": x_origin_verify_secret.secret_arn,
                "REVIEW_TABLE_NAME": "asset-review",
            },
        )

        search_handler = _lambda.Function(
            self,
            "SearchHandler",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="index.handler",
            architecture=lambda_architecture,
            code=_lambda.Code.from_asset("lambdas/search_handler"),
            log_group=api_handler_log_group,
            role=lambda_execution_role,
            timeout=Duration.seconds(30),
            environment={
                "X_ORIGIN_VERIFY_SECRET_ARN": x_origin_verify_secret.secret_arn,
            },
        )

        # Add methods to resources with specific Lambda integrations
        reviews_resource.add_method(
            "GET",
            apigateway.LambdaIntegration(reviews_handler),
            authorization_type=apigateway.AuthorizationType.COGNITO,
            authorizer=cognito_authorizer,
        )

        reviews_resource.add_method(
            "POST",
            apigateway.LambdaIntegration(reviews_handler),
            authorization_type=apigateway.AuthorizationType.COGNITO,
            authorizer=cognito_authorizer,
        )

        search_resource.add_method(
            "POST",
            apigateway.LambdaIntegration(search_handler),
            authorization_type=apigateway.AuthorizationType.COGNITO,
            authorizer=cognito_authorizer,
        )

        self.rest_api_id = rest_api.rest_api_id
