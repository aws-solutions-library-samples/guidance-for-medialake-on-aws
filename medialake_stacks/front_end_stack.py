from aws_cdk import (
    Stack,
    aws_apigateway as apigateway,
    aws_cloudfront as cf,
    aws_s3 as s3,
    aws_dynamodb as dynamodb,
    aws_s3_deployment as s3deploy,
    aws_secretsmanager as secretsmanager,
    aws_cognito as cognito,
    aws_lambda as lambda_,
    aws_logs as logs,
    aws_cloudfront as cloudfront,
    aws_iam as iam,
    aws_s3 as s3,
    RemovalPolicy,
    CfnOutput,
    Duration,
    ILocalBundling,
    BundlingOptions,
    DockerImage,
)

import os
from aws_cdk.aws_lambda_python_alpha import PythonFunction


from constructs import Construct

from aws_cdk.aws_cognito_identitypool_alpha import (
    IdentityPool,
    UserPoolAuthenticationProvider,
    IdentityPoolAuthenticationProviders,
)


@jsii.implements(ILocalBundling)
class MyLocalBundling:
    def __init__(self, app_path: str, build_path: str):
        self.app_path = app_path
        self.build_path = build_path

    def try_bundle(self, output_dir: str, image) -> bool:
        try:
            # Define options for subprocess
            options = {"cwd": self.app_path, "env": os.environ.copy(), "shell": True}

            subprocess.check_call("npm install", **options)
            subprocess.check_call("npm run build", **options)

            # Copy the build output to the expected location
            # Check if the 'build' directory exists
            build_path = os.path.join(self.app_path, "build")
            if os.path.exists(build_path):
                dist_path = build_path
                print(f"Using 'build' directory at: {dist_path}")
            else:
                # Check if the 'dist' directory exists
                dist_path = os.path.join(self.app_path, "dist")
                if os.path.exists(dist_path):
                    print(f"Using 'dist' directory at: {dist_path}")
                else:
                    print("Neither 'build' nor 'dist' directory exists.")
                    sys.exit()

            for item in os.listdir(dist_path):
                s = os.path.join(dist_path, item)
                d = os.path.join(output_dir, item)
                if os.path.isdir(s):
                    shutil.copytree(s, d, dirs_exist_ok=True)
                else:
                    shutil.copy2(s, d)

            return True
        except subprocess.CalledProcessError as e:
            print(f"Bundling failed: {e}")
            return False


