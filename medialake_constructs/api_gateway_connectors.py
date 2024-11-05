"""
API Gateway Connectors module for MediaLake.

This module defines the ConnectorsConstruct class which sets up API Gateway endpoints
and associated Lambda functions for managing media connectors. It handles:
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
class ConnectorsProps:
    """Configuration for Lambda function creation."""

    asset_table: dynamodb.TableV2
    iac_assets_bucket: s3.Bucket


class ConnectorsConstruct(Construct):
    """
    AWS CDK Construct for managing MediaLake connectors infrastructure.

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
        props (ConnectorsProps): Configuration properties for the construct
    """

    def __init__(
        self,
        scope: Construct,
        constructor_id: str,
        api_resource: apigateway.IResource,
        cognito_authorizer: apigateway.IAuthorizer,
        x_origin_verify_secret: secretsmanager.Secret,
        ingest_event_bus: events.EventBus,
        iac_assets_bucket: s3.Bucket,
        props: ConnectorsProps,
    ) -> None:
        super().__init__(scope, constructor_id)

        # Get the current account ID
        account_id = Stack.of(self).account

        ingest_media_processor_layer = IngestMediaProcessorLayer(
            self,
            "IngestMediaProcessorLayer",
        )

        # Use the new LambdaDeployment construct
        self.lambda_deployment = LambdaDeployment(
            self,
            "IngestS3LambdaDeployment",
            destination_bucket=iac_assets_bucket.bucket,
            code_path=["lambdas", "ingest", "s3"],
        )

        dynamo_table = DynamoDB(
            self,
            "ConnectorsTable",
            props=DynamoDBProps(
                name=f"medialake_connector_table_{constructor_id}",
                partition_key_name="id",
                partition_key_type=dynamodb.AttributeType.STRING,
                # removal_policy=RemovalPolicy.DESTROY
            ),
        )

        # Create connectors resource
        connectors_resource = api_resource.root.add_resource("connectors")
        connectors_get_lambda_config = LambdaConfig(
            name="connectors_get_lambda",
            entry="lambdas/api/connectors/get_connectors",
            environment_variables={
                "X_ORIGIN_VERIFY_SECRET_ARN": (x_origin_verify_secret.secret_arn),
                "MEDIALAKE_CONNECTOR_TABLE": dynamo_table.table_arn,
            },
        )
        connectors_get_lambda = Lambda(
            self,
            "ConnectorsGetLambda",
            config=connectors_get_lambda_config,
        )

        connectors_get_lambda.function.role.add_to_policy(
            iam.PolicyStatement(
                actions=["dynamodb:Scan"], resources=[dynamo_table.table_arn]
            )
        )

        # Add KMS decrypt permission for the DynamoDB table's KMS key
        # connectors_get_lambda.function.role.add_to_policy(
        #     iam.PolicyStatement(
        #         actions=["kms:Decrypt"],
        #         resources=[dynamo_table.table.encryption_key],
        #     )
        # )

        connectors_resource.add_method(
            "GET",
            apigateway.LambdaIntegration(connectors_get_lambda.function),
            authorization_type=apigateway.AuthorizationType.COGNITO,
            authorizer=cognito_authorizer,
        )

        # Delete Connector
        connectors_del_lambda_config = LambdaConfig(
            name="connectors_del_lambda",
            entry="lambdas/api/connectors/del_connectors",
            environment_variables={
                "X_ORIGIN_VERIFY_SECRET_ARN": (x_origin_verify_secret.secret_arn),
                "MEDIALAKE_CONNECTOR_TABLE": dynamo_table.table_arn,
            },
        )
        connectors_del_lambda = Lambda(
            self,
            "ConnectorsDelLambda",
            config=connectors_del_lambda_config,
        )

        connectors_del_lambda.function.role.add_to_policy(
            iam.PolicyStatement(
                actions=["dynamodb:Scan"], resources=[dynamo_table.table_arn]
            )
        )
        connectors_del_lambda.function.role.add_to_policy(
            iam.PolicyStatement(
                actions=["dynamodb:GetItem"], resources=[dynamo_table.table_arn]
            )
        )

        # Add KMS decrypt permission for the DynamoDB table's KMS key
        # connectors_del_lambda.function.role.add_to_policy(
        #     iam.PolicyStatement(
        #         actions=["kms:Decrypt"],
        #         resources=[dynamo_table.kms_key.key_arn],
        #     )
        # )
        connectors_del_lambda.function.role.add_to_policy(
            iam.PolicyStatement(
                actions=["dynamodb:DeleteItem"], resources=[dynamo_table.table_arn]
            )
        )

        connectors_del_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "lambda:CreateFunction",
                    "lambda:UpdateFunctionCode",
                    "lambda:UpdateFunctionConfiguration",
                    "lambda:DeleteFunction",
                    "lambda:TagResource",
                    "lambda:CreateEventSourceMapping",
                ],
                resources=[
                    f"arn:aws:lambda:*:{account_id}:function:*",
                    f"arn:aws:lambda:*:{account_id}:event-source-mapping:*",  # Added resource
                ],
            )
        )

        # Update IAM/S3 policy with account-specific ARNs
        connectors_del_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "s3:PutBucketNotification",
                    "s3:GetBucketNotification",
                    "s3:DeleteBucketNotification",
                ],
                resources=["arn:aws:s3:::*"],
            )
        )

        # Separate IAM policy with account-specific ARNs
        connectors_del_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "iam:DeleteRole",
                    "iam:UpdateRole",
                    "iam:PutRolePolicy",
                    "iam:DeleteRolePolicy",
                    "iam:AttachRolePolicy",
                    "iam:DetachRolePolicy",
                    "iam:PassRole",
                    "iam:ListAttachedRolePolicies",
                    "iam:ListRolePolicies",
                    "iam:GetRolePolicy",
                ],
                resources=[f"arn:aws:iam::{account_id}:role/*"],
            )
        )

        # Policy for DynamoDB actions on a specific table
        connectors_del_lambda.function.role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "dynamodb:PutItem",
                    "dynamodb:GetItem",
                    "dynamodb:UpdateItem",
                    "dynamodb:DeleteItem",
                ],
                resources=[dynamo_table.table_arn],
            )
        )

        # Policy for S3 actions
        connectors_del_lambda.function.role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "s3:ListBucket",
                    "s3:GetBucketLocation",
                    "s3:PutBucketNotification",
                ],
                resources=["arn:aws:s3:::*"],
            )
        )

        connectors_del_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "sqs:GetQueueAttributes",
                    "sqs:CreateQueue",
                    "sqs:DeleteQueue",
                    "sqs:SetQueueAttributes",
                ],
                resources=[f"arn:aws:sqs:*:{account_id}:*"],
            )
        )

        connectors_resource.add_method(
            "DELETE",
            apigateway.LambdaIntegration(connectors_del_lambda.function),
            authorization_type=apigateway.AuthorizationType.COGNITO,
            authorizer=cognito_authorizer,
        )

        # Create s3connector resource and Lambda function
        connector_s3_resource = connectors_resource.add_resource("s3")

        connector_s3_get_lambda_config = LambdaConfig(
            name="connector_s3_get",
            entry="lambdas/api/connectors/s3/get_s3",
            environment_variables={
                "X_ORIGIN_VERIFY_SECRET_ARN": (x_origin_verify_secret.secret_arn),
            },
        )
        connector_s3_get_lambda = Lambda(
            self,
            "ConnectorS3GetLambda",
            config=connector_s3_get_lambda_config,
        )

        # Fix the policy statement syntax
        connector_s3_get_lambda.function.role.add_to_policy(
            iam.PolicyStatement(actions=["s3:ListAllMyBuckets"], resources=["*"])
        )

        connector_s3_resource.add_method(
            "GET",
            apigateway.LambdaIntegration(connector_s3_get_lambda.function),
            authorization_type=apigateway.AuthorizationType.COGNITO,
            authorizer=cognito_authorizer,
        )

        connector_s3_post_lambda_config = LambdaConfig(
            name="connector_s3_post",
            entry="lambdas/api/connectors/s3/post_s3",
            environment_variables={
                "X_ORIGIN_VERIFY_SECRET_ARN": x_origin_verify_secret.secret_arn,
                "MEDIALAKE_CONNECTOR_TABLE": dynamo_table.table_arn,
                "S3_CONNECTOR_LAMBDA": self.lambda_deployment.deployment_key,
                "IAC_ASSETS_BUCKET": iac_assets_bucket.bucket.bucket_name,
                "INGEST_MEDIA_PROCESSOR_LAYER": ingest_media_processor_layer.layer.layer_version_arn,
                "INGEST_EVENT_BUS": ingest_event_bus.event_bus_name,
                "MEDIALAKE_ASSET_TABLE": props.asset_table.table_arn,
            },
        )

        connector_s3_post_lambda = Lambda(
            self,
            "ConnectorS3PostLambda",
            config=connector_s3_post_lambda_config,
        )

        if props.iac_assets_bucket.bucket.encryption_key:
            connector_s3_post_lambda.function.add_to_role_policy(
                iam.PolicyStatement(
                    actions=[
                        "kms:Decrypt",
                        "kms:GenerateDataKey",
                    ],
                    resources=[props.iac_assets_bucket.bucket.encryption_key.key_arn],
                )
            )

        connector_s3_post_lambda.function.role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "s3:GetObject",
                    "s3:ListBucket",
                    "s3:GetObjectVersion",
                    "s3:GetObjectAttributes",
                ],
                resources=[
                    props.iac_assets_bucket.bucket.bucket_arn,
                    f"{props.iac_assets_bucket.bucket.bucket_arn}/*",
                ],
            )
        )

        # Update SQS policy with account-specific ARN
        connector_s3_post_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "sqs:GetQueueAttributes",
                    "sqs:CreateQueue",
                    "sqs:DeleteQueue",
                    "sqs:SetQueueAttributes",
                ],
                resources=[f"arn:aws:sqs:*:{account_id}:*"],
            )
        )

        # Update Lambda policy with account-specific ARN
        connector_s3_post_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "lambda:CreateFunction",
                    "lambda:UpdateFunctionCode",
                    "lambda:UpdateFunctionConfiguration",
                    "lambda:DeleteFunction",
                    "lambda:TagResource",
                    "lambda:CreateEventSourceMapping",
                    "lambda:GetLayerVersion",
                ],
                resources=[
                    f"arn:aws:lambda:*:{account_id}:function:*",
                    f"arn:aws:lambda:*:{account_id}:event-source-mapping:*",
                    f"arn:aws:lambda:*:{account_id}:layer:*",  # Added resource
                ],
            )
        )

        # Update IAM/S3 policy with account-specific ARNs
        connector_s3_post_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "s3:PutBucketNotification",
                    "s3:GetBucketNotification",
                    "s3:DeleteBucketNotification",
                ],
                resources=["arn:aws:s3:::*"],
            )
        )

        # Separate IAM policy with account-specific ARNs
        connector_s3_post_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "iam:DeleteRole",
                    "iam:UpdateRole",
                    "iam:PutRolePolicy",
                    "iam:AttachRolePolicy",
                    "iam:PassRole",
                    "iam:DeleteRolePolicy",
                    "iam:CreateRole",
                    "iam:TagRole",
                    "iam:AttachRolePolicy",
                    "iam:DetachRolePolicy",
                    "iam:PassRole",
                ],
                resources=[f"arn:aws:iam::{account_id}:role/*"],
            )
        )

        # Grant permissions correctly
        iac_assets_bucket.bucket.grant_read_write(connector_s3_post_lambda.function)

        # Policy for DynamoDB actions on a specific table
        connector_s3_post_lambda.function.role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "dynamodb:PutItem",
                    "dynamodb:GetItem",
                    "dynamodb:UpdateItem",
                    "dynamodb:DeleteItem",
                ],
                resources=[dynamo_table.table_arn],
            )
        )

        # Policy for S3 actions
        connector_s3_post_lambda.function.role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "s3:ListBucket",
                    "s3:GetBucketLocation",
                    "s3:PutBucketNotification",
                ],
                resources=["arn:aws:s3:::*"],
            )
        )

        # Policy for SQS actions
        connector_s3_post_lambda.function.role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "sqs:CreateQueue",
                    "sns:CreateTopic",
                ],
                resources=[
                    f"arn:aws:sqs:*:{account_id}:*",
                    f"arn:aws:sns:*:{account_id}:*",
                ],
            )
        )

        connector_s3_resource.add_method(
            "POST",
            apigateway.LambdaIntegration(connector_s3_post_lambda.function),
            authorization_type=apigateway.AuthorizationType.COGNITO,
            authorizer=cognito_authorizer,
        )

        # Create s3 explorer resource with path parameter
        s3_explorer_resource = connector_s3_resource.add_resource("explorer")
        s3_explorer_connector_resource = s3_explorer_resource.add_resource(
            "{connector_id}"
        )

        s3_explorer_get_lambda = Lambda(
            self,
            "S3ExplorerGetLambda",  # Changed ID to avoid conflict
            config=LambdaConfig(
                name="s3_explorer_get",
                entry="lambdas/api/connectors/s3/explorer/rp_connector_id",
                environment_variables={
                    "X_ORIGIN_VERIFY_SECRET_ARN": (x_origin_verify_secret.secret_arn),
                    "MEDIALAKE_CONNECTOR_TABLE": dynamo_table.table_arn,
                },
            ),
        )

        # s3_explorer_del_lambda = Lambda(
        #     self,
        #     "S3ExplorerDelLambda",  # Changed ID to avoid conflict
        #     config=LambdaConfig(
        #         name="s3_explorer_del",
        #         entry="lambdas/api/connectors/s3/explorer/rp_connector_id/del_connector_id",
        #         environment_variables={
        #             "X_ORIGIN_VERIFY_SECRET_ARN": (x_origin_verify_secret.secret_arn),
        #             "MEDIALAKE_CONNECTOR_TABLE": dynamo_table.table_arn,
        #         },
        #     ),
        # )

        # Configure the integration with path parameter mapping
        s3_explorer_integration = apigateway.LambdaIntegration(
            s3_explorer_get_lambda.function,
            request_templates={
                "application/json": '{ "connector_id": "$input.params(\'connector_id\')" }'
            },
        )

        s3_explorer_connector_resource.add_method(
            "GET",
            s3_explorer_integration,
            authorization_type=apigateway.AuthorizationType.COGNITO,
            authorizer=cognito_authorizer,
        )

        s3_explorer_get_lambda.function.role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "s3:*",
                ],
                resources=["arn:aws:s3:::*"],
            )
        )
        s3_explorer_get_lambda.function.role.add_to_policy(
            iam.PolicyStatement(
                actions=["dynamodb:Scan", "dynamodb:Query", "dynamodb:GetItem"],
                resources=[dynamo_table.table_arn],
            )
        )
