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

from medialake_constructs.shared_constructs.lambda_layers import (
    IngestMediaProcessorLayer,
)


@dataclass
class ConnectorsProps:
    asset_table: dynamodb.TableV2
    iac_assets_bucket: s3.Bucket
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
        props: ConnectorsProps,
    ) -> None:
        super().__init__(scope, constructor_id)

        # Get the current account ID
        account_id = Stack.of(self).account

        lambda_iam_boundry_policy = iam.ManagedPolicy(
            self,
            "ServiceBoundaryPolicy",
            statements=[
                # Broad Allow for non-IAM actions
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "lambda:*",
                        "s3:*",
                        "sqs:*",
                        "sns:*",
                        "dynamodb:*",
                        "events:*",
                        "states:*",
                    ],
                    resources=["*"],
                ),
                # Unconditional Allow for specific IAM read-only actions
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "iam:GetRole",
                        "iam:ListRoles",
                        "iam:GetRolePolicy",
                        "iam:DetachRolePolicy",
                        "iam:DeleteRolePolicy",
                        "iam:DeleteRole",
                        "iam:ListRolePolicies",
                        "iam:ListAttachedRolePolicies",
                        "iam:CreateRole",
                        "iam:PutRolePolicy",
                        "iam:AttachRolePolicy",
                        "iam:UpdateRole",
                        "iam:UpdateRoleDescription",
                        "iam:TagRole",
                        "iam:UntagRole",
                        "iam:PassRole",
                    ],
                    resources=["*"],
                ),
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "kms:Decrypt",
                    ],
                    resources=["*"],
                ),
                # Conditional Allow for IAM write actions that involve passing roles
                # iam.PolicyStatement(
                #     effect=iam.Effect.ALLOW,
                #     actions=[
                #         "iam:CreateRole",
                #         "iam:PutRolePolicy",
                #         "iam:AttachRolePolicy",
                #         "iam:UpdateRole",
                #         "iam:UpdateRoleDescription",
                #         "iam:TagRole",
                #         "iam:UntagRole",
                #         "iam:PassRole",
                #     ],
                #     resources=["*"],
                #     conditions={
                #         "StringLike": {
                #             "iam:PassedToService": [
                #                 "lambda.amazonaws.com",
                #                 "s3.amazonaws.com",
                #                 "sqs.amazonaws.com",
                #                 "sns.amazonaws.com",
                #                 "dynamodb.amazonaws.com",
                #                 "events.amazonaws.com",
                #                 "states.amazonaws.com",
                #             ]
                #         }
                #     },
                # ),
            ],
        )

        # Create request validator
        body_validator = apigateway.RequestValidator(
            self,
            "BodyValidator",
            rest_api=props.api_resource,
            validate_request_parameters=False,
            validate_request_body=True,
            request_validator_name="body-only-validator",
        )

        # Create validators
        params_validator = apigateway.RequestValidator(
            self,
            "ParamsValidator",
            rest_api=props.api_resource,
            validate_request_parameters=True,
            validate_request_body=False,
            request_validator_name="params-only-validator",
        )

        request_model = apigateway.Model(
            self,
            "RequestModel",
            rest_api=props.api_resource,
            content_type="application/json",
            model_name="RequestModel",
            schema=apigateway.JsonSchema(
                type=apigateway.JsonSchemaType.OBJECT,
                required=["username"],
                properties={
                    "username": apigateway.JsonSchema(
                        type=apigateway.JsonSchemaType.STRING
                    ),
                    "age": apigateway.JsonSchema(type=apigateway.JsonSchemaType.NUMBER),
                },
            ),
        )

        self.lambda_deployment = LambdaDeployment(
            self,
            "IngestS3LambdaDeployment",
            destination_bucket=props.iac_assets_bucket.bucket,
            code_path=["lambdas", "ingest", "s3"],
        )

        self.dynamo_table = DynamoDB(
            self,
            "ConnectorsTable",
            props=DynamoDBProps(
                name=f"medialake_connector_table_{constructor_id}",
                partition_key_name="id",
                partition_key_type=dynamodb.AttributeType.STRING,
            ),
        )

        # Create connectors resource
        connectors_resource = props.api_resource.root.add_resource("connectors")

        # Add connector_id path parameter resource
        connector_id_resource = connectors_resource.add_resource("{connector_id}")

        connectors_get_lambda = Lambda(
            self,
            "ConnectorsGetLambda",
            config=LambdaConfig(
                name="connectors_get_lambda",
                entry="lambdas/api/connectors/get_connectors",
                environment_variables={
                    "X_ORIGIN_VERIFY_SECRET_ARN": (
                        props.x_origin_verify_secret.secret_arn
                    ),
                    "MEDIALAKE_CONNECTOR_TABLE": self.dynamo_table.table_arn,
                },
            ),
        )

        self.dynamo_table.table.grant_read_data(connectors_get_lambda.function)

        connectors_resource.add_method(
            "GET",
            apigateway.LambdaIntegration(connectors_get_lambda.function),
            authorization_type=apigateway.AuthorizationType.COGNITO,
            authorizer=props.cognito_authorizer,
        )

        connectors_del_lambda = Lambda(
            self,
            "ConnectorsDelLambda",
            config=LambdaConfig(
                name="connectors_del_lambda",
                entry="lambdas/api/connectors/rp_connectorId/del_connectorId",
                iam_role_boundary_policy=lambda_iam_boundry_policy,
                environment_variables={
                    "X_ORIGIN_VERIFY_SECRET_ARN": (
                        props.x_origin_verify_secret.secret_arn
                    ),
                    "MEDIALAKE_CONNECTOR_TABLE": self.dynamo_table.table_arn,
                },
            ),
        )

        self.dynamo_table.table.grant_read_write_data(connectors_del_lambda.function)

        connectors_del_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "lambda:DeleteFunction",
                    "lambda:DeleteEventSourceMapping",
                    "sqs:DeleteQueue",
                    "s3:DeleteBucketNotification",
                    "s3:ListBucket",
                    "s3:GetBucketLocation",
                ],
                resources=[
                    f"arn:aws:lambda:*:{account_id}:function:*",
                    f"arn:aws:lambda:*:{account_id}:event-source-mapping:*",
                    f"arn:aws:sqs:*:{account_id}:*",
                    "arn:aws:s3:::*",
                ],
            )
        )

        connectors_del_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "s3:PutBucketNotification",
                    "s3:GetBucketNotification",
                    "s3:DeleteBucketNotification",
                    "s3:ListBucket",
                    "s3:GetBucketLocation",
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
                    "iam:DeleteRolePolicy",
                    "iam:DetachRolePolicy",
                    "iam:ListAttachedRolePolicies",
                    "iam:ListRolePolicies",
                    "iam:GetRolePolicy",
                ],
                resources=[f"arn:aws:iam::{account_id}:role/*"],
            )
        )

        # SQS policy for s3 connectors lambda that builds SQS queues
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

        # POST connector
        ingest_media_processor_layer = IngestMediaProcessorLayer(
            self,
            "IngestMediaProcessorLayer",
        )

        connector_s3_post_lambda = Lambda(
            self,
            "ConnectorS3PostLambda",
            config=LambdaConfig(
                name="connector_s3_post",
                entry="lambdas/api/connectors/s3/post_s3",
                # iam_role_boundary_policy=lambda_iam_boundry_policy,
                environment_variables={
                    "X_ORIGIN_VERIFY_SECRET_ARN": props.x_origin_verify_secret.secret_arn,
                    "MEDIALAKE_CONNECTOR_TABLE": self.dynamo_table.table_arn,
                    "S3_CONNECTOR_LAMBDA": self.lambda_deployment.deployment_key,
                    "IAC_ASSETS_BUCKET": props.iac_assets_bucket.bucket.bucket_name,
                    "INGEST_MEDIA_PROCESSOR_LAYER": ingest_media_processor_layer.layer.layer_version_arn,
                    "INGEST_EVENT_BUS": props.ingest_event_bus.event_bus_name,
                    "MEDIALAKE_ASSET_TABLE": props.asset_table.table_arn,
                    "MEDIALAKE_ASSET_TABLE_FILE_HASH_INDEX": props.asset_table_file_hash_index_arn,
                    "MEDIALAKE_ASSET_TABLE_ASSET_ID_INDEX": props.asset_table_asset_id_index_arn,
                },
            ),
        )

        # props.resource_table.grant_read_write_data(connector_s3_post_lambda.function)

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

        props.iac_assets_bucket.bucket.grant_read_write(
            connector_s3_post_lambda.function
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
                    "arn:aws:lambda:*:*:layer:*:*",
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
                    "iam:ListAttachedRolePolicies",
                    "iam:CreateRole",
                    "iam:TagRole",
                    "iam:AttachRolePolicy",
                    "iam:DetachRolePolicy",
                    "iam:GetRole",
                ],
                resources=[f"arn:aws:iam::{account_id}:role/*"],
            )
        )

        # Grant permissions correctly
        props.iac_assets_bucket.bucket.grant_read_write(
            connector_s3_post_lambda.function
        )

        # Policy for DynamoDB actions on a specific table
        connector_s3_post_lambda.function.role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "dynamodb:PutItem",
                    "dynamodb:GetItem",
                    "dynamodb:UpdateItem",
                    "dynamodb:DeleteItem",
                    "dynamodb:Scan",
                ],
                resources=[self.dynamo_table.table_arn],
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

        # Policy for EventBridge actions
        connector_s3_post_lambda.function.role.add_to_policy(
            iam.PolicyStatement(
                actions=["events:PutRule", "events:PutTargets", "events:DeleteRule"],
                resources=[
                    f"arn:aws:events:{scope.region}:{account_id}:rule/*",
                ],
            )
        )

        connector_s3_resource.add_method(
            "POST",
            apigateway.LambdaIntegration(connector_s3_post_lambda.function),
            authorization_type=apigateway.AuthorizationType.COGNITO,
            authorizer=props.cognito_authorizer,
        )

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
                resources=["*"],
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
            "S3ExplorerGetLambda",
            config=LambdaConfig(
                name="s3_explorer_get",
                entry="lambdas/api/connectors/s3/explorer/rp_connector_id",
                environment_variables={
                    "X_ORIGIN_VERIFY_SECRET_ARN": (
                        props.x_origin_verify_secret.secret_arn
                    ),
                    "MEDIALAKE_CONNECTOR_TABLE": self.dynamo_table.table_arn,
                },
            ),
        )

        self.dynamo_table.table.grant_read_data(s3_explorer_get_lambda.function)
        s3_explorer_get_lambda.function.role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "s3:ListBucket",
                    "s3:GetBucketLocation",
                    "s3:ListBucketVersions",
                    "s3:GetObject",
                    "s3:ListBucketMultipartUploads",
                ],
                resources=[
                    "arn:aws:s3:::*",
                    "arn:aws:s3:::*/*",
                ],
            )
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

        self.dynamo_table.table.grant_read_data(s3_explorer_get_lambda.function)

    @property
    def connector_table(self) -> dynamodb.TableV2:

        return self.dynamo_table.table
