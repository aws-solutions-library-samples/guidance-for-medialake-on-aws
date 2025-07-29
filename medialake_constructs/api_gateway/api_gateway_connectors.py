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

from aws_cdk import Stack
from aws_cdk import aws_apigateway as apigateway
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_secretsmanager as secretsmanager
from aws_cdk import aws_ssm as ssm
from constructs import Construct

from config import config
from constants import DynamoDB as DynamoDBConstants
from constants import EnvVars
from medialake_constructs.api_gateway.api_gateway_utils import add_cors_options_method
from medialake_constructs.shared_constructs.dynamodb import (
    DynamoDB as DynamoDBConstruct,
)
from medialake_constructs.shared_constructs.dynamodb import (
    DynamoDBProps,
)
from medialake_constructs.shared_constructs.lam_deployment import LambdaDeployment
from medialake_constructs.shared_constructs.lambda_base import Lambda, LambdaConfig
from medialake_constructs.shared_constructs.lambda_layers import (
    IngestMediaProcessorLayer,
)


@dataclass
class ConnectorsProps:
    asset_table: dynamodb.TableV2
    iac_assets_bucket: s3.IBucket
    media_assets_bucket: s3.IBucket  # Added for cross-bucket deletion permissions
    asset_table_file_hash_index_arn: str
    asset_table_asset_id_index_arn: str
    asset_table_s3_path_index_arn: str
    asset_sync_job_table: dynamodb.TableV2
    asset_sync_engine_lambda: lambda_.Function
    open_search_endpoint: str
    opensearch_index: str
    pipelines_event_bus: str | None
    vpc_subnet_ids: str
    security_group_id: str

    # S3 Vector Store configuration
    s3_vector_bucket_name: str
    s3_vector_index_name: str = "media-vectors"

    # Optional fields
    api_resource: str | None = None
    cognito_authorizer: str | None = None
    x_origin_verify_secret: secretsmanager.Secret | None = None
    system_settings_table_name: str | None = None
    system_settings_table_arn: str | None = None


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
                # non-IAM permissions
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
                # CloudWatch and X-Ray permissions
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
                        "cloudwatch:PutMetricData",
                        "logs:CreateLogGroup",
                        "logs:CreateLogStream",
                        "logs:PutLogEvents",
                        "xray:PutTraceSegments",
                        "xray:PutTelemetryRecords",
                        "xray:GetSamplingRules",
                        "xray:GetSamplingTargets",
                        "xray:GetSamplingStatisticSummaries",
                    ],
                    resources=["*"],
                ),
                # KMS permissions
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "kms:Decrypt",
                    ],
                    resources=["*"],
                ),
                # IAM Role Management permissions
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "iam:ListRoles",
                        "iam:GetRole",
                        "iam:CreateRole",
                        "iam:DeleteRole",
                        "iam:PutRolePolicy",
                        "iam:DeleteRolePolicy",
                        "iam:AttachRolePolicy",
                        "iam:DetachRolePolicy",
                        "iam:UpdateRole",
                        "iam:UpdateRoleDescription",
                        "iam:TagRole",
                        "iam:UntagRole",
                        "iam:PassRole",
                    ],
                    resources=[
                        # f"arn:aws:iam::{account_id}:role/{config.resource_prefix}-*",
                        f"arn:aws:iam::{account_id}:role/*",
                    ],  # Restrict to roles with prefix
                    conditions={
                        "StringLike": {
                            "iam:PassedToService": [
                                "lambda.amazonaws.com",
                                "s3.amazonaws.com",
                                "sqs.amazonaws.com",
                                "sns.amazonaws.com",
                                "dynamodb.amazonaws.com",
                                "events.amazonaws.com",
                                "states.amazonaws.com",
                            ]
                        }
                    },
                ),
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

        self.connectors_table = DynamoDBConstruct(
            self,
            "ConnectorsTable",
            props=DynamoDBProps(
                name=DynamoDBConstants.connector_table_name(),
                partition_key_name="id",
                partition_key_type=dynamodb.AttributeType.STRING,
            ),
        )

        # Store connector table name in SSM for other stacks to reference
        ssm.StringParameter(
            self,
            "ConnectorTableNameParameter",
            parameter_name=f"/{config.resource_prefix}/connector-table-name",
            string_value=self.connectors_table.table.table_name,
            description="MediaLake Connector Table Name",
        )

        # Create connectors resource
        connectors_resource = props.api_resource.root.add_resource("connectors")

        # Add connector_id path parameter resource
        connector_id_resource = connectors_resource.add_resource("{connector_id}")

        connectors_get_lambda = Lambda(
            self,
            "ConnectorsGetLambda",
            config=LambdaConfig(
                name="connectors_get",
                entry="lambdas/api/connectors/get_connectors",
                environment_variables={
                    "X_ORIGIN_VERIFY_SECRET_ARN": (
                        props.x_origin_verify_secret.secret_arn
                    ),
                    "MEDIALAKE_CONNECTOR_TABLE": self.connectors_table.table_arn,
                },
            ),
        )

        self.connectors_table.table.grant_read_data(connectors_get_lambda.function)

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
                name="rp_connector_id_del",
                entry="lambdas/api/connectors/rp_connectorId/del_connectorId",
                # iam_role_boundary_policy=lambda_iam_boundry_policy,
                environment_variables={
                    "X_ORIGIN_VERIFY_SECRET_ARN": (
                        props.x_origin_verify_secret.secret_arn
                    ),
                    "MEDIALAKE_CONNECTOR_TABLE": self.connectors_table.table_arn,
                },
            ),
        )

        self.connectors_table.table.grant_read_write_data(
            connectors_del_lambda.function
        )

        connectors_del_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "lambda:DeleteFunction",
                    "lambda:DeleteEventSourceMapping",
                    "lambda:ListEventSourceMappings",
                    "sqs:DeleteQueue",
                    "s3:DeleteBucketNotification",
                    "s3:ListBucket",
                    "s3:GetBucketLocation",
                    "s3:DeleteBucket",
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
                    "iam:ListInstanceProfilesForRole",
                    "iam:GetRole",
                ],
                resources=[f"arn:aws:iam::{account_id}:role/*"],
            )
        )

        connectors_del_lambda.function.role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "events:ListTargetsByRule",
                    "events:DeleteRule",
                ],
                resources=[
                    f"arn:aws:events:{scope.region}:{account_id}:rule/*",
                ],
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

        # Add EventBridge Pipes permissions
        connectors_del_lambda.function.role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "pipes:DeletePipe",
                    "pipes:DescribePipe",
                    "pipes:ListPipes",
                    "pipes:StopPipe",
                    "pipes:TagResource",
                    "pipes:UntagResource",
                    "pipes:ListTagsForResource",
                ],
                resources=[f"arn:aws:pipes:{scope.region}:{account_id}:pipe/*"],
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

        # Prepare environment variables
        env_vars = {
            "X_ORIGIN_VERIFY_SECRET_ARN": props.x_origin_verify_secret.secret_arn,
            "MEDIALAKE_CONNECTOR_TABLE": self.connectors_table.table_arn,
            "S3_CONNECTOR_LAMBDA": self.lambda_deployment.deployment_key,
            "IAC_ASSETS_BUCKET": props.iac_assets_bucket.bucket.bucket_name,
            "MEDIA_ASSETS_BUCKET": props.media_assets_bucket.bucket.bucket_name,  # Added for cross-bucket deletion
            "INGEST_MEDIA_PROCESSOR_LAYER": ingest_media_processor_layer.layer.layer_version_arn,
            "PIPELINES_EVENT_BUS": props.pipelines_event_bus,
            "MEDIALAKE_ASSET_TABLE": props.asset_table.table_arn,
            "MEDIALAKE_ASSET_TABLE_FILE_HASH_INDEX": props.asset_table_file_hash_index_arn,
            "MEDIALAKE_ASSET_TABLE_ASSET_ID_INDEX": props.asset_table_asset_id_index_arn,
            "MEDIALAKE_ASSET_TABLE_S3_PATH_INDEX": props.asset_table_s3_path_index_arn,
            "RESOURCE_PREFIX": config.resource_prefix,
            "RESOURCE_APPLICATION_TAG": config.resource_application_tag,
            "REGION": config.primary_region,
            "OPENSEARCH_ENDPOINT": props.open_search_endpoint,
            "OPENSEARCH_INDEX": props.opensearch_index,
            "INDEX_NAME": props.opensearch_index,
            "OPENSEARCH_VPC_SUBNET_IDS": props.vpc_subnet_ids,
            "OPENSEARCH_SECURITY_GROUP_ID": props.security_group_id,
            # S3 Vector Store configuration
            "VECTOR_BUCKET_NAME": props.s3_vector_bucket_name,
            "VECTOR_INDEX_NAME": props.s3_vector_index_name,
        }

        connector_s3_post_lambda = Lambda(
            self,
            "ConnectorS3PostLambda",
            config=LambdaConfig(
                name="connectors_s3_post",
                entry="lambdas/api/connectors/s3/post_s3",
                memory_size=256,
                environment_variables=env_vars,
            ),
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
                    "lambda:DeleteEventSourceMapping",
                ],
                resources=[
                    f"arn:aws:lambda:*:{account_id}:function:*",
                    f"arn:aws:lambda:*:{account_id}:event-source-mapping:*",
                    "arn:aws:lambda:*:*:layer:*:*",
                ],
            )
        )

        # Add EC2 permissions for VPC Lambda creation
        connector_s3_post_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "ec2:CreateNetworkInterface",
                    "ec2:DescribeNetworkInterfaces",
                    "ec2:DeleteNetworkInterface",
                    "ec2:AttachNetworkInterface",
                    "ec2:DetachNetworkInterface",
                ],
                resources=[
                    f"arn:aws:ec2:{scope.region}:{account_id}:network-interface/*",
                    f"arn:aws:ec2:{scope.region}:{account_id}:subnet/*",
                    f"arn:aws:ec2:{scope.region}:{account_id}:security-group/*",
                ],
            )
        )

        # These EC2 actions are used by Lambda when deploying it into a VPC.
        # They allow the Lambda service to look up network configuration like VPCs, subnets, and security groups.
        #
        # These are **read-only** (describe) actions and do not allow modifying or deleting anything.
        # Because of how AWS permissions work, "describe" actions **cannot** be restricted to specific ARNs.
        # AWS requires that the `resources` field be set to `"*"` for these actions, since they operate across the account.
        #
        # It's safe to include these permissions because they only allow the Lambda to retrieve network info,
        # which is necessary for it to be deployed into a VPC.
        connector_s3_post_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "ec2:DescribeSecurityGroups",
                    "ec2:DescribeSubnets",
                    "ec2:DescribeVpcs",
                ],
                resources=["*"],  # Describe actions require * resource
            )
        )

        # Update IAM/S3 policy with account-specific ARNs
        connector_s3_post_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "s3:ListBucket",
                    "s3:GetBucketLocation",
                    "s3:PutBucketNotification",
                    "s3:GetBucketNotification",
                    "s3:DeleteBucketNotification",
                    "s3:GetBucketEncryption",
                    "s3:GetBucketPolicy",
                    "s3:GetEncryptionConfiguration",
                    "s3:CreateBucket",
                    "s3:PutBucketPublicAccessBlock",
                    "s3:PutEncryptionConfiguration",
                    "s3:GetBucketPublicAccessBlock",
                    "s3:DeleteBucket",
                    "s3:ListObjectsV2",
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

        # Add S3 Vector Store permissions for connector S3 post Lambda
        connector_s3_post_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "s3vectors:ListVectors",
                    "s3vectors:GetVectors",  # Required when returnMetadata=True
                    "s3vectors:DeleteVectors",
                    "s3vectors:QueryVectors",
                ],
                resources=[
                    f"arn:aws:s3vectors:{Stack.of(self).region}:{Stack.of(self).account}:bucket/{props.s3_vector_bucket_name}",
                    f"arn:aws:s3vectors:{Stack.of(self).region}:{Stack.of(self).account}:bucket/{props.s3_vector_bucket_name}/*",
                ],
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
                resources=[self.connectors_table.table_arn],
            )
        )
        # Policy for SNS actions
        connector_s3_post_lambda.function.role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "sns:CreateTopic",
                    "sns:DeleteTopic",
                    "sns:GetTopicAttributes",
                    "sns:SetTopicAttributes",
                    "sns:Publish",
                ],
                resources=[
                    f"arn:aws:sns:*:{account_id}:*",
                ],
            )
        )

        # Policy for EventBridge actions
        connector_s3_post_lambda.function.role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "events:PutRule",
                    "events:PutTargets",
                    "events:DeleteRule",
                    "events:RemoveTargets",
                ],
                resources=[
                    f"arn:aws:events:{scope.region}:{account_id}:rule/*",
                ],
            )
        )

        # Add EventBridge Pipes permissions
        connector_s3_post_lambda.function.role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "pipes:CreatePipe",
                    "pipes:DeletePipe",
                    "pipes:DescribePipe",
                    "pipes:ListPipes",
                    "pipes:StartPipe",
                    "pipes:StopPipe",
                    "pipes:UpdatePipe",
                    "pipes:TagResource",
                    "pipes:UntagResource",
                    "pipes:ListTagsForResource",
                ],
                resources=[f"arn:aws:pipes:{scope.region}:{account_id}:pipe/*"],
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
                    "SYSTEM_SETTINGS_TABLE_NAME": props.system_settings_table_name
                    or "",
                },
            ),
        )

        connector_s3_get_lambda.function.role.add_to_policy(
            iam.PolicyStatement(
                actions=["s3:ListAllMyBuckets"],
                resources=["*"],
            )
        )

        # Grant DynamoDB read permissions for system settings table
        if props.system_settings_table_arn:
            connector_s3_get_lambda.function.role.add_to_policy(
                iam.PolicyStatement(
                    actions=[
                        "dynamodb:GetItem",
                        "dynamodb:Query",
                    ],
                    resources=[props.system_settings_table_arn],
                )
            )

        connector_s3_resource.add_method(
            "GET",
            apigateway.LambdaIntegration(connector_s3_get_lambda.function),
            authorization_type=apigateway.AuthorizationType.COGNITO,
            authorizer=props.cognito_authorizer,
        )

        s3_sync_connector_resource = connector_id_resource.add_resource("sync")

        self._connector_sync_lambda = Lambda(
            self,
            "ConnectorSyncLambda",
            config=LambdaConfig(
                name="post_connector_sync",
                entry="lambdas/api/connectors/rp_connectorId/sync/post_sync",
                environment_variables={
                    "MEDIALAKE_CONNECTOR_TABLE": self.connectors_table.table_arn,
                    "MEDIALAKE_ASSET_TABLE": props.asset_table.table_arn,
                    "MEDIALAKE_ASSET_SYNC_JOB_TABLE_ARN": props.asset_sync_job_table.table_arn,
                    EnvVars.JOB_TABLE_NAME: props.asset_sync_job_table.table_name,
                    EnvVars.CONNECTOR_TABLE_NAME: DynamoDBConstants.connector_table_name(),
                    "ENGINE_FUNCTION_ARN": props.asset_sync_engine_lambda.function_arn,
                },
            ),
        )
        self.connectors_table.table.grant_read_data(
            self._connector_sync_lambda.function
        )
        props.asset_sync_job_table.grant_read_write_data(
            self._connector_sync_lambda.function
        )
        props.asset_sync_engine_lambda.grant_invoke(
            self._connector_sync_lambda.function
        )

        s3_sync_connector_resource.add_method(
            "POST",
            apigateway.LambdaIntegration(self._connector_sync_lambda.function),
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
                    "MEDIALAKE_CONNECTOR_TABLE": self.connectors_table.table_arn,
                },
            ),
        )

        self.connectors_table.table.grant_read_data(s3_explorer_get_lambda.function)
        s3_explorer_get_lambda.function.role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "s3:ListBucket",
                    "s3:GetBucketLocation",
                    "s3:ListBucketVersions",
                    "s3:GetObject",
                    "s3:ListBucketMultipartUploads",
                    "s3:GetBucketEncryption",
                    "s3:GetBucketPolicy",
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

        self.connectors_table.table.grant_read_data(s3_explorer_get_lambda.function)

        # Create storage/s3/buckets resource for get_buckets endpoint
        storage_resource = props.api_resource.root.add_resource("storage")
        storage_s3_resource = storage_resource.add_resource("s3")
        storage_buckets_resource = storage_s3_resource.add_resource("buckets")

        # Create get_buckets Lambda function
        get_buckets_lambda = Lambda(
            self,
            "GetBucketsLambda",
            config=LambdaConfig(
                name="get_buckets",
                entry="lambdas/api/storage/s3/buckets/get_buckets",
                environment_variables={
                    "X_ORIGIN_VERIFY_SECRET_ARN": props.x_origin_verify_secret.secret_arn,
                    "SYSTEM_SETTINGS_TABLE_NAME": props.system_settings_table_name
                    or "",
                },
            ),
        )

        # Grant S3 list buckets permission
        get_buckets_lambda.function.role.add_to_policy(
            iam.PolicyStatement(
                actions=["s3:ListAllMyBuckets"],
                resources=["*"],
            )
        )

        # Grant DynamoDB read permissions for system settings table
        if props.system_settings_table_arn:
            get_buckets_lambda.function.role.add_to_policy(
                iam.PolicyStatement(
                    actions=[
                        "dynamodb:GetItem",
                        "dynamodb:Query",
                    ],
                    resources=[props.system_settings_table_arn],
                )
            )

        # Add GET method to buckets resource
        storage_buckets_resource.add_method(
            "GET",
            apigateway.LambdaIntegration(get_buckets_lambda.function),
            authorization_type=apigateway.AuthorizationType.COGNITO,
            authorizer=props.cognito_authorizer,
        )

        # Store reference to get_buckets lambda for external configuration
        self._get_buckets_lambda = get_buckets_lambda

        # CORS support is handled by default_cors_preflight_options at the API Gateway level
        # No need to manually add OPTIONS methods as they're automatically added to all resources
        # add_cors_options_method(connectors_resource)
        # add_cors_options_method(connector_id_resource)
        # add_cors_options_method(connector_s3_resource)
        # add_cors_options_method(s3_sync_connector_resource)
        # add_cors_options_method(s3_explorer_resource)
        # add_cors_options_method(s3_explorer_connector_resource)

        aws_resource = props.api_resource.root.add_resource("aws")
        regions_resource = aws_resource.add_resource("regions")

        get_regions_lambda = Lambda(
            self,
            "GetAWSRegionsLambda",
            config=LambdaConfig(
                name="regions-get",
                entry="lambdas/api/aws/get_regions",
                environment_variables={
                    "X_ORIGIN_VERIFY_SECRET_ARN": (
                        props.x_origin_verify_secret.secret_arn
                    ),
                },
            ),
        )

        # Grant permission to describe regions
        get_regions_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=["ec2:DescribeRegions"],
                resources=["*"],
            )
        )

        regions_resource.add_method(
            "GET",
            apigateway.LambdaIntegration(get_regions_lambda.function),
            authorization_type=apigateway.AuthorizationType.COGNITO,
            authorizer=props.cognito_authorizer,
        )

        # CORS support is handled by default_cors_preflight_options at the API Gateway level
        # No need to manually add OPTIONS methods as they're automatically added to all resources
        add_cors_options_method(aws_resource)
        add_cors_options_method(regions_resource)
        add_cors_options_method(connector_id_resource)
        add_cors_options_method(connector_s3_resource)
        add_cors_options_method(s3_sync_connector_resource)
        add_cors_options_method(s3_explorer_resource)
        add_cors_options_method(s3_explorer_connector_resource)

    @property
    def connector_table(self) -> dynamodb.TableV2:
        return self.connectors_table.table

    @property
    def connector_sync_lambda(self) -> lambda_.Function:
        return self._connector_sync_lambda.function

    @property
    def get_buckets_lambda(self) -> lambda_.Function:
        return self._get_buckets_lambda.function
