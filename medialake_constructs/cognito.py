from aws_cdk import (
    aws_cognito as cognito,
    aws_iam as iam,
    aws_dynamodb as dynamodb,
    RemovalPolicy,
    custom_resources as cr,
    CfnOutput,
    Duration,
)

from aws_cdk.aws_cognito_identitypool_alpha import (
    IdentityPool,
    UserPoolAuthenticationProvider,
    IdentityPoolAuthenticationProviders,
)
from medialake_constructs.shared_constructs.dynamodb import DynamoDB, DynamoDBProps

from medialake_constructs.shared_constructs.lambda_base import Lambda, LambdaConfig
from dataclasses import dataclass
from constructs import Construct
from typing import Optional


@dataclass
class CognitoProps:
    # assets_bucket_arn: str
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

        self._user_settings_table = DynamoDB(
            self,
            "UserSettingsTable",
            props=DynamoDBProps(
                name="medialake_user_settings_table",
                partition_key_name="user_id",
                partition_key_type=dynamodb.AttributeType.STRING,
            ),
        )

        # Create the post confirmation Lambda
        post_confirmation_handler = Lambda(
            self,
            "PostConfirmationTrigger",
            LambdaConfig(
                name="PostConfirmationTrigger",
                entry="lambdas/auth/post_confirmation",
                environment_variables={
                    # The line `# "USER_POOL_ID": user_pool.user_pool_id,` is a commented-out line of code in the Python
                    # script. This line is not being executed by the program and is simply there for reference or as a
                    # placeholder for potential future use.
                    # "USER_POOL_ID": user_pool.user_pool_id,
                    "USER_SETTINGS_TABLE": self._user_settings_table.table_arn,
                },
            ),
        )

        self._cognito_trigger_lambda = Lambda(
            self,
            "CognitoTrigger",
            LambdaConfig(
                name="cognito-trigger",
                entry="lambdas/auth/cognito_trigger",
            ),
        )

        # Use provided props or create default props
        self.props = props or CognitoProps()

        user_pool = cognito.UserPool(
            self,
            "MediaLakeUserPool",
            removal_policy=self.props.removal_policy,
            self_sign_up_enabled=self.props.self_sign_up_enabled,
            auto_verify=cognito.AutoVerifiedAttrs(
                email=self.props.auto_verify_email, phone=self.props.auto_verify_phone
            ),
            sign_in_aliases=cognito.SignInAliases(email=self.props.sign_in_with_email),
            lambda_triggers=cognito.UserPoolTriggers(
                post_confirmation=self._cognito_trigger_lambda.function,
                post_authentication=self._cognito_trigger_lambda.function,
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

        # identity_pool.authenticated_role.add_to_principal_policy(
        #     iam.PolicyStatement(
        #         effect=iam.Effect.ALLOW,
        #         actions=["s3:GetObject"],
        #         resources=[props.assets_bucket_arn, f"{props.assets_bucket_arn}/*"],
        #     )
        # )

        self.user_pool_client = user_pool_client
        self.identity_pool = identity_pool
        self.user_pool = user_pool

        # # Add necessary permissions for the Lambda
        # self._cognito_trigger_lambda.function.add_to_role_policy(
        #     iam.PolicyStatement(
        #         effect=iam.Effect.ALLOW,
        #         actions=[
        #             "cognito-idp:AdminUpdateUserAttributes",
        #             "cognito-idp:AdminAddUserToGroup",
        #         ],
        #         resources=[self.user_pool.user_pool_arn],
        #     )
        # )

        create_user_handler = cr.AwsCustomResource(
            self,
            "CreateUserHandler",
            on_create=cr.AwsSdkCall(
                service="CognitoIdentityServiceProvider",
                action="adminCreateUser",
                parameters={
                    "UserPoolId": user_pool.user_pool_id,
                    "Username": "mne-mscdemo+medialake@amazon.com",
                    "TemporaryPassword": "ChangeMe123!",
                    "UserAttributes": [
                        {"Name": "email", "Value": "mne-mscdemo+medialake@amazon.com"},
                        {"Name": "email_verified", "Value": "true"},
                    ],
                },
                physical_resource_id=cr.PhysicalResourceId.of("CreateUserHandler"),
            ),
            policy=cr.AwsCustomResourcePolicy.from_statements(
                [
                    iam.PolicyStatement(
                        actions=["cognito-idp:AdminCreateUser"],
                        resources=[user_pool.user_pool_arn],
                    )
                ]
            ),
        )

        # Ensure the user is created after the user pool
        create_user_handler.node.add_dependency(user_pool)

        # Outputs
        CfnOutput(self, "UserPoolId", value=user_pool.user_pool_id)
        CfnOutput(self, "UserPoolClientId", value=user_pool_client.user_pool_client_id)
