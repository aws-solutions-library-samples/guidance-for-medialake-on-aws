"""
API Gateway settings module for MediaLake.

This module defines the settingsConstruct class which sets up API Gateway endpoints
and associated Lambda functions for managing media settings. It handles:
- S3 bucket connections
- DynamoDB table management
- IAM roles and permissions
- API Gateway integration
- Lambda function configuration
"""

from dataclasses import dataclass
from constructs import Construct
from aws_cdk import (
    aws_apigateway as apigateway,
    aws_iam as iam,
    aws_secretsmanager as secretsmanager,
    aws_dynamodb as dynamodb,
    aws_s3 as s3,
    aws_events as events,
    Stack,
)
from medialake_constructs.shared_constructs.lam_deployment import LambdaDeployment

from medialake_constructs.shared_constructs.lambda_base import (
    Lambda,
    LambdaConfig,
)
from medialake_constructs.shared_constructs.dynamodb import (
    DynamoDB,
    DynamoDBProps,
)
from medialake_constructs.shared_constructs.lambda_layers import (
    IngestMediaProcessorLayer,
)


@dataclass
class SettingsProps:
    """Configuration for Lambda function creation."""

    asset_table: dynamodb.TableV2
    iac_assets_bucket: s3.Bucket
    api_resource: apigateway.IResource
    cognito_authorizer: apigateway.IAuthorizer
    x_origin_verify_secret: secretsmanager.Secret
    ingest_event_bus: events.EventBus
    iac_assets_bucket: s3.Bucket

class SettingsConstruct(Construct):
    """
    AWS CDK Construct for managing MediaLake settings infrastructure.

    This construct creates and configures:
    - API Gateway endpoints for connector management
    - Lambda functions for handling connector operations
    - DynamoDB tables for storing connector metadata
    - IAM roles and policies for secure access
    - S3 bucket notifications and event handling
    - Integration with EventBridge for event processing

    Attributes:
        lambda_deployment (LambdaDeployment): Handles deployment of Lambda functions

    Args:
        scope (Construct): The scope in which to define this construct
        constructor_id (str): The scoped construct ID
        api_resource (apigateway.IResource): The API Gateway resource to attach to
        cognito_authorizer (apigateway.IAuthorizer): Cognito authorizer for API endpoints
        x_origin_verify_secret (secretsmanager.Secret): Secret for origin verification
        ingest_event_bus (events.EventBus): EventBus for ingestion events
        iac_assets_bucket (s3.Bucket): S3 bucket for infrastructure assets
        props (settingsProps): Configuration properties for the construct
    """

    def __init__(
        self,
        scope: Construct,
        constructor_id: str,
        props: SettingsProps,
    ) -> None:
        super().__init__(scope, constructor_id)

        # Get the current account ID
        account_id = Stack.of(self).account

        # Create settings resource
        settings_resource = props.api_resource.root.add_resource("settings")
        settings_user_resource = settings_resource.add_resource("users")
        settings_user_del_resource = settings_user_resource.add_resource("{id}")
        
        settings_users_get_lambda_config = LambdaConfig(
            name="settings_users_get_lambda",
            entry="lambdas/api/settings/users/get_users",
            environment_variables={
                "X_ORIGIN_VERIFY_SECRET_ARN": (props.x_origin_verify_secret.secret_arn),
            },
        )
        settings_users_get_lambda = Lambda(
            self,
            "SettingsUsersGetLambda",
            config=settings_users_get_lambda_config,
        )

        settings_user_resource.add_method(
            "GET",
            apigateway.LambdaIntegration(settings_users_get_lambda.function),
            authorization_type=apigateway.AuthorizationType.COGNITO,
            authorizer=props.cognito_authorizer,
        )

        # Delete Connector
        settings_user_del_lambda_config = LambdaConfig(
            name="settings_del_lambda",
            entry="lambdas/api/settings/users/del_settings",
            environment_variables={
                "X_ORIGIN_VERIFY_SECRET_ARN": (props.x_origin_verify_secret.secret_arn),
            },
        )
        
        settings_user_del_lambda = Lambda(
            self,
            "SettingsUserDelLambda",
            config=settings_user_del_lambda_config,
        )

        settings_user_del_resource.add_method(
            "DELETE",
            apigateway.LambdaIntegration(settings_user_del_lambda.function),
            authorization_type=apigateway.AuthorizationType.COGNITO,
            authorizer=props.cognito_authorizer,
        )