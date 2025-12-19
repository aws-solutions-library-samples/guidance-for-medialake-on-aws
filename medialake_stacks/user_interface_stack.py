import secrets
import string
from dataclasses import dataclass

from aws_cdk import CfnOutput, Fn, Stack, Token
from aws_cdk import aws_iam as iam
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_ssm as ssm
from aws_cdk import custom_resources as cr

# from medialake_stacks.auth_stack import AuthStack
from constructs import Construct

from config import config
from medialake_constructs.userInterface import UIConstruct, UIConstructProps


@dataclass
class UserInterfaceStackProps:
    # Buckets are now imported from BaseInfrastructureStack exports
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
                            resources=["*"],
                        )
                    ]
                ),
            )
            waf_acl_arn = waf_acl_param.get_response_field("Parameter.Value")

        parameter_name = (
            f"/medialake/{config.environment}/cloudfront-distribution-domain"
        )

        # Import API Gateway REST API ID from CloudFormation export
        api_gateway_rest_id = Fn.import_value("MediaLakeApiGatewayCore-ApiGatewayId")

        # Read API Gateway stage name from SSM Parameter Store instead of CloudFormation export
        # This avoids circular dependency issues since the deployment stack is created after this stack
        api_gateway_stage_param = ssm.StringParameter.from_string_parameter_name(
            self,
            "ApiGatewayStageNameParameter",
            string_parameter_name=f"/medialake/{config.environment}/api-gateway-stage-name",
        )
        api_gateway_stage = api_gateway_stage_param.string_value

        # Import S3 buckets from BaseInfrastructureStack exports
        media_assets_bucket_arn = Fn.import_value(
            "MediaLakeBaseInfrastructure-MediaAssetsBucketArn"
        )
        media_assets_bucket_kms_key_arn = Fn.import_value(
            "MediaLakeBaseInfrastructure-MediaAssetsBucketKmsKeyArn"
        )
        access_log_bucket_arn = Fn.import_value(
            "MediaLakeBaseInfrastructure-AccessLogsBucketArn"
        )

        # Create bucket references from ARNs
        media_assets_bucket = s3.Bucket.from_bucket_arn(
            self, "ImportedMediaAssetsBucket", media_assets_bucket_arn
        )
        access_log_bucket = s3.Bucket.from_bucket_arn(
            self, "ImportedAccessLogBucket", access_log_bucket_arn
        )

        # Extract custom domain configuration from config
        custom_domain_name = None
        certificate_arn = None
        if config.cloudfront_custom_domain:
            custom_domain_name = config.cloudfront_custom_domain.domain_name
            certificate_arn = config.cloudfront_custom_domain.certificate_arn

        self._ui = UIConstruct(
            self,
            "UserInterface",
            props=UIConstructProps(
                cognito_user_pool_id=props.cognito_user_pool_id,
                cognito_user_pool_client_id=props.cognito_user_pool_client_id,
                cognito_identity_pool=props.cognito_identity_pool,
                api_gateway_rest_id=api_gateway_rest_id,
                api_gateway_stage=api_gateway_stage,
                access_log_bucket=access_log_bucket,
                media_assets_bucket=media_assets_bucket,
                media_assets_bucket_kms_key_arn=media_assets_bucket_kms_key_arn,
                cloudfront_waf_acl_arn=waf_acl_arn,
                cognito_domain_prefix=props.cognito_domain_prefix,
                parameter_name=parameter_name,
                custom_domain_name=custom_domain_name,
                certificate_arn=certificate_arn,
            ),
        )

        # Create the SSM parameter after UI construct is created
        # so we can access the CloudFront distribution domain
        ssm.StringParameter(
            self,
            "CloudFrontDistributionDomainParameter",
            parameter_name=parameter_name,
            string_value=self._ui.cloudfront_distribution.distribution_domain_name,
            description="CloudFront distribution domain for MediaLake UI",
        )

        # Export SSM parameter name as CloudFormation output
        CfnOutput(
            self,
            "CloudFrontDistributionDomainParameterName",
            value=f"/medialake/{config.environment}/cloudfront-distribution-domain",
            description="SSM parameter name for CloudFront distribution domain",
            export_name=f"{self.stack_name}-CloudFrontDistributionDomainParameterName",
        )

        update_params = {
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
        }

        _ = cr.AwsCustomResource(
            self,
            "UpdateCognitoVerificationMessage",
            on_create=cr.AwsSdkCall(
                service="CognitoIdentityServiceProvider",
                action="updateUserPool",
                parameters=update_params,
                physical_resource_id=cr.PhysicalResourceId.of(
                    "UpdateCognitoVerificationMessage"
                ),
            ),
            on_update=cr.AwsSdkCall(
                service="CognitoIdentityServiceProvider",
                action="updateUserPool",
                parameters=update_params,
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

        # Export CloudFront distribution domain as a stack output
        CfnOutput(
            self,
            "CloudFrontDistributionDomain",
            value=self._ui.cloudfront_distribution.distribution_domain_name,
            export_name=f"{config.resource_prefix}-{config.environment}-cloudfront-domain",
            description="CloudFront distribution domain for CORS configuration",
        )

        # Store the domain as a class property for cross-stack references
        self.cloudfront_domain = (
            self._ui.cloudfront_distribution.distribution_domain_name
        )

        # Optional custom UI origin host (can be set to a custom domain in the future)
        # For now, defaults to None - will fall back to CloudFront domain
        self.ui_origin_host = None

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
