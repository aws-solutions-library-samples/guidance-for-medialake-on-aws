import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import jsii
from aws_cdk import (
    BundlingOptions,
    DockerImage,
    Duration,
    ILocalBundling,
    RemovalPolicy,
    Stack,
)
from aws_cdk import aws_cloudfront as cloudfront
from aws_cdk import aws_cloudfront_origins as origins
from aws_cdk import aws_iam as iam
from aws_cdk import aws_logs as logs
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_s3_deployment as s3deploy
from aws_cdk import aws_secretsmanager as secretsmanager
from aws_cdk import custom_resources as cr
from constructs import Construct

from config import config
from medialake_constructs.shared_constructs.s3bucket import S3Bucket, S3BucketProps


@jsii.implements(ILocalBundling)
class LocalBundling:
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
            if os.path.exists(self.build_path):
                dist_path = self.build_path
                print(f"Using 'build' directory at: {dist_path}")
            else:
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


@dataclass
class UIConstructProps:
    access_log_bucket: s3.IBucket
    api_gateway_rest_id: str
    api_gateway_stage: str
    cognito_user_pool_id: str
    cognito_user_pool_client_id: str
    cloudfront_waf_acl_arn: str
    cognito_identity_pool: str
    cognito_domain_prefix: str
    cognito_construct: Optional[Construct] = None
    app_path: str = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "medialake_user_interface"
    )
    removal_policy: RemovalPolicy = RemovalPolicy.DESTROY
    block_public_access: s3.BlockPublicAccess = s3.BlockPublicAccess.BLOCK_ALL
    auto_delete_objects: bool = True
    website_index_document: str = "index.html"
    website_error_document: str = "index.html"
    price_class: cloudfront.PriceClass = cloudfront.PriceClass.PRICE_CLASS_ALL
    error_response_code: int = 404
    error_response_page_path: str = "/index.html"
    error_caching_min_ttl: int = 0
    distribution_default_root_object: str = "index.html"
    generate_secret_string_key: str = "headerValue"
    exclude_punctuation: bool = True
    origin_headers: Dict[str, str] = field(
        default_factory=lambda: {
            "x-api-key",
            "Referer",
            "Origin",
            "Authorization",
            "Content-Type",
            "x-forwarded-user",
            "Access-Control-Request-Headers",
            "Access-Control-Request-Method",
            "Access-Control-Allow-Origin",
        }
    )
    max_ttl_minutes: int = 30
    command: List[str] = field(
        default_factory=lambda: [
            "sh",
            "-c",
            "npm --cache /tmp/.npm install && npm --cache /tmp/.npm run build && cp -aur /asset-input/dist/* /asset-output/",
        ]
    )
    docker_image: str = "public.ecr.aws/sam/build-nodejs22.x:latest"


