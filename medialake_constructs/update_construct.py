from aws_cdk import (
    Stack,
    RemovalPolicy,
    CfnOutput,
    custom_resources as cr,
    aws_iam as iam,
    aws_cognito as cognito,
)
from constructs import Construct
from typing import Optional, List, Dict
from dataclasses import dataclass


@dataclass
class UpdateConstructProps:
    user_pool: cognito.UserPool
    distribution_url: str


class UpdateConstruct(Construct):
    def __init__(
        self, scope: Construct, id: str, *, props: UpdateConstructProps
    ) -> None:
        super().__init__(scope, id)
        self.user_pool = props.user_pool
        self._update_email_template_custom_resource(props.distribution_url)

    def _update_email_template_custom_resource(self, distribution_url: str) -> None:
        """Create a custom resource to update the user pool email template"""
        email_body = """
                <html>
                <body>
                    <p>Hello,</p>
                    
                    <p>Welcome to MediaLake! Your account has been created successfully.</p>
                    
                    <p><strong>Your login credentials:</strong><br/>
                    Username: {username}<br/>
                    Temporary Password: {{####}}</p>
                    
                    <p><strong>To get started:</strong></p>
                    <li>Visit <a href="{distribution_url}">{distribution_url}</a></li>

                    <ol>
                        <li>Sign in with your credentials</li>
                        <li>You'll be prompted to create a new password on your first login</li>
                    </ol>
                    
                    <p><em>For security reasons, please change your password immediately upon signing in.</em></p>
                    
                    <p>If you need assistance, please contact your system administrator.</p>
                    
                    <p>Best regards,<br/>
                    The MediaLake Team</p>
                </body>
                </html>
            """.format(
            username="{username}",
            distribution_url=distribution_url,
        )

        # Create custom resource to update the user pool
        cr.AwsCustomResource(
            self,
            "UpdateEmailTemplateHandler",
            on_create=cr.AwsSdkCall(
                service="CognitoIdentityServiceProvider",
                action="updateUserPool",
                parameters={
                    "UserPoolId": self.user_pool.user_pool_id,
                    "AdminCreateUserConfig": {
                        "EmailMessage": email_body,
                        "EmailSubject": "Welcome to MediaLake - Your Account Information",
                    },
                },
                physical_resource_id=cr.PhysicalResourceId.of(
                    "UpdateEmailTemplateHandler"
                ),
            ),
            policy=cr.AwsCustomResourcePolicy.from_statements(
                [
                    iam.PolicyStatement(
                        actions=["cognito-idp:UpdateUserPool"],
                        resources=[self.user_pool.user_pool_arn],
                    )
                ]
            ),
        )
