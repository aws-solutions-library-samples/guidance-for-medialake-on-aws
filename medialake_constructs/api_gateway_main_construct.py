from aws_cdk import (
    aws_apigateway as apigateway,
    aws_logs as logs,
    aws_secretsmanager as secretsmanager,
    Duration,
    RemovalPolicy,
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

        # Create Cognito Authorizer first
        cognito_authorizer = apigateway.CognitoUserPoolsAuthorizer(
            self,
            "CognitoAuthorizer",
            identity_source="method.request.header.Authorization",
            cognito_user_pools=[user_pool],
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
                max_age=Duration.minutes(5),
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
            default_method_options=apigateway.MethodOptions(
                authorization_type=apigateway.AuthorizationType.COGNITO,
                authorizer=cognito_authorizer,
            ),
        )

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

        self.rest_api = rest_api
        self.api_resource = rest_api
        self.cognito_authorizer = cognito_authorizer
        self.x_origin_verify_secret = x_origin_verify_secret