class UIConstruct(Construct):

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        props: UIConstructProps,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        stack = Stack.of(self)
        build_path = os.path.join(props.app_path, "dist")

        medialake_ui_s3_bucket = S3Bucket(
            self,
            "MediaLakeUserInterfaceBucket",
            props=S3BucketProps(
                bucket_name=f"{config.resource_prefix}-user-interface-{stack.account}-{config.environment}",
                website_index_document=props.website_index_document,
                website_error_document=props.website_error_document,
            ),
        )

        x_origin_verify_secret = secretsmanager.Secret(
            self,
            "X-Origin-Verify-Secret",
            removal_policy=props.removal_policy,
            generate_secret_string=secretsmanager.SecretStringGenerator(
                exclude_punctuation=props.exclude_punctuation,
                generate_string_key=props.generate_secret_string_key,
                secret_string_template="{}",
            ),
        )

        self.user_interface_waf_log_group = logs.LogGroup(
            self,
            "WafLogGroup",
            log_group_name=f"aws-waf-logs-{config.resource_prefix}-{stack.region}-{stack.account}-user-interface-waf-logs",
            retention=logs.RetentionDays.ONE_WEEK,
            removal_policy=RemovalPolicy.DESTROY,
        )

        # Enhanced security headers policy
        ui_response_headers_policy = cloudfront.ResponseHeadersPolicy(
            self,
            "UISecurityHeadersPolicy",
            security_headers_behavior=cloudfront.ResponseSecurityHeadersBehavior(
                content_security_policy={
                    "content_security_policy": (
                        "default-src 'self'; "
                        f"script-src 'self' 'unsafe-inline' 'unsafe-eval' https://*.amazonaws.com https://*.amazoncognito.com{' http://localhost:* http://127.0.0.1:*' if config.environment == 'dev' else ''}; "
                        "style-src 'self' 'unsafe-inline' chrome: resource:; "
                        "style-src-attr 'self' 'unsafe-inline'; "
                        "img-src 'self' data: https: blob:; "
                        "font-src 'self' data:; "
                        "media-src 'self' blob: data: https://*.amazonaws.com; "
                        f"connect-src 'self' https://*.amazonaws.com https://*.amazoncognito.com{' http://localhost:* http://127.0.0.1:*' if config.environment == 'dev' else ''}; "
                        "frame-ancestors 'none'; "
                        "base-uri 'self'; "
                        "form-action 'self'; "
                        "object-src 'none'"
                    ),
                    "override": True,
                },
                strict_transport_security={
                    "override": True,
                    "access_control_max_age": Duration.seconds(31536000),
                    "include_subdomains": True,
                    "preload": True,
                },
                content_type_options={"override": True},
                frame_options={
                    "frame_option": cloudfront.HeadersFrameOption.DENY,
                    "override": True,
                },
                xss_protection={
                    "protection": True,
                    "mode_block": True,
                    "override": True,
                },
                referrer_policy={
                    "referrer_policy": cloudfront.HeadersReferrerPolicy.STRICT_ORIGIN_WHEN_CROSS_ORIGIN,
                    "override": True,
                },
            ),
            custom_headers_behavior=cloudfront.ResponseCustomHeadersBehavior(
                custom_headers=[
                    cloudfront.ResponseCustomHeader(
                        header="Permissions-Policy",
                        value="camera=(), microphone=(), geolocation=()",
                        override=True,
                    ),
                ]
            ),
            cors_behavior=cloudfront.ResponseHeadersCorsBehavior(
                access_control_allow_credentials=False,
                access_control_allow_headers=[
                    "Authorization",
                    "authorization",
                    "Content-Type",
                    "X-Api-Key",
                    "X-Amz-Date",
                    "X-Amz-Security-Token",
                    "X-Forwarded-User",
                ],
                access_control_allow_methods=[
                    "GET",
                    "HEAD",
                    "POST",
                    "DELETE",
                    "OPTIONS",
                ],
                access_control_allow_origins=["*"],
                origin_override=True,
                access_control_expose_headers=["*"],
                access_control_max_age=Duration.seconds(7200),
            ),
        )

        api_response_headers_policy = cloudfront.ResponseHeadersPolicy(
            self,
            "APISecurityHeadersPolicy",
            security_headers_behavior=cloudfront.ResponseSecurityHeadersBehavior(
                content_security_policy={
                    "content_security_policy": (
                        "default-src 'self'; "
                        "script-src 'self' 'unsafe-inline' 'unsafe-eval' http://localhost:5173; "
                        "style-src 'self' 'unsafe-inline'; "
                        "img-src 'self' data: https: blob:; "
                        "font-src 'self' data:; "
                        "connect-src 'self' http://localhost:5173 https://*.amazonaws.com https://*.amazoncognito.com; "
                        "frame-ancestors 'none'; "
                        "base-uri 'self'; "
                        "form-action 'self'; "
                        "object-src 'none'; "
                        "upgrade-insecure-requests;"
                    ),
                    "override": True,
                },
                strict_transport_security={
                    "override": True,
                    "access_control_max_age": Duration.seconds(31536000),
                    "include_subdomains": True,
                    "preload": True,
                },
                content_type_options={"override": True},
                frame_options={
                    "frame_option": cloudfront.HeadersFrameOption.DENY,
                    "override": True,
                },
                xss_protection={
                    "protection": True,
                    "mode_block": True,
                    "override": True,
                },
                referrer_policy={
                    "referrer_policy": cloudfront.HeadersReferrerPolicy.STRICT_ORIGIN_WHEN_CROSS_ORIGIN,
                    "override": True,
                },
            ),
            custom_headers_behavior=cloudfront.ResponseCustomHeadersBehavior(
                custom_headers=[
                    cloudfront.ResponseCustomHeader(
                        header="Permissions-Policy",
                        value="camera=(), microphone=(), geolocation=()",
                        override=True,
                    ),
                ]
            ),
            cors_behavior=cloudfront.ResponseHeadersCorsBehavior(
                access_control_allow_credentials=False,
                access_control_allow_headers=[
                    "Authorization",
                    "authorization",
                    "Content-Type",
                    "X-Api-Key",
                    "X-Amz-Date",
                    "X-Amz-Security-Token",
                    "X-Forwarded-User",
                    "Cache-Control",
                    "Pragma",
                    "Expires",
                ],
                access_control_allow_methods=[
                    "GET",
                    "HEAD",
                    "POST",
                    "DELETE",
                    "OPTIONS",
                ],
                access_control_allow_origins=["*"],
                origin_override=True,
                access_control_expose_headers=["*"],
                access_control_max_age=Duration.seconds(7200),
            ),
        )

        # Create a custom cache policy for static assets
        static_assets_cache_policy = cloudfront.CachePolicy(
            self,
            "StaticAssetsCachePolicy",
            comment="Cache policy for static assets (JS, CSS, images)",
            default_ttl=Duration.days(1),
            min_ttl=Duration.minutes(1),
            max_ttl=Duration.days(365),
            cookie_behavior=cloudfront.CacheCookieBehavior.none(),
            header_behavior=cloudfront.CacheHeaderBehavior.none(),
            query_string_behavior=cloudfront.CacheQueryStringBehavior.none(),
            enable_accept_encoding_gzip=True,
            enable_accept_encoding_brotli=True,
        )

        # Create a shared CF Origin for static assets (S3)
        s3_orig = origins.S3BucketOrigin.with_origin_access_control(
            medialake_ui_s3_bucket.bucket,
        )

        self.cloudfront_distribution = cloudfront.Distribution(
            self,
            "MediaLakeDistrubtion",
            web_acl_id=props.cloudfront_waf_acl_arn,
            default_behavior=cloudfront.BehaviorOptions(
                origin=s3_orig,
                response_headers_policy=ui_response_headers_policy,
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                allowed_methods=cloudfront.AllowedMethods.ALLOW_GET_HEAD_OPTIONS,
                cached_methods=cloudfront.CachedMethods.CACHE_GET_HEAD_OPTIONS,
                cache_policy=static_assets_cache_policy,
                origin_request_policy=cloudfront.OriginRequestPolicy.CORS_S3_ORIGIN,
                compress=True,
            ),
            additional_behaviors={
                "*.js": cloudfront.BehaviorOptions(
                    origin=s3_orig,
                    viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                    allowed_methods=cloudfront.AllowedMethods.ALLOW_GET_HEAD_OPTIONS,
                    cached_methods=cloudfront.CachedMethods.CACHE_GET_HEAD_OPTIONS,
                    cache_policy=static_assets_cache_policy,
                    origin_request_policy=cloudfront.OriginRequestPolicy.CORS_S3_ORIGIN,
                    response_headers_policy=ui_response_headers_policy,
                    compress=True,
                ),
                "*.css": cloudfront.BehaviorOptions(
                    origin=s3_orig,
                    viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                    allowed_methods=cloudfront.AllowedMethods.ALLOW_GET_HEAD_OPTIONS,
                    cached_methods=cloudfront.CachedMethods.CACHE_GET_HEAD_OPTIONS,
                    cache_policy=static_assets_cache_policy,
                    origin_request_policy=cloudfront.OriginRequestPolicy.CORS_S3_ORIGIN,
                    response_headers_policy=ui_response_headers_policy,
                    compress=True,
                ),
                f"/{props.api_gateway_stage}/*": cloudfront.BehaviorOptions(
                    origin=origins.HttpOrigin(
                        f"{props.api_gateway_rest_id}.execute-api.{scope.region}.amazonaws.com",
                        origin_ssl_protocols=[cloudfront.OriginSslPolicy.TLS_V1_2],
                        protocol_policy=cloudfront.OriginProtocolPolicy.HTTPS_ONLY,
                    ),
                    cache_policy=cloudfront.CachePolicy(
                        self,
                        "APIBehaviorCachePolicy",
                        default_ttl=Duration.seconds(0),
                    ),
                    response_headers_policy=api_response_headers_policy,
                    allowed_methods=cloudfront.AllowedMethods.ALLOW_ALL,
                    origin_request_policy=cloudfront.OriginRequestPolicy.ALL_VIEWER_EXCEPT_HOST_HEADER,
                ),
            },
            minimum_protocol_version=cloudfront.SecurityPolicyProtocol.TLS_V1_2_2021,
            ssl_support_method=cloudfront.SSLMethod.SNI,
            enable_logging=True,
            log_bucket=props.access_log_bucket,
            log_file_prefix="medialake-cloudfront-logs",
            price_class=cloudfront.PriceClass.PRICE_CLASS_100,
            default_root_object=props.distribution_default_root_object,
            # geo_restriction=cloudfront.GeoRestriction.allowlist("US", "GB"),
            error_responses=[
                cloudfront.ErrorResponse(
                    http_status=403,
                    response_http_status=200,
                    response_page_path="/index.html",
                    ttl=Duration.minutes(0),
                ),
                cloudfront.ErrorResponse(
                    http_status=404,
                    response_http_status=200,
                    response_page_path="/index.html",
                    ttl=Duration.minutes(0),
                ),
            ],
        )

        print(f"Cognito domain prefix: {props.cognito_domain_prefix}")
        print(
            f"Cognito domain: {config.resource_prefix}-{config.environment}-{props.cognito_domain_prefix}.auth.{stack.region}.amazoncognito.com"
        )
        # Get SAML provider if configured
        saml_provider = next(
            (
                provider
                for provider in config.authZ.identity_providers
                if provider.identity_provider_method == "saml"
            ),
            None,
        )

        # Check if there's a SAML provider and extract the name safely
        if saml_provider and hasattr(saml_provider, "identity_provider_name"):
            saml_provider.identity_provider_name

        config_content = {
            "region": stack.region,
            "Auth": {
                "identity_providers": [
                    {
                        "identity_provider_method": provider.identity_provider_method,
                        "identity_provider_name": getattr(
                            provider, "identity_provider_name", ""
                        ),
                        "identity_provider_metadata_url": getattr(
                            provider, "identity_provider_metadata_url", ""
                        ),
                    }
                    for provider in config.authZ.identity_providers
                ],
                "Cognito": {
                    "userPoolClientId": props.cognito_user_pool_client_id,
                    "userPoolId": props.cognito_user_pool_id,
                    "identityPoolId": props.cognito_identity_pool,
                    "domain": f"{props.cognito_domain_prefix}.auth.{stack.region}.amazoncognito.com",
                    "loginWith": {
                        "username": True,
                        "email": True,
                        "oauth": {
                            "domain": f"{props.cognito_domain_prefix}.auth.{stack.region}.amazoncognito.com",
                            "scopes": ["email", "openid", "profile"],
                            "responseType": "code",
                            "redirectSignIn": f"https://{self.cloudfront_distribution.distribution_domain_name}/",
                            "redirectSignOut": f"https://{self.cloudfront_distribution.distribution_domain_name}/sign-in",
                        },
                    },
                },
            },
            "API": {
                "REST": {
                    "RestApi": {
                        "endpoint": f"https://{self.cloudfront_distribution.distribution_domain_name}/{props.api_gateway_stage}"
                    }
                }
            },
        }

        config_resource = cr.AwsCustomResource(
            self,
            "ConfigResource",
            on_create=cr.AwsSdkCall(
                service="S3",
                action="putObject",
                parameters={
                    "Bucket": medialake_ui_s3_bucket.bucket.bucket_name,
                    "Key": "aws-exports.json",
                    "Body": json.dumps(config_content),
                    "ContentType": "application/json",
                },
                physical_resource_id=cr.PhysicalResourceId.of(
                    f"{config.resource_prefix}-aws-exports-json"
                ),
            ),
            on_update=cr.AwsSdkCall(
                service="S3",
                action="putObject",
                parameters={
                    "Bucket": medialake_ui_s3_bucket.bucket.bucket_name,
                    "Key": "aws-exports.json",
                    "Body": json.dumps(config_content),
                    "ContentType": "application/json",
                },
                physical_resource_id=cr.PhysicalResourceId.of(
                    f"{config.resource_prefix}-aws-exports-json"
                ),
            ),
            policy=cr.AwsCustomResourcePolicy.from_statements(
                [
                    iam.PolicyStatement(
                        actions=["s3:PutObject"],
                        resources=[
                            medialake_ui_s3_bucket.bucket.arn_for_objects(
                                "aws-exports.json"
                            )
                        ],
                    ),
                    # KMS permissions
                    iam.PolicyStatement(
                        actions=[
                            "kms:Decrypt",
                            "kms:GenerateDataKey",
                            "kms:GenerateDataKeyWithoutPlaintext",
                            "kms:DescribeKey",
                        ],
                        resources=["*"],
                    ),
                ]
            ),
        )

        _ = cr.AwsCustomResource(
            self,
            "UpdateUserPoolClientCallbacks",
            on_update=cr.AwsSdkCall(
                service="CognitoIdentityServiceProvider",
                action="updateUserPoolClient",
                parameters={
                    "UserPoolId": props.cognito_user_pool_id,
                    "ClientId": props.cognito_user_pool_client_id,
                    "CallbackURLs": [
                        f"https://{props.cognito_domain_prefix}.auth.{Stack.of(self).region}.amazoncognito.com/oauth2/idpresponse",
                        f"https://{props.cognito_domain_prefix}.auth.{Stack.of(self).region}.amazoncognito.com/saml2/idpresponse",
                        f"https://{self.cloudfront_distribution.distribution_domain_name}",
                        f"https://{self.cloudfront_distribution.distribution_domain_name}/",
                        f"https://{self.cloudfront_distribution.distribution_domain_name}/sign-in",
                        f"https://localhost:5173",
                        f"https://localhost:5173/",
                        f"https://localhost:5173/login",
                    ],
                    "LogoutURLs": [
                        f"https://{props.cognito_domain_prefix}.auth.{Stack.of(self).region}.amazoncognito.com",
                        f"https://{props.cognito_domain_prefix}.auth.{Stack.of(self).region}.amazoncognito.com/",
                        f"https://{props.cognito_domain_prefix}.auth.{Stack.of(self).region}.amazoncognito.com/sign-in",
                        f"https://{self.cloudfront_distribution.distribution_domain_name}",
                        f"https://{self.cloudfront_distribution.distribution_domain_name}/",
                        f"https://{self.cloudfront_distribution.distribution_domain_name}/sign-in",
                        f"https://localhost:5173",
                        f"https://localhost:5173/",
                        f"https://localhost:5173/login",
                    ],
                    "AllowedOAuthFlows": ["code", "implicit"],
                    "AllowedOAuthScopes": ["email", "openid", "profile"],
                    "AllowedOAuthFlowsUserPoolClient": True,
                    "SupportedIdentityProviders": ["COGNITO"]
                    + [
                        provider.identity_provider_name
                        for provider in config.authZ.identity_providers
                        if provider.identity_provider_method == "saml"
                    ],
                },
                physical_resource_id=cr.PhysicalResourceId.of(
                    f"{config.resource_prefix}-cognito-callback-urls-update"
                ),
            ),
            policy=cr.AwsCustomResourcePolicy.from_sdk_calls(
                resources=cr.AwsCustomResourcePolicy.ANY_RESOURCE
            ),
        )

        # Add dependencies
        config_resource.node.add_dependency(self.cloudfront_distribution)
        config_resource.node.add_dependency(medialake_ui_s3_bucket)

        # deploy assets to S3
        if "CI" in os.environ and "CODEBUILD_BUILD_ID" in os.environ:
            dist_path = Path(props.app_path).parent / "assets/dist"
            asset = s3deploy.Source.asset(str(dist_path))
        else:
            asset = s3deploy.Source.asset(
                props.app_path,
                bundling=BundlingOptions(
                    image=DockerImage.from_registry(props.docker_image),
                    command=props.command,
                    local=LocalBundling(props.app_path, build_path),
                ),
            )

        s3deploy.BucketDeployment(
            self,
            "UserInterfaceDeployment",
            sources=[asset],
            destination_bucket=medialake_ui_s3_bucket.bucket,
            distribution=self.cloudfront_distribution,
            distribution_paths=["/*"],
            memory_limit=1024,
            exclude=["aws-exports.json"],
        )

    @property
    def user_interface_url(self) -> str:
        return f"https://{self.cloudfront_distribution.distribution_domain_name}"
