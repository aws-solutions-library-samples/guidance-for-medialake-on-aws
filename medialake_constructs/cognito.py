import hashlib
from dataclasses import dataclass

from aws_cdk import CfnOutput, RemovalPolicy, Stack
from aws_cdk import aws_cognito as cognito
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_iam as iam
from aws_cdk import custom_resources as cr
from aws_cdk.aws_cognito_identitypool_alpha import (
    IdentityPool,
    IdentityPoolAuthenticationProviders,
    UserPoolAuthenticationProvider,
)
from constructs import Construct

from config import config
from medialake_constructs.shared_constructs.dynamodb import DynamoDB, DynamoDBProps
from medialake_constructs.shared_constructs.lambda_base import Lambda, LambdaConfig


@dataclass
class CognitoGroupConfig:
    name: str
    description: str
    precedence: int


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
        self,
        scope: Construct,
        construct_id: str,
        props: CognitoProps,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Setup
        stack = Stack.of(self)
        region = stack.region
        self.props = props or CognitoProps()
        self._cloudfront_domain = None

        # Create the DynamoDB table for authorization configuration
        self._auth_table_props = DynamoDBProps(
            name=f"{config.resource_prefix}-authorization-{config.environment}",
            partition_key_name="PK",
            partition_key_type=dynamodb.AttributeType.STRING,
            sort_key_name="SK",
            sort_key_type=dynamodb.AttributeType.STRING,
            point_in_time_recovery=True,
            billing_mode=dynamodb.Billing.on_demand(),
            # Enable DynamoDB Streams for policy synchronization
            stream=dynamodb.StreamViewType.NEW_AND_OLD_IMAGES,
            global_secondary_indexes=[
                # GSI1 (Query assignments by PermissionSet or Group)
                dynamodb.GlobalSecondaryIndexPropsV2(
                    index_name="GSI1",
                    partition_key=dynamodb.Attribute(
                        name="GSI1PK", type=dynamodb.AttributeType.STRING
                    ),
                    sort_key=dynamodb.Attribute(
                        name="GSI1SK", type=dynamodb.AttributeType.STRING
                    ),
                    projection_type=dynamodb.ProjectionType.ALL,
                ),
            ],
        )
        self._auth_table = DynamoDB(self, "AuthorizationTable", self._auth_table_props)

        # Create Lambda functions
        self._cognito_trigger_lambda = Lambda(
            self,
            "CognitoTrigger",
            LambdaConfig(
                name="cognito-trigger",
                entry="lambdas/auth/cognito_trigger",
            ),
        )

        # Pre-Token Generation Lambda is now created in CognitoUpdateStack
        # This avoids circular dependencies and timing issues

        # Create User Pool using L1 construct, needed for configuration parameters
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
                pre_sign_up=self._cognito_trigger_lambda.function.function_arn,
                post_confirmation=self._cognito_trigger_lambda.function.function_arn,
                # Pre-token generation config is now set via CognitoUpdateStack
            ),
            "user_pool_add_ons": cognito.CfnUserPool.UserPoolAddOnsProperty(
                advanced_security_mode="ENFORCED"
            ),
            "schema": [
                cognito.CfnUserPool.SchemaAttributeProperty(
                    name="groups",
                    attribute_data_type="String",
                    mutable=True,
                    required=False,
                    string_attribute_constraints=cognito.CfnUserPool.StringAttributeConstraintsProperty(
                        min_length="1", max_length="2048"
                    ),
                ),
                cognito.CfnUserPool.SchemaAttributeProperty(
                    name="email",
                    attribute_data_type="String",
                    required=True,
                    mutable=True,
                ),
                cognito.CfnUserPool.SchemaAttributeProperty(
                    name="given_name",
                    attribute_data_type="String",
                    required=False,
                    mutable=True,
                ),
                cognito.CfnUserPool.SchemaAttributeProperty(
                    name="family_name",
                    attribute_data_type="String",
                    required=False,
                    mutable=True,
                ),
                # Custom attributes
                cognito.CfnUserPool.SchemaAttributeProperty(
                    name="permission_sets",
                    attribute_data_type="String",
                    required=False,
                    mutable=True,
                    developer_only_attribute=False,
                ),
                cognito.CfnUserPool.SchemaAttributeProperty(
                    name="avp_entity_id",
                    attribute_data_type="String",
                    required=False,
                    mutable=True,
                    developer_only_attribute=False,
                ),
                cognito.CfnUserPool.SchemaAttributeProperty(
                    name="organization_id",
                    attribute_data_type="String",
                    required=False,
                    mutable=True,
                    developer_only_attribute=False,
                ),
            ],
        }
        # Create the user pool with all properties
        cfn_user_pool = cognito.CfnUserPool(
            self, "MediaLakeUserPool", **user_pool_props
        )

        # Create L2 construct from L1
        self._user_pool = cognito.UserPool.from_user_pool_id(
            self, "MediaLakeUserPoolL2", cfn_user_pool.ref
        )

        # Grant permissions AFTER the user pool is created
        # Grant permission for pre-signup lambda (same as post confirmation)
        self._cognito_trigger_lambda.function.add_permission(
            "CognitoInvokePreSignUp",
            principal=iam.ServicePrincipal("cognito-idp.amazonaws.com"),
            source_arn=cfn_user_pool.attr_arn,
        )

        # Grant permission for post confirmation lambda
        self._cognito_trigger_lambda.function.add_permission(
            "CognitoInvokePostConfirmation",
            principal=iam.ServicePrincipal("cognito-idp.amazonaws.com"),
            source_arn=cfn_user_pool.attr_arn,
        )

        # Pre-token generation lambda permissions are now granted in CognitoUpdateStack

        # Using stack name, region, account, and environment ensures uniqueness across different deployments
        unique_id = hashlib.md5(
            f"{config.resource_prefix}-{config.primary_region}-{config.account_id}-{config.environment}".encode()
        ).hexdigest()[:16]
        domain_prefix = (
            f"{config.resource_prefix}-{config.environment.lower()}-{unique_id}"
        )
        self._domain_prefix = domain_prefix

        self._domain = self._user_pool.add_domain(
            "CognitoDomain",
            cognito_domain=cognito.CognitoDomainOptions(
                domain_prefix=domain_prefix.lower()
            ),
        )

        # Create default user groups
        self._user_groups = []

        default_groups = [
            CognitoGroupConfig(
                name="superAdministrators",
                description="Super administrators with full access to all MediaLake features and settings",
                precedence=1,
            ),
            CognitoGroupConfig(
                name="editors",
                description="Can upload, edit and manage media assets",
                precedence=20,
            ),
            CognitoGroupConfig(
                name="read-only",
                description="Read-only access to media assets",
                precedence=40,
            ),
        ]

        # Create the groups
        for group in default_groups:
            group = cognito.CfnUserPoolGroup(
                self,
                f"UserGroup-{group.name}",
                user_pool_id=self._user_pool.user_pool_id,
                group_name=group.name,
                description=group.description,
                precedence=group.precedence,
            )
            self._user_groups.append(group)

        # Create base client props
        user_pool_client_props = {
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
                        # Standard mappings
                        "email": "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress",
                        "given_name": "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/givenname",
                        "family_name": "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/surname",
                        "custom:groups": "http://schemas.microsoft.com/ws/2008/06/identity/claims/groups",
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
            user_pool_client_props.update(
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
                            f"https://{domain_prefix.lower()}.auth.{region}.amazoncognito.com/oauth2/idpresponse",
                            f"https://{domain_prefix.lower()}.auth.{region}.amazoncognito.com/saml2/idpresponse",
                        ],
                        logout_urls=[
                            f"https://{domain_prefix.lower()}.auth.{region}.amazoncognito.com",
                            f"https://{domain_prefix.lower()}.auth.{region}.amazoncognito.com/",
                            f"https://{domain_prefix.lower()}.auth.{region}.amazoncognito.com/sign-in",
                        ],
                    ),
                }
            )

        # Create the client
        self._user_pool_client = self._user_pool.add_client(
            "MediaLakeUserPoolClient", **user_pool_client_props
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
    def user_pool_arn(self) -> str:
        return self._user_pool.user_pool_arn

    @property
    def user_pool_client(self) -> cognito.UserPoolClient:
        """Return the user pool client"""
        return self._user_pool_client

    @property
    def user_pool_client_id(self) -> str:
        return self._user_pool_client.user_pool_client_id

    @property
    def identity_pool(self) -> str:
        return self._identity_pool.identity_pool_id

    @property
    def cognito_domain_prefix(self) -> str:
        return self._domain_prefix

    @property
    def auth_table(self):
        """Return the authorization table"""
        return self._auth_table.table

    @property
    def auth_table_name(self) -> str:
        """Return the authorization table name"""
        return self._auth_table.table_name

    def update_callback_urls(self, cloudfront_domain: str) -> None:
        """
        Updates the callback URLs for the Cognito User Pool Client with the CloudFront domain.
        This should be called after the CloudFront distribution is created.

        Args:
            cloudfront_domain: The CloudFront distribution domain name
        """
        if not cloudfront_domain:
            return

        self._cloudfront_domain = cloudfront_domain

        _ = cr.AwsCustomResource(
            self,
            "UpdateUserPoolClientCallbacks",
            on_update=cr.AwsSdkCall(
                service="CognitoIdentityServiceProvider",
                action="updateUserPoolClient",
                parameters={
                    "UserPoolId": self._user_pool.user_pool_id,
                    "ClientId": self._user_pool_client.user_pool_client_id,
                    "CallbackURLs": [
                        f"https://{self._domain_prefix.lower()}.auth.{Stack.of(self).region}.amazoncognito.com/oauth2/idpresponse",
                        f"https://{self._domain_prefix.lower()}.auth.{Stack.of(self).region}.amazoncognito.com/saml2/idpresponse",
                        f"https://{cloudfront_domain}",
                        f"https://{cloudfront_domain}/",
                        f"https://{cloudfront_domain}/login",
                    ],
                    "LogoutURLs": [
                        f"https://{self._domain_prefix.lower()}.auth.{Stack.of(self).region}.amazoncognito.com",
                        f"https://{self._domain_prefix.lower()}.auth.{Stack.of(self).region}.amazoncognito.com/",
                        f"https://{self._domain_prefix.lower()}.auth.{Stack.of(self).region}.amazoncognito.com/sign-in",
                        f"https://{cloudfront_domain}",
                        f"https://{cloudfront_domain}/",
                        f"https://{cloudfront_domain}/sign-in",
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
