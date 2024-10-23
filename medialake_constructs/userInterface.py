import os
import shutil
import sys
import subprocess
from aws_cdk import (
    aws_s3 as s3,
    aws_cloudfront as cloudfront,
    aws_s3_deployment as s3deploy,
    aws_secretsmanager as secretsmanager,
    Duration,
    RemovalPolicy,
    ILocalBundling,
    BundlingOptions,
    DockerImage,
)
from constructs import Construct
from dataclasses import dataclass, field
from typing import List, Dict

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

            # subprocess.check_call("rm -f package-lock.json && rm -r node_modules", **options)
            subprocess.check_call("npm install", **options)
            subprocess.check_call("npm run build", **options)

            # Copy the build output to the expected location
            # build_path = os.path.join(self.app_path, "build")
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
    docker_image: str = "public.ecr.aws/sam/build-nodejs18.x:latest"


class UIConstruct(Construct):

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        rest_api_id,
        user_pool,
        user_pool_client,
        identity_pool,
        props: UIConstructProps,
    ) -> None:
        super().__init__(scope, construct_id)

        # Use provided props or create default props
        self.props = props or UIConstructProps()

        build_path = os.path.join(self.props.app_path, "dist")

        # S3 Bucket for hosting the UI
        website_bucket = s3.Bucket(
            self,
            "WebsiteBucket",
            removal_policy=self.props.removal_policy,
            block_public_access=self.props.block_public_access,
            auto_delete_objects=self.props.auto_delete_objects,
            website_index_document=self.props.website_index_document,
            website_error_document=self.props.website_error_document,
        )

        # CloudFront distribution for serving the UI
        origin_access_identity = cloudfront.OriginAccessIdentity(self, "S3OAI")
        website_bucket.grant_read(origin_access_identity)

        x_origin_verify_secret = secretsmanager.Secret(
            self,
            "X-Origin-Verify-Secret",
            removal_policy=self.props.removal_policy,
            generate_secret_string=secretsmanager.SecretStringGenerator(
                exclude_punctuation=self.props.exclude_punctuation,
                generate_string_key=self.props.generate_secret_string_key,
                secret_string_template="{}",
            ),
        )

        distribution = cloudfront.CloudFrontWebDistribution(
            self,
            "Distribution",
            origin_configs=[
                cloudfront.SourceConfiguration(
                    s3_origin_source=cloudfront.S3OriginConfig(
                        s3_bucket_source=website_bucket,
                        origin_access_identity=origin_access_identity,
                    ),
                    behaviors=[cloudfront.Behavior(is_default_behavior=True)],
                ),
                cloudfront.SourceConfiguration(
                    custom_origin_source=cloudfront.CustomOriginConfig(
                        domain_name=f"{rest_api_id}.execute-api.{scope.region}.amazonaws.com",
                        origin_protocol_policy=cloudfront.OriginProtocolPolicy.HTTPS_ONLY,
                        origin_headers={
                            "X-Origin-Verify": x_origin_verify_secret.secret_value_from_json(
                                self.props.generate_secret_string_key
                            ).unsafe_unwrap()
                        },
                    ),
                    behaviors=[
                        cloudfront.Behavior(
                            path_pattern="/prod/api/*",
                            allowed_methods=cloudfront.CloudFrontAllowedMethods.ALL,
                            cached_methods=cloudfront.CloudFrontAllowedCachedMethods.GET_HEAD,
                            compress=False,
                            forwarded_values=cloudfront.CfnDistribution.ForwardedValuesProperty(
                                query_string=True,
                                headers=list(self.props.origin_headers),
                            ),
                            default_ttl=Duration.seconds(0),
                            is_default_behavior=False,
                            max_ttl=Duration.minutes(self.props.max_ttl_minutes),
                            viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.HTTPS_ONLY,
                        ),
                    ],
                ),
            ],
            price_class=self.props.price_class,
            error_configurations=[
                cloudfront.CfnDistribution.CustomErrorResponseProperty(
                    error_code=self.props.error_response_code,
                    error_caching_min_ttl=self.props.error_caching_min_ttl,
                    response_code=200,
                    response_page_path=self.props.error_response_page_path,
                )
            ],
            default_root_object=self.props.distribution_default_root_object,
        )

        # S3 Deployment
        exports_asset = s3deploy.Source.json_data(
            "aws-exports.json",
            {
                "region": scope.region,
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
                            "endpoint": f"https://{distribution.distribution_domain_name}/prod",
                        },
                    },
                },
            },
        )

        asset = s3deploy.Source.asset(
            self.props.app_path,
            bundling=BundlingOptions(
                image=DockerImage.from_registry(self.props.docker_image),
                command=self.props.command,
                local=LocalBundling(self.props.app_path, build_path),
            ),
        )

        s3deploy.BucketDeployment(
            self,
            "UserInterfaceDeployment",
            sources=[asset, exports_asset],
            destination_bucket=website_bucket,
            distribution=distribution,
            distribution_paths=["/*"],
        )

        # Outputs
        self.distribution_url = f"https://{distribution.distribution_domain_name}"
        self.website_bucket = website_bucket
