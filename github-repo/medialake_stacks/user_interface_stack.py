import secrets
import string
from dataclasses import dataclass

from aws_cdk import Stack, Token
from aws_cdk import aws_iam as iam
from aws_cdk import aws_s3 as s3
from aws_cdk import custom_resources as cr

# from medialake_stacks.auth_stack import AuthStack
from constructs import Construct

from config import config
from medialake_constructs.userInterface import UIConstruct, UIConstructProps


@dataclass
class UserInterfaceStackProps:
    access_log_bucket: s3.IBucket
    api_gateway_rest_id: str
    api_gateway_stage: str
    cognito_user_pool_id: str
    cognito_user_pool_client_id: str
    cognito_identity_pool: str
    cognito_user_pool_arn: str
    cloudfront_waf_acl_arn: str
    cognito_domain_prefix: str


def generate_random_password(length=16):
    # Ensure at least one of each required character type
    lowercase = string.ascii_lowercase
    uppercase = string.ascii_uppercase
    digits = string.digits
    symbols = "!@#$%^&*()_+-=[]{}|"

    password = [
        secrets.choice(lowercase),
        secrets.choice(uppercase),
        secrets.choice(digits),
        secrets.choice(symbols),
    ]

    all_chars = lowercase + uppercase + digits + symbols
    password.extend(secrets.choice(all_chars) for _ in range(length - 4))
    password_list = list(password)
    secrets.SystemRandom().shuffle(password_list)

    return "".join(password_list)


class UserInterfaceStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        props: UserInterfaceStackProps,
        **kwargs,
    ):
        super().__init__(scope, construct_id, **kwargs)

        # Look up the WAF ACL ARN from SSM Parameter Store
        # If props.cloudfront_waf_acl_arn starts with '/', assume it's an SSM parameter path
        waf_acl_arn = props.cloudfront_waf_acl_arn
        if props.cloudfront_waf_acl_arn.startswith("/"):
            # Use a custom resource to get the parameter from us-east-1
            waf_acl_param = cr.AwsCustomResource(
                self,
                "GetWafAclArnFromSsm",
                on_update={
                    "service": "SSM",
                    "action": "getParameter",
                    "parameters": {"Name": props.cloudfront_waf_acl_arn},
                    "region": "us-east-1",  # Important: specify us-east-1 region
                    "physical_resource_id": cr.PhysicalResourceId.of(
                        "waf-acl-arn-param-" + props.cloudfront_waf_acl_arn
                    ),
                },
                policy=cr.AwsCustomResourcePolicy.from_statements(
                    [
                        iam.PolicyStatement(
                            actions=["ssm:GetParameter"],
                            resources=["*"],  # You can restrict this further if needed
                        )
                    ]
                ),
            )
            waf_acl_arn = waf_acl_param.get_response_field("Parameter.Value")

        self._ui = UIConstruct(
            self,
            "UserInterface",
            props=UIConstructProps(
                cognito_user_pool_id=props.cognito_user_pool_id,
                cognito_user_pool_client_id=props.cognito_user_pool_client_id,
                cognito_identity_pool=props.cognito_identity_pool,
                api_gateway_rest_id=props.api_gateway_rest_id,
                api_gateway_stage=props.api_gateway_stage,
                access_log_bucket=props.access_log_bucket,
                cloudfront_waf_acl_arn=waf_acl_arn,
                cognito_domain_prefix=props.cognito_domain_prefix,
            ),
        )

        _ = cr.AwsCustomResource(
            self,
            "UpdateCognitoVerificationMessage",
            on_create=cr.AwsSdkCall(
                service="CognitoIdentityServiceProvider",
                action="updateUserPool",
                parameters={
                    "UserPoolId": Token.as_string(props.cognito_user_pool_id),
                    "AdminCreateUserConfig": {
                        "AllowAdminCreateUserOnly": True,
                        "InviteMessageTemplate": {
                            "EmailMessage": f"""
                            <html>
                            <body>
                                <p>Hello,</p>
                                <p>Welcome to MediaLake! Your account has been created successfully.</p>
                                <p><strong>Your login credentials:</strong><br/>
                                Username: {{username}}<br/>
                                Temporary Password: {{####}}</p>
                                <p><strong>To get started:</strong></p>
                                <ol>
                                    <li>Visit {self._ui.user_interface_url} to sign in</li>
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
                            "EmailSubject": "Welcome to MediaLake",
                        },
                    },
                    "VerificationMessageTemplate": {
                        "DefaultEmailOption": "CONFIRM_WITH_LINK",
                        "EmailMessageByLink": f"""
                        <html>
                        <body>
                            <p>Hello,</p>
                            <p>You have requested to reset your MediaLake password.</p>
                            <p>Click the link below to set a new password:</p>
                            <p>{{##Click here to reset your password at {self._ui.user_interface_url}/reset-password?code={{####}}##}}</p>
                            <p>If you did not request this password reset, please ignore this email.</p>
                            <p>Best regards,<br/>
                            The MediaLake Team</p>
                        </body>
                        </html>
                        """,
                        "EmailSubjectByLink": "Reset your MediaLake password",
                    },
                },
                physical_resource_id=cr.PhysicalResourceId.of(
                    "UpdateCognitoVerificationMessage"
                ),
            ),
            policy=cr.AwsCustomResourcePolicy.from_statements(
                [
                    iam.PolicyStatement(
                        actions=["cognito-idp:UpdateUserPool"],
                        resources=[Token.as_string(props.cognito_user_pool_arn)],
                    )
                ]
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
                    "UserPoolId": props.cognito_user_pool_id,
                    "Username": config.initial_user.email,
                    "TemporaryPassword": random_password,
                    "UserAttributes": [
                        {"Name": "email", "Value": config.initial_user.email},
                        {"Name": "given_name", "Value": config.initial_user.first_name},
                        {"Name": "family_name", "Value": config.initial_user.last_name},
                        {"Name": "email_verified", "Value": "true"},
                    ],
                },
                physical_resource_id=cr.PhysicalResourceId.of("CreateUserHandler"),
                ignore_error_codes_matching="UsernameExistsException|User account already exists",
            ),
            on_delete=cr.AwsSdkCall(
                service="CognitoIdentityServiceProvider",
                action="adminDeleteUser",
                parameters={
                    "UserPoolId": props.cognito_user_pool_id,
                    "Username": config.initial_user.email,
                },
                physical_resource_id=cr.PhysicalResourceId.of("DeleteUserHandler"),
                ignore_error_codes_matching="UserNotFoundException|User does not exist",
            ),
            policy=cr.AwsCustomResourcePolicy.from_statements(
                [
                    iam.PolicyStatement(
                        actions=[
                            "cognito-idp:AdminCreateUser",
                            "cognito-idp:AdminDeleteUser",
                        ],
                        resources=[props.cognito_user_pool_arn],
                    )
                ]
            ),
        )

        # Add dependency
        create_user_handler.node.add_dependency(self._ui)

        # Add the initial user to the administrators group
        add_to_admin_group_handler = cr.AwsCustomResource(
            self,
            "AddToAdminGroupHandler",
            on_create=cr.AwsSdkCall(
                service="CognitoIdentityServiceProvider",
                action="adminAddUserToGroup",
                parameters={
                    "UserPoolId": props.cognito_user_pool_id,
                    "Username": config.initial_user.email,
                    "GroupName": "superAdministrators",
                },
                physical_resource_id=cr.PhysicalResourceId.of("AddToAdminGroupHandler"),
                ignore_error_codes_matching="UserNotFoundException|ResourceNotFoundException",
            ),
            on_delete=cr.AwsSdkCall(
                service="CognitoIdentityServiceProvider",
                action="adminRemoveUserFromGroup",
                parameters={
                    "UserPoolId": props.cognito_user_pool_id,
                    "Username": config.initial_user.email,
                    "GroupName": "superAdministrators",
                },
                physical_resource_id=cr.PhysicalResourceId.of(
                    "RemoveFromAdminGroupHandler"
                ),
                ignore_error_codes_matching="UserNotFoundException|ResourceNotFoundException",
            ),
            policy=cr.AwsCustomResourcePolicy.from_statements(
                [
                    iam.PolicyStatement(
                        actions=[
                            "cognito-idp:AdminAddUserToGroup",
                            "cognito-idp:AdminRemoveUserFromGroup",
                            "cognito-idp:AdminListGroupsForUser",
                        ],
                        resources=[props.cognito_user_pool_arn],
                    )
                ]
            ),
        )

        # Ensure the user is created before adding to group
        add_to_admin_group_handler.node.add_dependency(create_user_handler)

    @property
    def user_interface_url(self) -> str:
        return self._ui.user_interface_url
