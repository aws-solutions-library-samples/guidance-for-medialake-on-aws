from aws_cdk import (
    Stack,
    aws_s3 as s3,
    aws_s3_deployment as s3deploy,
    aws_cloudfront as cloudfront,
    aws_cognito as cognito,
    RemovalPolicy,
    CfnOutput,
    DockerImage,
)
from aws_cdk.aws_cognito_identitypool_alpha import (
    IdentityPool,
    UserPoolAuthenticationProvider,
    IdentityPoolAuthenticationProviders,
)
from constructs import Construct
import os
from typing import Any
from .my_local_bundling import MyLocalBundling

# Constants
WEBSITE_INDEX_DOC = "index.html"
WEBSITE_ERROR_DOC = "index.html"


class UserInterfaceStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs: Any) -> None:
        """Initialize the User Interface stack."""
        super().__init__(scope, construct_id, **kwargs)

        # S3 Bucket for User Interface
        self.user_interface_bucket = self.create_s3_bucket()

        # Cognito Resources
        self.user_pool, self.user_pool_client = self.create_cognito_resources()
        self.identity_pool = self.create_identity_pool(
            self.user_pool, self.user_pool_client
        )

        # CloudFront Distribution
        self.distribution = self.create_cloudfront_distribution()

        # Deploy User Interface
        self.deploy_user_interface()

        # Outputs
        self.create_outputs()

    def create_s3_bucket(self) -> s3.Bucket:
        """Create an S3 bucket."""
        return s3.Bucket(
            self,
            "UserInterfaceBucket",
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            website_index_document=WEBSITE_INDEX_DOC,
            website_error_document=WEBSITE_ERROR_DOC,
        )

    def create_cognito_resources(
        self,
    ) -> tuple[cognito.UserPool, cognito.UserPoolClient]:
        """
        Create Cognito user pool and client.

        Returns:
            tuple: Cognito user pool and user pool client.
        """
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

        return user_pool, user_pool_client

    def create_identity_pool(
        self, user_pool: cognito.UserPool, user_pool_client: cognito.UserPoolClient
    ) -> IdentityPool:
        """Create an identity pool."""
        return IdentityPool(
            self,
            "IdentityPool",
            authentication_providers=IdentityPoolAuthenticationProviders(
                user_pools=[
                    UserPoolAuthenticationProvider(
                        user_pool=user_pool, user_pool_client=user_pool_client
                    )
                ]
            ),
        )

    def create_cloudfront_distribution(self) -> cloudfront.CloudFrontWebDistribution:
        """Create a CloudFront distribution."""
        origin_access_identity = cloudfront.OriginAccessIdentity(self, "S3OAI")
        self.user_interface_bucket.grant_read(origin_access_identity)

        return cloudfront.CloudFrontWebDistribution(
            self,
            "Distribution",
            origin_configs=[
                cloudfront.SourceConfiguration(
                    s3_origin_source=cloudfront.S3OriginConfig(
                        s3_bucket_source=self.user_interface_bucket,
                        origin_access_identity=origin_access_identity,
                    ),
                    behaviors=[cloudfront.Behavior(is_default_behavior=True)],
                ),
            ],
            error_configurations=[
                cloudfront.CfnDistribution.CustomErrorResponseProperty(
                    error_code=404,
                    error_caching_min_ttl=0,
                    response_code=200,
                    response_page_path=f"/{WEBSITE_ERROR_DOC}",
                )
            ],
            default_root_object=WEBSITE_INDEX_DOC,
        )

    def deploy_user_interface(self) -> None:
        """Deploy the user interface to the S3 bucket."""

        app_path = os.path.join(os.path.dirname(__file__), "../user-interface")
        build_path = os.path.join(app_path, "dist")

        asset = s3deploy.Source.asset(
            app_path,
            bundling=s3deploy.BundlingOptions(
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
            sources=[asset],
            destination_bucket=self.user_interface_bucket,
            distribution=self.distribution,
            distribution_paths=["/*"],
        )

    def create_outputs(self) -> None:
        """Create and add CloudFormation outputs to the stack."""
        CfnOutput(
            self,
            "UserInterfaceDomainName",
            value=f"https://{self.distribution.distribution_domain_name}",
        )
