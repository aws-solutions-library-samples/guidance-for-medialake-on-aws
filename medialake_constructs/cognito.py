import secrets
import string
from dataclasses import dataclass
from constructs import Construct
from typing import Optional
from aws_cdk import (
    aws_cognito as cognito,
    aws_iam as iam,
    aws_dynamodb as dynamodb,
    RemovalPolicy,
    custom_resources as cr,
    CfnOutput,
    Duration,
    Fn,
)
from config import config
from aws_cdk.aws_cognito_identitypool_alpha import (
    IdentityPool,
    UserPoolAuthenticationProvider,
    IdentityPoolAuthenticationProviders,
)
from medialake_constructs.shared_constructs.dynamodb import DynamoDB, DynamoDBProps
from medialake_constructs.shared_constructs.lambda_base import Lambda, LambdaConfig


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


def generate_random_password(length=16):
    alphabet = string.ascii_letters + string.digits + string.punctuation
    password = "".join(secrets.choice(alphabet) for _ in range(length))
    return password


class CognitoConstruct(Construct):
    def __init__(
        self, scope: Construct, construct_id: str, props: Optional[CognitoProps] = None
    ) -> None:
        super().__init__(scope, construct_id)

        # Use provided props or create default props
        self.props = props or CognitoProps()

        # Create DynamoDB table for user settings
        self._user_settings_table = DynamoDB(
            self,
            "UserSettingsTable",
            props=DynamoDBProps(
                name="medialake_user_settings_table",
                partition_key_name="user_id",
                partition_key_type=dynamodb.AttributeType.STRING,
            ),
        )

        # Create Lambda functions
        self._cognito_trigger_lambda = Lambda(
            self,
            "CognitoTrigger",
            LambdaConfig(
                name="cognito-trigger",
                entry="lambdas/auth/cognito_trigger",
            ),
        )

        # Create User Pool
        self._user_pool = cognito.UserPool(
            self,
            "MediaLakeUserPool",
            removal_policy=self.props.removal_policy,
            self_sign_up_enabled=self.props.self_sign_up_enabled,
            advanced_security_mode=cognito.AdvancedSecurityMode.ENFORCED,
            auto_verify=cognito.AutoVerifiedAttrs(
                email=self.props.auto_verify_email, phone=self.props.auto_verify_phone
            ),
            sign_in_aliases=cognito.SignInAliases(email=self.props.sign_in_with_email),
            lambda_triggers=cognito.UserPoolTriggers(
                post_confirmation=self._cognito_trigger_lambda.function,
            ),
            password_policy=cognito.PasswordPolicy(
                min_length=8,
                require_lowercase=True,
                require_uppercase=True,
                require_digits=True,
                require_symbols=True,
                temp_password_validity=Duration.days(7),
            ),
            user_invitation=cognito.UserInvitationConfig(
                email_subject="Welcome to MediaLake",
                email_body="""
                <html>
                <body>
                    <p>Hello,</p>
                    <p>Welcome to MediaLake! Your account has been created successfully.</p>
                    <p><strong>Your login credentials:</strong><br/>
                    Username: {username}<br/>
                    Temporary Password: {####}</p>
                    <p><strong>To get started:</strong></p>
                    <ol>
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
            ),
        )

        # Create User Pool Client
        self._user_pool_client = self._user_pool.add_client(
            "MediaLakeUserPoolClient",
            generate_secret=self.props.generate_secret,
            auth_flows=cognito.AuthFlow(
                admin_user_password=self.props.admin_user_password,
                user_password=self.props.user_password,
                user_srp=self.props.user_srp,
            ),
        )

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

        random_password = generate_random_password()

        # Create default admin user
        create_user_handler = cr.AwsCustomResource(
            self,
            "CreateUserHandler",
            on_create=cr.AwsSdkCall(
                service="CognitoIdentityServiceProvider",
                action="adminCreateUser",
                parameters={
                    "UserPoolId": self._user_pool.user_pool_id,
                    "Username": config.initial_user_email,
                    "TemporaryPassword": random_password,
                    "UserAttributes": [
                        {"Name": "email", "Value": config.initial_user_email},
                        {"Name": "email_verified", "Value": "true"},
                    ],
                },
                physical_resource_id=cr.PhysicalResourceId.of("CreateUserHandler"),
            ),
            policy=cr.AwsCustomResourcePolicy.from_statements(
                [
                    iam.PolicyStatement(
                        actions=["cognito-idp:AdminCreateUser"],
                        resources=[self._user_pool.user_pool_arn],
                    )
                ]
            ),
        )

        # Add dependency
        create_user_handler.node.add_dependency(self._user_pool)

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
