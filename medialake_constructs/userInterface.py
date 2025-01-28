import os
import shutil
import sys
import subprocess

from aws_cdk import (
    aws_s3 as s3,
    aws_logs as logs,
    aws_cloudfront as cloudfront,
    aws_s3_deployment as s3deploy,
    aws_secretsmanager as secretsmanager,
    aws_cloudfront_origins as origins,
    aws_wafv2 as wafv2,
    Duration,
    RemovalPolicy,
    ILocalBundling,
    BundlingOptions,
    DockerImage,
    Stack,
)
from constructs import Construct

from dataclasses import dataclass, field
from medialake_constructs.shared_constructs.s3bucket import S3Bucket, S3BucketProps
from typing import List, Dict, Optional
from config import config
import jsii


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
    cognito_user_pool_id: str
    cognito_user_pool_client_id: str
    cognito_identity_pool: str
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
                bucket_name=f"{config.global_prefix}-user-interface-{config.account_id}-{config.environment}",
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
            log_group_name=f"aws-waf-logs-{config.global_prefix}-{config.primary_region}-{config.account_id}-user-interface-waf-logs",
            retention=logs.RetentionDays.ONE_WEEK,
            removal_policy=RemovalPolicy.DESTROY,
        )

        self.user_interface_waf_acl = wafv2.CfnWebACL(
            self,
            "CloudFrontWAF",
            default_action={"allow": {}},
            scope="CLOUDFRONT",
            visibility_config={
                "sampledRequestsEnabled": True,
                "cloudWatchMetricsEnabled": True,
                "metricName": "CloudFrontWAFMetrics",
            },
            rules=[
                {
                    "name": "AWSManagedRulesCommonRuleSet",
                    "priority": 1,
                    "overrideAction": {"none": {}},
                    "statement": {
                        "managedRuleGroupStatement": {
                            "vendorName": "AWS",
                            "name": "AWSManagedRulesCommonRuleSet",
                        }
                    },
                    "visibilityConfig": {
                        "sampledRequestsEnabled": True,
                        "cloudWatchMetricsEnabled": True,
                        "metricName": "AWSManagedRulesCommonRuleSetMetric",
                    },
                },
                {
                    "name": "AWSManagedRulesKnownBadInputsRuleSet",
                    "priority": 2,
                    "overrideAction": {"none": {}},
                    "statement": {
                        "managedRuleGroupStatement": {
                            "vendorName": "AWS",
                            "name": "AWSManagedRulesKnownBadInputsRuleSet",
                        }
                    },
                    "visibilityConfig": {
                        "sampledRequestsEnabled": True,
                        "cloudWatchMetricsEnabled": True,
                        "metricName": "KnownBadInputsRuleSetMetric",
                    },
                },
                {
                    "name": "AWSManagedRulesSQLiRuleSet",
                    "priority": 3,
                    "overrideAction": {"none": {}},
                    "statement": {
                        "managedRuleGroupStatement": {
                            "vendorName": "AWS",
                            "name": "AWSManagedRulesSQLiRuleSet",
                        }
                    },
                    "visibilityConfig": {
                        "cloudWatchMetricsEnabled": True,
                        "metricName": "SQLiRuleSetMetric",
                        "sampledRequestsEnabled": True,
                    },
                },
            ],
        )

        self.user_interface_waf_logging_config = wafv2.CfnLoggingConfiguration(
            self,
            "WafLoggingConfig",
            resource_arn=self.user_interface_waf_acl.attr_arn,
            log_destination_configs=[self.user_interface_waf_log_group.log_group_arn],
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
                        "style-src 'self' 'unsafe-inline'; "
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

        self.cloudfront_distribution = cloudfront.Distribution(
            self,
            "MediaLakeDistrubtion",
            web_acl_id=self.user_interface_waf_acl.attr_arn,
            default_behavior=cloudfront.BehaviorOptions(
                origin=origins.S3BucketOrigin.with_origin_access_control(
                    medialake_ui_s3_bucket.bucket,
                ),
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
                    origin=origins.S3BucketOrigin.with_origin_access_control(
                        medialake_ui_s3_bucket.bucket,
                    ),
                    viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                    allowed_methods=cloudfront.AllowedMethods.ALLOW_GET_HEAD_OPTIONS,
                    cached_methods=cloudfront.CachedMethods.CACHE_GET_HEAD_OPTIONS,
                    cache_policy=static_assets_cache_policy,
                    origin_request_policy=cloudfront.OriginRequestPolicy.CORS_S3_ORIGIN,
                    response_headers_policy=ui_response_headers_policy,
                    compress=True,
                ),
                "*.css": cloudfront.BehaviorOptions(
                    origin=origins.S3BucketOrigin.with_origin_access_control(
                        medialake_ui_s3_bucket.bucket,
                    ),
                    viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                    allowed_methods=cloudfront.AllowedMethods.ALLOW_GET_HEAD_OPTIONS,
                    cached_methods=cloudfront.CachedMethods.CACHE_GET_HEAD_OPTIONS,
                    cache_policy=static_assets_cache_policy,
                    origin_request_policy=cloudfront.OriginRequestPolicy.CORS_S3_ORIGIN,
                    response_headers_policy=ui_response_headers_policy,
                    compress=True,
                ),
                f"/{config.api_path}/*": cloudfront.BehaviorOptions(
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
            geo_restriction=cloudfront.GeoRestriction.allowlist("US", "GB"),
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

        # Get SAML provider if configured
        saml_provider = next(
            (
                provider
                for provider in config.authZ.identity_providers
                if provider.identity_provider_method == "saml"
            ),
            None,
        )

        # S3 Deployment
        exports_asset = s3deploy.Source.json_data(
            "aws-exports.json",
            {
                "region": scope.region,
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
                        "domain": f"{config.resource_prefix}-{config.environment}.auth.{scope.region}.amazoncognito.com",
                        "loginWith": {
                            "username": True,
                            "email": True,
                            "oauth": {
                                "domain": f"{config.resource_prefix}-{config.environment}.auth.{scope.region}.amazoncognito.com",
                                "scopes": ["email", "openid", "profile"],
                                "responseType": "code",
                                "redirectSignIn": f"https://{self.cloudfront_distribution.distribution_domain_name}",
                                "redirectSignOut": f"https://{self.cloudfront_distribution.distribution_domain_name}/sign-in",
                            },
                        },
                    },
                },
                "API": {
                    "REST": {
                        "RestApi": {
                            "endpoint": f"https://{self.cloudfront_distribution.distribution_domain_name}/{config.api_path}",
                        },
                    },
                },
            },
        )

        # deploy assets to S3
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
            sources=[asset, exports_asset],
            destination_bucket=medialake_ui_s3_bucket.bucket,
            distribution=self.cloudfront_distribution,
            distribution_paths=["/*"],
            memory_limit=1024,
        )

    @property
    def user_interface_url(self) -> str:
        return f"https://{self.cloudfront_distribution.distribution_domain_name}"