class FrontEndStack(Stack):
    def __init__(self, scope: Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        app_path = os.path.join(os.path.dirname(__file__), "../user-interface")
        build_path = os.path.join(app_path, "dist")

        user_interface_bucket = s3.Bucket(
            self,
            "UserInterfaceBucket",
            removal_policy=RemovalPolicy.DESTROY,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            auto_delete_objects=True,
            website_index_document="index.html",
            website_error_document="index.html",
        )

        user_pool = cognito.UserPool(
            self,
            "UserPool",
            removal_policy=RemovalPolicy.DESTROY,
            self_sign_up_enabled=False,
            auto_verify=cognito.AutoVerifiedAttrs(email=True, phone=True),
            sign_in_aliases=cognito.SignInAliases(email=True),
        )

        user_pool_client = user_pool.add_client(
            "UserPoolClient",
            generate_secret=False,
            auth_flows=cognito.AuthFlow(
                admin_user_password=True,
                user_password=True,
                user_srp=True,
            ),
        )

        identity_pool = IdentityPool(
            self,
            "IdentityPool",
            authentication_providers=IdentityPoolAuthenticationProviders(
                user_pools=[
                    UserPoolAuthenticationProvider(
                        user_pool=user_pool, user_pool_client=user_pool_client
                    )
                ],
            ),
        )

        origin_access_identity = cf.OriginAccessIdentity(self, "S3OAI")
        user_interface_bucket.grant_read(origin_access_identity)

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

        # DynamoDB to store job details and status
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

        api_handler_role.add_to_principal_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["logs:CreateLogStream", "logs:PutLogEvents"],
                resources=[api_handler_log_group.log_group_arn],
            )
        )

        api_handler = PythonFunction(
            self,
            "ApiHandler",
            entry="lambdas/api_handler",
            handler="handler",
            role=api_handler_role,
            log_group=api_handler_log_group,
            runtime=lambda_.Runtime.PYTHON_3_11,
            architecture=lambda_architecture,
            timeout=Duration.minutes(5),
            memory_size=128,
            tracing=lambda_.Tracing.ACTIVE,
            layers=[powertools_layer],
            environment={
                "X_ORIGIN_VERIFY_SECRET_ARN": x_origin_verify_secret.secret_arn,
            },
        )

        x_origin_verify_secret.grant_read(api_handler)
        jobs_table.grant_read_write_data(api_handler)

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

        ## Roles for get status and submit job
        rest_api_get_status_role = iam.Role(
            self,
            "GetStatusExecutionRole",
            assumed_by=iam.ServicePrincipal("apigateway.amazonaws.com"),
        )
        rest_api_get_status_role.add_to_principal_policy(
            iam.PolicyStatement(
                actions=["lambda:InvokeFunction"],
                resources=["*"],
                effect=iam.Effect.ALLOW,
            )
        )

        ## API resources for each API domain
        v1_resource = rest_api.root.add_resource("v1")
        api_resource = rest_api.root.add_resource("app")

        ## Proxy resources for each API domain
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

        distribution = cloudfront.CloudFrontWebDistribution(
            self,
            "Distribution",
            origin_configs=[
                cloudfront.SourceConfiguration(
                    s3_origin_source=cloudfront.S3OriginConfig(
                        s3_bucket_source=user_interface_bucket,
                        origin_access_identity=origin_access_identity,
                    ),
                    behaviors=[cloudfront.Behavior(is_default_behavior=True)],
                ),
                cloudfront.SourceConfiguration(
                    custom_origin_source=cloudfront.CustomOriginConfig(
                        domain_name=f"{rest_api.rest_api_id}.execute-api.{self.region}.amazonaws.com",
                        origin_protocol_policy=cloudfront.OriginProtocolPolicy.HTTPS_ONLY,
                        origin_headers={
                            "X-Origin-Verify": x_origin_verify_secret.secret_value_from_json(
                                "headerValue"
                            ).unsafe_unwrap()
                        },
                    ),
                    behaviors=[
                        cloudfront.Behavior(
                            path_pattern="/api/*",
                            allowed_methods=cloudfront.CloudFrontAllowedMethods.ALL,
                            cached_methods=cloudfront.CloudFrontAllowedCachedMethods.GET_HEAD,
                            compress=False,
                            forwarded_values=cloudfront.CfnDistribution.ForwardedValuesProperty(
                                query_string=True,
                                headers=[
                                    "x-api-key",
                                    "Referer",
                                    "Origin",
                                    "Authorization",
                                    "Content-Type",
                                    "x-forwarded-user",
                                    "Access-Control-Request-Headers",
                                    "Access-Control-Request-Method",
                                ],
                            ),
                            default_ttl=Duration.seconds(0),
                            is_default_behavior=False,
                            max_ttl=Duration.minutes(30),
                            viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.HTTPS_ONLY,
                        ),
                    ],
                ),
            ],
            price_class=cloudfront.PriceClass.PRICE_CLASS_ALL,
            error_configurations=[
                cloudfront.CfnDistribution.CustomErrorResponseProperty(
                    error_code=404,
                    error_caching_min_ttl=0,
                    response_code=200,
                    response_page_path="/index.html",
                )
            ],
            default_root_object="index.html",
        )

        ## Proxy methods for each API domain

        v1_proxy_resource.add_method(
            "ANY",
            apigateway.LambdaIntegration(api_handler, proxy=True),
        )

        api_proxy_resource.add_method(
            "ANY",
            apigateway.LambdaIntegration(api_handler, proxy=True),
        )

        exports_asset = s3deploy.Source.json_data(
            "aws-exports.json",
            {
                "region": self.region,
                "Auth": {
                    "Cognito": {
                        "userPoolClientId": user_pool_client.user_pool_client_id,
                        "userPoolId": user_pool.user_pool_id,
                        "identityPoolId": identity_pool.identity_pool_id,
                    },
                },
                "API": {
                    "REST": {
                        "RestApi": {
                            "endpoint": f"https://{distribution.distribution_domain_name}/api/v1",
                        },
                    },
                },
            },
        )

        asset = s3deploy.Source.asset(
            app_path,
            bundling=BundlingOptions(
                image=DockerImage.from_registry(
                    "public.ecr.aws/sam/build-nodejs18.x:latest"
                ),
                command=[
                    "sh",
                    "-c",
                    "npm --cache /tmp/.npm install && npm --cache /tmp/.npm run build && cp -aur /asset-input/dist/* /asset-output/",
                ],
                local=MyLocalBundling(app_path, build_path),
            ),
        )

        s3deploy.BucketDeployment(
            self,
            "UserInterfaceDeployment",
            sources=[asset, exports_asset],
            destination_bucket=user_interface_bucket,
            distribution=distribution,
            distribution_paths=["/*"],
        )

        CfnOutput(
            self,
            "UserInterfaceDomainName",
            value=f"https://{distribution.distribution_domain_name}",
        )
