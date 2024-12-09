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
    aws_dynamodb as dynamodb,
    aws_s3 as s3,
    aws_secretsmanager as secretsmanager,
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


@dataclass
class ConnectorsProps:
    """Configuration for Lambda function creation."""

    asset_table: dynamodb.TableV2
    iac_assets_bucket: s3.Bucket
    resource_table: dynamodb.Table
    asset_table_file_hash_index_arn: str
    asset_table_asset_id_index_arn: str
    ingest_event_bus: str | None
    api_resource: str | None = None
    cognito_authorizer: str | None = None
    x_origin_verify_secret: secretsmanager.Secret | None = None


class ConnectorsConstruct(Construct):
    """
    Create docstring
    """

    def __init__(
        self,
        scope: Construct,
        constructor_id: str,
        # api_resource: apigateway.IResource,
        # cognito_authorizer: apigateway.IAuthorizer,
        # x_origin_verify_secret: secretsmanager.Secret,
        # ingest_event_bus: events.EventBus,
        # iac_assets_bucket: s3.Bucket,
        props: ConnectorsProps,
    ) -> None:
        super().__init__(scope, constructor_id)

        # Get the current account ID
        account_id = Stack.of(self).account

        self.lambda_deployment = LambdaDeployment(
            self,
            "IngestS3LambdaDeployment",
            destination_bucket=props.iac_assets_bucket.bucket,
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
        connectors_resource = props.api_resource.root.add_resource("connectors")

        # Add connector_id path parameter resource
        connector_id_resource = connectors_resource.add_resource("{connector_id}")

        connectors_get_lambda_config = LambdaConfig(
            name="connectors_get_lambda",
            entry="lambdas/api/connectors/get_connectors",
            environment_variables={
                "X_ORIGIN_VERIFY_SECRET_ARN": (props.x_origin_verify_secret.secret_arn),
                "MEDIALAKE_CONNECTOR_TABLE": dynamo_table.table_arn,
            },
        )
        connectors_get_lambda = Lambda(
            self,
            "ConnectorsGetLambda",
            config=connectors_get_lambda_config,
        )

        # connectors_get_lambda.function.role.add_to_policy(
        #     iam.PolicyStatement(
        #         actions=["dynamodb:Scan"], resources=[dynamo_table.table_arn]
        #     )
        # )

        dynamo_table.table.grant_read_data(connectors_get_lambda.function)

        connectors_resource.add_method(
            "GET",
            apigateway.LambdaIntegration(connectors_get_lambda.function),
            authorization_type=apigateway.AuthorizationType.COGNITO,
            authorizer=props.cognito_authorizer,
        )

        # Delete Connector Lambda config remains the same
        connectors_del_lambda = Lambda(
            self,
            "ConnectorsDelLambda",
            config=LambdaConfig(
                name="connectors_del_lambda",
                entry="lambdas/api/connectors/rp_connectorId/del_connectorId",
                environment_variables={
                    "X_ORIGIN_VERIFY_SECRET_ARN": (
                        props.x_origin_verify_secret.secret_arn
                    ),
                    "MEDIALAKE_CONNECTOR_TABLE": dynamo_table.table_arn,
                },
            ),
        )

        # connectors_del_lambda.function.role.add_to_policy(
        #     iam.PolicyStatement(
        #         actions=["dynamodb:Scan"], resources=[dynamo_table.table_arn]
        #     )
        # )
        # connectors_del_lambda.function.role.add_to_policy(
        #     iam.PolicyStatement(
        #         actions=["dynamodb:GetItem"], resources=[dynamo_table.table_arn]
        #     )
        # )

        # connectors_del_lambda.function.role.add_to_policy(
        #     iam.PolicyStatement(
        #         actions=["dynamodb:DeleteItem"], resources=[dynamo_table.table_arn]
        #     )
        # )

        dynamo_table.table.grant_read_write_data(connectors_del_lambda.function)

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
                resources=[f"arn:aws:s3:::{account_id}:*"],
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
        # connectors_del_lambda.function.role.add_to_policy(
        #     iam.PolicyStatement(
        #         actions=[
        #             "dynamodb:PutItem",
        #             "dynamodb:GetItem",
        #             "dynamodb:UpdateItem",
        #             "dynamodb:DeleteItem",
        #         ],
        #         resources=[dynamo_table.table_arn],
        #     )
        # )

        # Policy for S3 actions
        connectors_del_lambda.function.role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "s3:ListBucket",
                    "s3:GetBucketLocation",
                    "s3:PutBucketNotification",
                ],
                resources=[f"arn:aws:s3:::{account_id}:*"],
            )
        )
        # SQS policy for s3 connectors lambda that builds SQS queues
        connectors_del_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "sqs:GetQueueAttributes",
                    "sqs:CreateQueue",
                    # "sqs:DeleteQueue",
                    "sqs:SetQueueAttributes",
                ],
                resources=[f"arn:aws:sqs:*:{account_id}:*"],
            )
        )

        # Move the DELETE method to the connector_id_resource and add path parameter mapping
        connector_id_resource.add_method(
            "DELETE",
            apigateway.LambdaIntegration(
                connectors_del_lambda.function,
                request_templates={
                    "application/json": '{ "connector_id": "$input.params(\'connector_id\')" }'
                },
            ),
            authorization_type=apigateway.AuthorizationType.COGNITO,
            authorizer=props.cognito_authorizer,
        )

        # Create s3connector resource and Lambda function
        connector_s3_resource = connectors_resource.add_resource("s3")

        connector_s3_get_lambda = Lambda(
            self,
            "ConnectorS3GetLambda",
            config=LambdaConfig(
                name="connector_s3_get",
                entry="lambdas/api/connectors/s3/get_s3",
                environment_variables={
                    "X_ORIGIN_VERIFY_SECRET_ARN": (
                        props.x_origin_verify_secret.secret_arn
                    ),
                },
            ),
        )

        connector_s3_get_lambda.function.role.add_to_policy(
            iam.PolicyStatement(
                actions=["s3:ListAllMyBuckets"],
                resources=[f"arn:aws:s3:::{account_id}:*"],
            )
        )

        connector_s3_resource.add_method(
            "GET",
            apigateway.LambdaIntegration(connector_s3_get_lambda.function),
            authorization_type=apigateway.AuthorizationType.COGNITO,
            authorizer=props.cognito_authorizer,
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
                    "X_ORIGIN_VERIFY_SECRET_ARN": (
                        props.x_origin_verify_secret.secret_arn
                    ),
                    "MEDIALAKE_CONNECTOR_TABLE": dynamo_table.table_arn,
                },
            ),
        )

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
            authorizer=props.cognito_authorizer,
        )

        s3_explorer_get_lambda.function.role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "s3:*",
                ],
                resources=[f"arn:aws:s3:::{account_id}:*"],
            )
        )

        s3_explorer_get_lambda.function.role.add_to_policy(
            iam.PolicyStatement(
                actions=["dynamodb:Scan", "dynamodb:Query", "dynamodb:GetItem"],
                resources=[dynamo_table.table_arn],
            )
        )
