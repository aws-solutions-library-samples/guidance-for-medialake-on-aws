import secrets
import string

from aws_cdk import (
    Stack,
    aws_dynamodb as dynamodb,
    aws_s3 as s3,
    aws_ec2 as ec2,
    aws_lambda as lambda_,
    aws_events as events,
    aws_apigateway as apigateway,
    aws_iam as iam,
    custom_resources as cr,
    RemovalPolicy,
)
from constructs import Construct
from dataclasses import dataclass
from medialake_constructs.api_gateway.api_gateway_main_construct import (
    ApiGatewayConstruct,
    ApiGatewayProps,
)

from medialake_constructs.api_gateway.api_gateway_pipelines import (
    ApiGatewayPipelinesConstruct,
    ApiGatewayPipelinesProps,
)

from config import config
from medialake_constructs.cognito import CognitoConstruct, CognitoProps
from medialake_constructs.api_gateway.api_gateway_main_construct import (
    ApiGatewayConstruct,
)
from medialake_constructs.api_gateway.api_gateway_connectors import (
    ConnectorsConstruct,
    ConnectorsProps,
)

from medialake_constructs.api_gateway.api_gateway_search import (
    SearchConstruct,
    SearchProps,
)
from medialake_constructs.api_gateway.api_gateway_assets import (
    AssetsConstruct,
    AssetsProps,
)
from medialake_constructs.api_gateway.api_gateway_settings import (
    SettingsConstruct,
    SettingsConstructProps,
)
from medialake_constructs.api_gateway.api_gateway_users import (
    UsersApi,
    UsersApiProps,
)
from medialake_constructs.api_gateway.api_gateway_environments import (
    ApiGatewayEnvironmentsConstruct,
    ApiGatewayEnvironmentsProps,
)
from medialake_stacks.pipelines_executions_stack import (
    PipelinesExecutionsStack,
    PipelinesExecutionsStackProps,
)
from medialake_constructs.api_gateway.api_gateway_integrations import (
    ApiGatewayIntegrationsConstruct,
    ApiGatewayIntegrationsProps,
)

from medialake_constructs.api_gateway.api_gateway_nodes import (
    ApiGatewayNodesConstruct,
    ApiGatewayNodesProps,
)

from medialake_constructs.userInterface import UIConstruct, UIConstructProps


@dataclass
class ApiGatewayStackProps:
    """Configuration for API Gateway Stack."""

    asset_table: dynamodb.TableV2
    iac_assets_bucket: s3.Bucket
    media_assets_bucket: s3.Bucket
    pipelines_nodes_templates_bucket: s3.Bucket
    asset_table_file_hash_index_arn: str
    asset_table_asset_id_index_arn: str
    ingest_event_bus: events.EventBus
    vpc: ec2.Vpc
    security_group: ec2.SecurityGroup
    collection_endpoint: str
    collection_arn: str
    access_log_bucket: s3.Bucket
    pipeline_table: dynamodb.TableV2
    image_metadata_extractor_lambda: lambda_.Function
    image_proxy_lambda: lambda_.Function
    pipelines_nodes_table: dynamodb.TableV2
    node_table: dynamodb.TableV2


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


