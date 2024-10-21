from aws_cdk import (
    aws_cognito as cognito,
    aws_iam as iam,
    aws_s3 as s3,
    RemovalPolicy,
)

from aws_cdk.aws_cognito_identitypool_alpha import (
    IdentityPool,
    UserPoolAuthenticationProvider,
    IdentityPoolAuthenticationProviders,
)

from dataclasses import dataclass
from constructs import Construct
from typing import List, Optional

@dataclass
class CognitoProps:
    assets_bucket_arn: str
    self_sign_up_enabled: bool = False
    auto_verify_email: bool = True
    auto_verify_phone: bool = True
    sign_in_with_email: bool = True
    generate_secret: bool = False
    admin_user_password: bool = True
    user_password: bool = True
    user_srp: bool = True
    removal_policy: RemovalPolicy = RemovalPolicy.DESTROY

class CognitoConstruct(Construct):
    def __init__(self, scope: Construct, construct_id: str, props: Optional[CognitoProps] = None) -> None:
        super().__init__(scope, construct_id)

        # Use provided props or create default props
        self.props = props or CognitoProps()

        user_pool = cognito.UserPool(
            self,
            "MediaLakeUserPool",
            removal_policy=self.props.removal_policy,
            self_sign_up_enabled=self.props.self_sign_up_enabled,
            auto_verify=cognito.AutoVerifiedAttrs(
                email=self.props.auto_verify_email,
                phone=self.props.auto_verify_phone
            ),
            sign_in_aliases=cognito.SignInAliases(email=self.props.sign_in_with_email),
        )

        user_pool_client = user_pool.add_client(
            "MediaLakeUserPoolClient",
            generate_secret=self.props.generate_secret,
            auth_flows=cognito.AuthFlow(
                admin_user_password=self.props.admin_user_password,
                user_password=self.props.user_password,
                user_srp=self.props.user_srp,
            ),
        )

        identity_pool = IdentityPool(
            self,
            "MediaLakeIdentityPool",
            authentication_providers=IdentityPoolAuthenticationProviders(
                user_pools=[
                    UserPoolAuthenticationProvider(
                        user_pool=user_pool, user_pool_client=user_pool_client
                    )
                ],
            ),
        )

        identity_pool.authenticated_role.add_to_principal_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=["s3:GetObject"],
            resources=[props.assets_bucket_arn,f"{props.assets_bucket_arn}/*"]
        ))

        asset_bucket = s3.Bucket.from_bucket_arn(self,"AssetsBucket",props.assets_bucket_arn)
        asset_bucket.grant_read(identity_pool.authenticated_role)


        self.user_pool_client = user_pool_client
        self.identity_pool = identity_pool
        self.user_pool = user_pool