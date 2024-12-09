from aws_cdk import (
    Stack,
    aws_apigateway as apigateway,
    aws_cognito as cognito,
    aws_lambda as lambda_,
    aws_iam as iam,
    aws_logs as logs,
    CfnOutput,
    Duration,
    RemovalPolicy,
)
from constructs import Construct


class ApiAuthStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Create Cognito User Pool
        user_pool = cognito.UserPool(
            self,
            "UserPool",
            user_pool_name="MyAppUserPool",
            self_sign_up_enabled=True,
            sign_in_aliases=cognito.SignInAliases(email=True),
            auto_verify=cognito.AutoVerifiedAttrs(email=True),
            password_policy=cognito.PasswordPolicy(
                min_length=8,
                require_lowercase=True,
                require_numbers=True,
                require_symbols=True,
                require_uppercase=True,
            ),
            removal_policy=RemovalPolicy.DESTROY,
        )

        # Create User Pool Client
        user_pool_client = user_pool.add_client(
            "MyAppClient",
            generate_secret=False,
            auth_flows=cognito.AuthFlow(
                user_password=True,
                user_srp=True,
                custom=True,
                admin_user_password=True,
            ),
            prevent_user_existence_errors=True,
        )

        # Create Lambda Layer for Powertools
        powertools_layer = lambda_.LayerVersion.from_layer_version_arn(
            self,
            "PowertoolsLayer",
            # Replace with the latest layer ARN for your region
            layer_version_arn=f"arn:aws:lambda:{self.region}:017000801446:layer:AWSLambdaPowertoolsPython:33",
        )

        # Create Custom Authorizer Lambda
        authorizer_lambda = lambda_.Function(
            self,
            "CustomAuthorizerLambda",
            runtime=lambda_.Runtime.PYTHON_3_9,
            handler="index.handler",
            code=lambda_.Code.from_asset("lambda"),
            layers=[powertools_layer],
            environment={
                "USER_POOL_ID": user_pool.user_pool_id,
                "USER_POOL_CLIENT_ID": user_pool_client.user_pool_client_id,
                "POWERTOOLS_SERVICE_NAME": "custom-authorizer",
                "POWERTOOLS_METRICS_NAMESPACE": "CustomAuthorizer",
                "LOG_LEVEL": "INFO",
            },
            timeout=Duration.seconds(10),
            tracing=lambda_.Tracing.ACTIVE,
            log_retention=logs.RetentionDays.ONE_WEEK,
        )

        # Grant permissions to the authorizer lambda
        authorizer_lambda.add_to_role_policy(
            iam.PolicyStatement(actions=["apigateway:GET"], resources=["*"])
        )

        # Create API Gateway
        api = apigateway.RestApi(
            self,
            "MyApi",
            rest_api_name="MyApi",
            deploy_options=apigateway.StageOptions(
                stage_name="prod",
                throttling_rate_limit=5,
                throttling_burst_limit=10,
                metrics_enabled=True,
                logging_level=apigateway.MethodLoggingLevel.INFO,
                data_trace_enabled=True,
                tracing_enabled=True,
            ),
        )

        # Create Custom Authorizer
        auth = apigateway.TokenAuthorizer(
            self,
            "CustomAuthorizer",
            handler=authorizer_lambda,
            results_cache_ttl=Duration.minutes(5),
        )

        # Create Usage Plan
        plan = api.add_usage_plan(
            "StandardUsagePlan",
            name="StandardUsagePlan",
            description="Standard usage plan for API access",
            throttle=apigateway.ThrottleSettings(rate_limit=5, burst_limit=10),
            quota=apigateway.QuotaSettings(limit=1000, period=apigateway.Period.MONTH),
        )

        # Create API Key
        api_key = api.add_api_key(
            "SystemApiKey",
            api_key_name="SystemApiKey",
            description="API Key for system-to-system access",
        )

        # Associate API Key with Usage Plan
        plan.add_api_key(api_key)
        plan.add_api_stage(stage=api.deployment_stage)

        # Create single endpoint that accepts both auth methods
        items = api.root.add_resource("items")

        # GET Method with custom authorizer
        items.add_method(
            "GET",
            apigateway.MockIntegration(
                integration_responses=[
                    {
                        "statusCode": "200",
                        "responseTemplates": {
                            "application/json": '{"message": "Success", "auth_type": "$context.authorizer.auth_type"}'
                        },
                    }
                ],
                request_templates={"application/json": '{"statusCode": 200}'},
            ),
            method_responses=[
                {
                    "statusCode": "200",
                    "responseModels": {
                        "application/json": apigateway.Model.EMPTY_MODEL
                    },
                }
            ],
            authorizer=auth,
            authorization_type=apigateway.AuthorizationType.CUSTOM,
        )

        # Stack Outputs
        CfnOutput(self, "UserPoolId", value=user_pool.user_pool_id)
        CfnOutput(self, "UserPoolClientId", value=user_pool_client.user_pool_client_id)
        CfnOutput(self, "ApiUrl", value=api.url)
