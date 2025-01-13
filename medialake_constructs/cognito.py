from dataclasses import dataclass
from constructs import Construct
from typing import Optional
from aws_cdk import (
    aws_cognito as cognito,
    aws_dynamodb as dynamodb,
    RemovalPolicy,
    CfnOutput,
    Stack,
)
from aws_cdk.aws_cognito_identitypool_alpha import (
    IdentityPool,
    UserPoolAuthenticationProvider,
    IdentityPoolAuthenticationProviders,
)
from medialake_constructs.shared_constructs.dynamodb import DynamoDB, DynamoDBProps
from medialake_constructs.shared_constructs.lambda_base import Lambda, LambdaConfig
from config import config


@dataclass
class CognitoProps:
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
    def __init__(
        self, scope: Construct, construct_id: str, props: Optional[CognitoProps] = None
    ) -> None:
        super().__init__(scope, construct_id)

        # Use provided props or create default props
        self.props = props or CognitoProps()

        # Create Lambda functions
        self._cognito_trigger_lambda = Lambda(
            self,
            "CognitoTrigger",
            LambdaConfig(
                name="cognito-trigger",
                entry="lambdas/auth/cognito_trigger",
            ),
        )

        # Create User Pool using L1 construct for more control
        user_pool_props = {
            "admin_create_user_config": cognito.CfnUserPool.AdminCreateUserConfigProperty(
                allow_admin_create_user_only=not self.props.self_sign_up_enabled,
                invite_message_template=cognito.CfnUserPool.InviteMessageTemplateProperty(
                    email_message="""
                    <html>
                    <body>
                        <p>Hello,</p>
                        <p>Welcome to MediaLake! Your account has been created successfully.</p>
                        <p><strong>Your login credentials:</strong><br/>
                        Username: {username}<br/>
                        Temporary Password: {####}</p>
                        <p><strong>To get started:</strong></p>
                        <ol>
                            <li>Sign in at the MediaLake portal</li>
                            <li>Sign in with your credentials</li>
                            <li>You'll be prompted to create a new password on your first login</li>
                        </ol>
                        <p><em>For security reasons, please change your password immediately upon signing in.</em></p>
                        <p>If you need assistance, please contact your MediaLake administrator.</p>
                        <p>Best regards,<br/>
                        The MediaLake Team</p>
                    </body>
                    </html>
                    """,
                    email_subject="Welcome to MediaLake",
                ),
            ),
            "auto_verified_attributes": (
                ["email"] if self.props.auto_verify_email else []
            ),
            "username_attributes": ["email"] if self.props.sign_in_with_email else None,
            "verification_message_template": cognito.CfnUserPool.VerificationMessageTemplateProperty(
                default_email_option="CONFIRM_WITH_LINK",
                email_message_by_link="""
                <html>
                <body>
                    <p>Hello,</p>
                    <p>You have requested to reset your MediaLake password.</p>
                    <p>Click the link below to set a new password:</p>
                    <p>{##Click here to reset your password##}</p>
                    <p>If you did not request this password reset, please ignore this email.</p>
                    <p>Best regards,<br/>
                    The MediaLake Team</p>
                </body>
                </html>
                """,
                email_subject_by_link="Reset your MediaLake password",
            ),
            "policies": cognito.CfnUserPool.PoliciesProperty(
                password_policy=cognito.CfnUserPool.PasswordPolicyProperty(
                    minimum_length=8,
                    require_lowercase=True,
                    require_numbers=True,
                    require_symbols=True,
                    require_uppercase=True,
                    temporary_password_validity_days=7,
                )
            ),
            "lambda_config": cognito.CfnUserPool.LambdaConfigProperty(
                post_confirmation=self._cognito_trigger_lambda.function.function_arn
            ),
            "user_pool_add_ons": cognito.CfnUserPool.UserPoolAddOnsProperty(
                advanced_security_mode="ENFORCED"
            ),
        }

        # Create the user pool with all properties
        cfn_user_pool = cognito.CfnUserPool(
            self, "MediaLakeUserPool", **user_pool_props
        )

        # Create L2 construct from L1
        self._user_pool = cognito.UserPool.from_user_pool_id(
            self, "MediaLakeUserPoolL2", cfn_user_pool.ref
        )

        # Create domain prefix using resource prefix, environment, and hash
        domain_prefix = f"{config.resource_prefix.lower()}-{config.environment.lower()}-{config.primary_region.lower()}-{config.account_id}"
        print(f"Domain prefix: {domain_prefix}")
        self._domain = self._user_pool.add_domain(
            "CognitoDomain",
            cognito_domain=cognito.CognitoDomainOptions(
                domain_prefix=domain_prefix.lower()
            ),
        )

        # Create base client props
        client_props = {
            "generate_secret": self.props.generate_secret,
            "auth_flows": cognito.AuthFlow(
                admin_user_password=self.props.admin_user_password,
                user_password=self.props.user_password,
                user_srp=self.props.user_srp,
            ),
        }

        # Configure identity providers
        supported_providers = []
        saml_providers = []

        # Process each configured identity provider
        for provider in config.authZ.identity_providers:
            if provider.identity_provider_method == "saml":
                # Create SAML provider
                saml_provider = cognito.CfnUserPoolIdentityProvider(
                    self,
                    f"SAMLProvider-{provider.identity_provider_name}",
                    user_pool_id=cfn_user_pool.ref,
                    provider_name=provider.identity_provider_name,
                    provider_type="SAML",
                    provider_details={
                        "MetadataURL": provider.identity_provider_metadata_url,
                        "MetadataFile": provider.identity_provider_metadata_path,
                    },
                    attribute_mapping={
                        "email": "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress",
                        "given_name": "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/givenname",
                        "family_name": "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/surname",
                        "custom:role": "http://schemas.microsoft.com/ws/2008/06/identity/claims/role",
                    },
                    idp_identifiers=[provider.identity_provider_name],
                )
                supported_providers.append(
                    cognito.UserPoolClientIdentityProvider.custom(
                        provider.identity_provider_name
                    )
                )
                saml_providers.append(saml_provider)
            elif provider.identity_provider_method == "cognito":
                supported_providers.append(
                    cognito.UserPoolClientIdentityProvider.COGNITO
                )

        # Update client props with configured providers
        if supported_providers:
            client_props.update(
                {
                    "supported_identity_providers": supported_providers,
                    "o_auth": cognito.OAuthSettings(
                        flows=cognito.OAuthFlows(
                            authorization_code_grant=True, implicit_code_grant=True
                        ),
                        scopes=[
                            cognito.OAuthScope.EMAIL,
                            cognito.OAuthScope.OPENID,
                            cognito.OAuthScope.PROFILE,
                        ],
                        callback_urls=[
                            "http://localhost:3000",  # For local development
                            "https://d358w0v8eryzhn.cloudfront.net",  # CloudFront URL
                            "https://d358w0v8eryzhn.cloudfront.net/",  # With trailing slash
                            "https://d358w0v8eryzhn.cloudfront.net/sign-in",  # Sign-in page
                            f"https://{domain_prefix.lower()}.auth.{config.primary_region}.amazoncognito.com/oauth2/idpresponse",  # OAuth callback
                            f"https://{domain_prefix.lower()}.auth.{config.primary_region}.amazoncognito.com/saml2/idpresponse",  # SAML callback
                        ],
                        logout_urls=[
                            "http://localhost:3000",  # For local development
                            "https://d358w0v8eryzhn.cloudfront.net",  # CloudFront URL
                            "https://d358w0v8eryzhn.cloudfront.net/",  # With trailing slash
                            "https://d358w0v8eryzhn.cloudfront.net/sign-in",  # Sign-in page
                        ],
                    ),
                }
            )

        # Create the client
        self._user_pool_client = self._user_pool.add_client(
            "MediaLakeUserPoolClient", **client_props
        )

        # Add dependencies for SAML providers if any
        for provider in saml_providers:
            self._user_pool_client.node.add_dependency(provider)

        # Create Identity Pool
        self._identity_pool = IdentityPool(
            self,
            "MediaLakeIdentityPool",
            authentication_providers=IdentityPoolAuthenticationProviders(
                user_pools=[
                    UserPoolAuthenticationProvider(
                        user_pool=self._user_pool,
                        user_pool_client=self._user_pool_client,
                    )
                ],
            ),
        )

        self.client_id = CfnOutput(
            self,
            "UserPoolClientId",
            value=self._user_pool_client.user_pool_client_id,
            export_name="UserPoolClientId",
        )

    @property
    def user_pool(self) -> cognito.IUserPool:
        return self._user_pool

    @property
    def user_pool_ref(self) -> cognito.IUserPool:
        return self._user_pool

    @property
    def user_pool_id(self) -> str:
        return self._user_pool.user_pool_id

    @property
    def user_pool_client(self) -> str:
        return self._user_pool_client.user_pool_client_id

    @property
    def identity_pool(self) -> str:
        return self._identity_pool.identity_pool_id