class ApiGatewayStack(Stack):
    def __init__(
        self, scope: Construct, id: str, props: ApiGatewayStackProps, **kwargs
    ):
        super().__init__(scope, id, **kwargs)

        # Create Cognito construct first
        self._cognito_construct = CognitoConstruct(
            self,
            "Cognito",
            props=CognitoProps(
                self_sign_up_enabled=False,
                auto_verify_email=True,
                auto_verify_phone=True,
                sign_in_with_email=True,
                generate_secret=False,
                admin_user_password=True,
                user_password=True,
                user_srp=True,
                removal_policy=RemovalPolicy.DESTROY,
            ),
        )

        # Create API Gateway construct
        self._api_gateway = ApiGatewayConstruct(
            self,
            "ApiGateway",
            props=ApiGatewayProps(
                user_pool=self._cognito_construct.user_pool,
                access_log_bucket=props.access_log_bucket,
            ),
        )

        self._connectors_api_gateway = ConnectorsConstruct(
            self,
            "ConnectorsApiGateway",
            props=ConnectorsProps(
                asset_table=props.asset_table,
                asset_table_file_hash_index_arn=props.asset_table_file_hash_index_arn,
                asset_table_asset_id_index_arn=props.asset_table_asset_id_index_arn,
                iac_assets_bucket=props.iac_assets_bucket,
                api_resource=self._api_gateway.rest_api,
                cognito_authorizer=self._api_gateway.cognito_authorizer,
                x_origin_verify_secret=self._api_gateway.x_origin_verify_secret,
                ingest_event_bus=props.ingest_event_bus,
            ),
        )

        self._integrations_stack = ApiGatewayIntegrationsConstruct(
            self,
            "Integrations",
            props=ApiGatewayIntegrationsProps(
                api_resource=self._api_gateway.rest_api,
                x_origin_verify_secret=self._api_gateway.x_origin_verify_secret,
                cognito_authorizer=self._api_gateway.cognito_authorizer,
                pipelines_nodes_table=props.pipelines_nodes_table,
            ),
        )
        self._pipelines_executions_stack = PipelinesExecutionsStack(
            self,
            "PipelinesExecutions",
            props=PipelinesExecutionsStackProps(
                x_origin_verify_secret=self._api_gateway.x_origin_verify_secret,
            ),
        )

        self._pipeline_stack = ApiGatewayPipelinesConstruct(
            self,
            "Pipelines",
            api_resource=self._api_gateway.rest_api,
            cognito_authorizer=self._api_gateway.cognito_authorizer,
            ingest_event_bus=props.ingest_event_bus,
            x_origin_verify_secret=self._api_gateway.x_origin_verify_secret,
            iac_assets_bucket=props.iac_assets_bucket,
            media_assets_bucket=props.media_assets_bucket,
            props=ApiGatewayPipelinesProps(
                asset_table=props.asset_table,
                connector_table=self._connectors_api_gateway.connector_table,
                node_table=props.node_table,
                pipeline_table=props.pipeline_table,
                image_proxy_lambda=props.image_proxy_lambda,
                image_metadata_extractor_lambda=props.image_metadata_extractor_lambda,
                iac_assets_bucket=props.iac_assets_bucket,
                pipelines_nodes_templates_bucket=props.pipelines_nodes_templates_bucket,
                get_pipelines_executions_lambda=self._pipelines_executions_stack.get_pipelines_executions_lambda,
                post_retry_pipelines_executions_lambda=self._pipelines_executions_stack.post_retry_pipelines_executions_lambda,
            ),
        )

        _ = SearchConstruct(
            self,
            "SearchApiGateway",
            props=SearchProps(
                asset_table=props.asset_table,
                media_assets_bucket=props.media_assets_bucket,
                api_resource=self._api_gateway.rest_api,
                cognito_authorizer=self._api_gateway.cognito_authorizer,
                x_origin_verify_secret=self._api_gateway.x_origin_verify_secret,
                open_search_endpoint=props.collection_endpoint,
                open_search_arn=props.collection_arn,
                open_search_index="media",
                vpc=props.vpc,
                security_group=props.security_group,
            ),
        )

        _ = AssetsConstruct(
            self,
            "AssetsApiGateway",
            props=AssetsProps(
                asset_table=props.asset_table,
                api_resource=self._api_gateway.rest_api,
                cognito_authorizer=self._api_gateway.cognito_authorizer,
                x_origin_verify_secret=self._api_gateway.x_origin_verify_secret,
            ),
        )

        _ = SettingsConstruct(
            self,
            "SettingsApiGateway",
            props=SettingsConstructProps(
                api_resource=self._api_gateway.rest_api,
                cognito_authorizer=self._api_gateway.cognito_authorizer,
                cognito_user_pool=self._cognito_construct.user_pool,
                cognito_app_client=self._cognito_construct.user_pool_client,
                x_origin_verify_secret=self._api_gateway.x_origin_verify_secret,
            ),
        )

        _ = UsersApi(
            self,
            "UsersApiGateway",
            props=UsersApiProps(
                api_resource=self._api_gateway.rest_api,
                cognito_authorizer=self._api_gateway.cognito_authorizer,
                cognito_user_pool=self._cognito_construct.user_pool,
                x_origin_verify_secret=self._api_gateway.x_origin_verify_secret,
            ),
        )

        # Create Environments API Gateway construct
        _ = ApiGatewayEnvironmentsConstruct(
            self,
            "EnvironmentsApiGateway",
            props=ApiGatewayEnvironmentsProps(
                api_resource=self._api_gateway.rest_api,
                cognito_authorizer=self._api_gateway.cognito_authorizer,
                x_origin_verify_secret=self._api_gateway.x_origin_verify_secret,
                integrations_table=self._integrations_stack.integrations_table,
            ),
        )

        _ = ApiGatewayNodesConstruct(
            self,
            "NodesApiGateway",
            props=ApiGatewayNodesProps(
                api_resource=self._api_gateway.rest_api,
                x_origin_verify_secret=self._api_gateway.x_origin_verify_secret,
                cognito_authorizer=self._api_gateway.cognito_authorizer,
                pipelines_nodes_table=props.pipelines_nodes_table,
            ),
        )

        # Create UI construct
        self._ui = UIConstruct(
            self,
            "UserInterface",
            props=UIConstructProps(
                cognito_user_pool_id=self._cognito_construct.user_pool_id,
                cognito_user_pool_client_id=self._cognito_construct.user_pool_client,
                cognito_identity_pool=self._cognito_construct.identity_pool,
                api_gateway_rest_id=self._api_gateway.rest_api.rest_api_id,
                access_log_bucket=props.access_log_bucket,
            ),
        )

        _ = cr.AwsCustomResource(
            self,
            "UpdateCognitoVerificationMessage",
            on_create=cr.AwsSdkCall(
                service="CognitoIdentityServiceProvider",
                action="updateUserPool",
                parameters={
                    "UserPoolId": self._cognito_construct.user_pool_id,
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
                        resources=[self._cognito_construct.user_pool.user_pool_arn],
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
                    "UserPoolId": self._cognito_construct.user_pool.user_pool_id,
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
            ),
            policy=cr.AwsCustomResourcePolicy.from_statements(
                [
                    iam.PolicyStatement(
                        actions=["cognito-idp:AdminCreateUser"],
                        resources=[self._cognito_construct.user_pool.user_pool_arn],
                    )
                ]
            ),
        )

        # Add dependency
        create_user_handler.node.add_dependency(self._ui)

    @property
    def rest_api(self) -> apigateway.RestApi:
        return self._api_gateway.rest_api

    @property
    def connector_table(self) -> dynamodb.TableV2:
        return self._connectors_api_gateway.connector_table

    @property
    def user_interface_url(self) -> str:
        return self._ui.user_interface_url

    @property
    def pipelines_create_handler(self) -> lambda_.Function:
        return self._pipeline_stack.pipelines_create_handler

    def get_functions(self) -> list[lambda_.Function]:
        """Return all Lambda functions in this stack that need warming."""
        return [
            # self._pipeline_stack.post_pipelines_handler.function,
            # self._pipeline_stack.get_pipelines_handler.function,
            # self._pipeline_stack.get_pipeline_id_handler.function,
            # self._pipeline_stack.put_pipeline_id_handler.function,
            # self._pipeline_stack.del_pipeline_id_handler.function,
            # self._pipeline_stack.pipeline_trigger_lambda.function,
        ]
