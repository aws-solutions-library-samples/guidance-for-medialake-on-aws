"""
API Gateway Assets module for MediaLake.

This module defines the AssetsConstruct class which sets up API Gateway endpoints
for managing assets, including:
- GET /assets/{id} - Get asset details
- DELETE /assets/{id} - Delete an asset
- GET /assets/{id}/relatedversions - Get related versions of an asset
"""

from dataclasses import dataclass
from typing import Optional

from aws_cdk import Duration, RemovalPolicy, Stack
from aws_cdk import aws_apigateway as api_gateway
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_efs as efs
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda_event_sources as lambda_event_sources
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_secretsmanager as secretsmanager
from aws_cdk import aws_sqs as sqs
from aws_cdk import aws_stepfunctions as sfn
from aws_cdk import aws_stepfunctions_tasks as tasks
from constructs import Construct

from config import config
from medialake_constructs.api_gateway.api_gateway_utils import add_cors_options_method
from medialake_constructs.shared_constructs.lambda_base import Lambda, LambdaConfig
from medialake_constructs.shared_constructs.lambda_layers import (
    SearchLayer,
    ZipmergeLayer,
)


@dataclass
class AssetsProps:
    """Configuration for Assets API endpoints."""

    asset_table: dynamodb.TableV2
    api_resource: api_gateway.IResource
    cognito_authorizer: api_gateway.IAuthorizer
    x_origin_verify_secret: secretsmanager.Secret
    open_search_endpoint: str
    opensearch_index: str
    open_search_arn: str
    user_table: (
        dynamodb.Table
    )  # User table for bulk download jobs (replaces dedicated bulk download table)

    # S3 Vector Store configuration
    s3_vector_bucket_name: str

    # Optional fields (must come after required fields)
    vpc: Optional[ec2.IVpc] = None
    security_group: Optional[ec2.SecurityGroup] = None
    media_assets_bucket: Optional[s3.Bucket] = None
    s3_vector_index_name: str = "media-vectors"

    # Bulk download parameters
    small_file_threshold_mb: int = 1024  # Max size for a file to be considered "small"
    chunk_size_mb: int = 100  # Size of each chunk for large file processing
    max_small_file_concurrency: int = 1000  # Max Lambdas for processing small files
    max_large_chunk_concurrency: int = 100  # Max Lambdas processing large file chunks
    merge_batch_size: int = (
        100  # Number of zip files merged at once in intermediate stage
    )


class AssetsConstruct(Construct):
    """
    AWS CDK Construct for managing MediaLake assets API endpoints.

    This construct creates and configures:
    - API Gateway endpoints for asset operations
    - Lambda functions for handling asset requests
    - IAM roles and permissions for secure access
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        props: AssetsProps,
    ) -> None:
        super().__init__(scope, construct_id)

        Stack.of(self).region
        # Create assets resource and add {id} parameter
        self._assets_resource = props.api_resource.root.add_resource("assets")
        asset_resource = self._assets_resource.add_resource("{id}")

        search_layer = SearchLayer(self, "SearchLayer")

        # GET /assets Lambda
        get_assets_lambda = Lambda(
            self,
            "GetAssetsLambda",
            config=LambdaConfig(
                name="assets-get",
                entry="lambdas/api/assets/get_assets",
                layers=[search_layer.layer],
                environment_variables={
                    "X_ORIGIN_VERIFY_SECRET_ARN": props.x_origin_verify_secret.secret_arn,
                    "MEDIALAKE_ASSET_TABLE": props.asset_table.table_name,
                },
            ),
        )

        get_assets_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "s3:GetObject",
                    "kms:Decrypt",
                ],
                resources=[
                    "arn:aws:s3:::*/*",
                    "arn:aws:s3:::*",
                    "arn:aws:kms:*:*:key/*",
                ],
            )
        )

        # Add DynamoDB permissions for GET Lambda
        get_assets_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=["dynamodb:GetItem"],
                resources=[props.asset_table.table_arn],
            )
        )

        self._assets_resource.add_method(
            "GET",
            api_gateway.LambdaIntegration(get_assets_lambda.function),
            authorization_type=api_gateway.AuthorizationType.COGNITO,
            authorizer=props.cognito_authorizer,
        )
        # /{id} Lambda
        get_asset_lambda = Lambda(
            self,
            "GetAssetLambda",
            config=LambdaConfig(
                name="rp_asset_id_get",
                entry="lambdas/api/assets/rp_assets_id/get_assets",
                vpc=props.vpc,
                security_groups=[props.security_group],
                layers=[search_layer.layer],
                environment_variables={
                    "X_ORIGIN_VERIFY_SECRET_ARN": props.x_origin_verify_secret.secret_arn,
                    "MEDIALAKE_ASSET_TABLE": props.asset_table.table_name,
                    "OPENSEARCH_ENDPOINT": props.open_search_endpoint,
                    "OPENSEARCH_INDEX": props.opensearch_index,
                    "SCOPE": "es",
                },
            ),
        )

        get_asset_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "s3:GetObject",
                    "kms:Decrypt",
                ],
                resources=[
                    "arn:aws:s3:::*/*",  # Access to all objects in all buckets
                    "arn:aws:s3:::*",  # Access to all buckets
                    "arn:aws:kms:*:*:key/*",
                ],
            )
        )

        # DELETE /assets/{id} Lambda
        delete_asset_lambda = Lambda(
            self,
            "DeleteAssetLambda",
            config=LambdaConfig(
                name="rp_asset_id_delete",
                entry="lambdas/api/assets/rp_assets_id/del_assets",
                vpc=props.vpc,
                security_groups=[props.security_group],
                layers=[search_layer.layer],
                environment_variables={
                    "X_ORIGIN_VERIFY_SECRET_ARN": props.x_origin_verify_secret.secret_arn,
                    "MEDIALAKE_ASSET_TABLE": props.asset_table.table_name,
                    "OPENSEARCH_ENDPOINT": props.open_search_endpoint,
                    "INDEX_NAME": props.opensearch_index,
                    "VECTOR_BUCKET_NAME": props.s3_vector_bucket_name,
                    "VECTOR_INDEX_NAME": props.s3_vector_index_name,
                },
            ),
        )

        delete_asset_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "s3:GetObject",
                    "s3:PutObject",
                    "s3:DeleteObject",
                    "s3:CopyObject",
                ],
                resources=[
                    "arn:aws:s3:::*/*",  # Access to all objects in all buckets
                    "arn:aws:s3:::*",  # Access to all buckets
                ],
            )
        )

        # Add S3 Vector Store permissions for delete asset Lambda
        delete_asset_lambda.function.add_to_role_policy(
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

        # Add DynamoDB permissions for GET Lambda
        get_asset_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=["dynamodb:GetItem"],
                resources=[props.asset_table.table_arn],
            )
        )

        # Add EC2 permissions for VPC access
        get_asset_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "ec2:CreateNetworkInterface",
                    "ec2:DescribeNetworkInterfaces",
                    "ec2:DeleteNetworkInterface",
                ],
                resources=["*"],
            )
        )

        # Add OpenSearch permissions
        get_asset_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "es:ESHttpGet",
                    "es:ESHttpPost",
                    "es:ESHttpPut",
                    "es:ESHttpDelete",
                    "es:DescribeElasticsearchDomain",
                    "es:ListDomainNames",
                    "es:ESHttpHead",
                ],
                resources=[props.open_search_arn, f"{props.open_search_arn}/*"],
            )
        )

        # Add Secrets Manager permissions for potential API key access
        get_asset_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "secretsmanager:GetSecretValue",
                    "secretsmanager:DescribeSecret",
                ],
                resources=[props.x_origin_verify_secret.secret_arn],
            )
        )

        # Add DynamoDB permissions for DELETE Lambda
        delete_asset_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=["dynamodb:DeleteItem", "dynamodb:GetItem"],
                resources=[props.asset_table.table_arn],
            )
        )

        # Add OpenSearch permissions for DELETE Lambda
        delete_asset_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "es:ESHttpGet",
                    "es:ESHttpPost",
                    "es:ESHttpPut",
                    "es:ESHttpDelete",
                    "es:DescribeElasticsearchDomain",
                    "es:ListDomainNames",
                    "es:ESHttpHead",
                ],
                resources=[props.open_search_arn, f"{props.open_search_arn}/*"],
            )
        )

        # Add Secrets Manager permissions for DELETE Lambda
        delete_asset_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "secretsmanager:GetSecretValue",
                    "secretsmanager:DescribeSecret",
                ],
                resources=[props.x_origin_verify_secret.secret_arn],
            )
        )

        # Add EC2 permissions for VPC access for DELETE Lambda
        delete_asset_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "ec2:CreateNetworkInterface",
                    "ec2:DescribeNetworkInterfaces",
                    "ec2:DeleteNetworkInterface",
                ],
                resources=["*"],
            )
        )

        # Add GET method to /assets/{id}
        asset_resource.add_method(
            "GET",
            api_gateway.LambdaIntegration(
                get_asset_lambda.function,
                proxy=True,
                integration_responses=[
                    api_gateway.IntegrationResponse(
                        status_code="200",
                        response_parameters={
                            "method.response.header.Access-Control-Allow-Origin": "'*'",
                        },
                    )
                ],
            ),
            authorization_type=api_gateway.AuthorizationType.COGNITO,
            authorizer=props.cognito_authorizer,
            method_responses=[
                api_gateway.MethodResponse(
                    status_code="200",
                    response_parameters={
                        "method.response.header.Access-Control-Allow-Origin": True,
                    },
                )
            ],
        )

        # Add DELETE method to /assets/{id}
        asset_resource.add_method(
            "DELETE",
            api_gateway.LambdaIntegration(
                delete_asset_lambda.function,
                proxy=True,
                integration_responses=[
                    api_gateway.IntegrationResponse(
                        status_code="200",
                        response_parameters={
                            "method.response.header.Access-Control-Allow-Origin": "'*'",
                        },
                    )
                ],
            ),
            authorization_type=api_gateway.AuthorizationType.COGNITO,
            authorizer=props.cognito_authorizer,
            method_responses=[
                api_gateway.MethodResponse(
                    status_code="200",
                    response_parameters={
                        "method.response.header.Access-Control-Allow-Origin": True,
                    },
                )
            ],
        )

        # Add POST /assets/generate-presigned-url endpoint
        presigned_url_resource = self._assets_resource.add_resource(
            "generate-presigned-url"
        )
        generate_presigned_url_lambda = Lambda(
            self,
            "GeneratePresignedUrlLambda",
            config=LambdaConfig(
                name="generate_presigned_url",
                layers=[search_layer.layer],
                entry="lambdas/api/assets/generate_presigned_url",
                environment_variables={
                    "X_ORIGIN_VERIFY_SECRET_ARN": props.x_origin_verify_secret.secret_arn,
                    "MEDIALAKE_ASSET_TABLE": props.asset_table.table_name,
                },
            ),
        )

        # Add DynamoDB and S3 permissions for presigned URL Lambda
        generate_presigned_url_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=["dynamodb:GetItem"],
                resources=[props.asset_table.table_arn],
            )
        )
        generate_presigned_url_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "kms:Decrypt",
                    "kms:DescribeKey",
                ],
                resources=["*"],
            )
        )

        generate_presigned_url_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "s3:GetObject",
                    "s3:GetObjectVersion",
                ],
                resources=["arn:aws:s3:::*/*"],  # Access to all objects in all buckets
            )
        )

        # Add S3 bucket-level permissions for GetBucketLocation (required for region discovery)
        generate_presigned_url_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=["s3:GetBucketLocation"],
                resources=[
                    "arn:aws:s3:::*"
                ],  # Access to all buckets for location queries
            )
        )

        # Add POST method to /assets/generate-presigned-url
        presigned_url_resource.add_method(
            "POST",
            api_gateway.LambdaIntegration(
                generate_presigned_url_lambda.function,
                proxy=True,
                integration_responses=[
                    api_gateway.IntegrationResponse(
                        status_code="200",
                        response_parameters={
                            "method.response.header.Access-Control-Allow-Origin": "'*'",
                        },
                    )
                ],
            ),
            authorization_type=api_gateway.AuthorizationType.COGNITO,
            authorizer=props.cognito_authorizer,
            method_responses=[
                api_gateway.MethodResponse(
                    status_code="200",
                    response_parameters={
                        "method.response.header.Access-Control-Allow-Origin": True,
                    },
                )
            ],
        )

        # Add POST /assets/generate-presigned-url endpoint
        upload_resource = self._assets_resource.add_resource("upload")
        upload_lambda = Lambda(
            self,
            "UploadLambda",
            config=LambdaConfig(
                name="upload_asset",
                layers=[search_layer.layer],
                entry="lambdas/api/assets/upload/post_upload",
                environment_variables={
                    "X_ORIGIN_VERIFY_SECRET_ARN": props.x_origin_verify_secret.secret_arn,
                    "MEDIALAKE_ASSET_TABLE": props.asset_table.table_name,
                },
            ),
        )

        # Add DynamoDB and S3 permissions for presigned URL Lambda
        upload_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=["dynamodb:GetItem"],
                resources=[props.asset_table.table_arn],
            )
        )
        upload_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "kms:Decrypt",
                    "kms:DescribeKey",
                ],
                resources=["*"],
            )
        )

        upload_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "s3:GetObject",
                    "s3:GetObjectVersion",
                ],
                resources=["arn:aws:s3:::*/*"],  # Access to all objects in all buckets
            )
        )

        # Add POST method to /assets/upload
        upload_resource.add_method(
            "POST",
            api_gateway.LambdaIntegration(
                upload_lambda.function,
                proxy=True,
                integration_responses=[
                    api_gateway.IntegrationResponse(
                        status_code="200",
                        response_parameters={
                            "method.response.header.Access-Control-Allow-Origin": "'*'",
                        },
                    )
                ],
            ),
            authorization_type=api_gateway.AuthorizationType.COGNITO,
            authorizer=props.cognito_authorizer,
            method_responses=[
                api_gateway.MethodResponse(
                    status_code="200",
                    response_parameters={
                        "method.response.header.Access-Control-Allow-Origin": True,
                    },
                )
            ],
        )

        # Add POST /assets/{id}/rename endpoint
        rename_resource = asset_resource.add_resource("rename")
        rename_asset_lambda = Lambda(
            self,
            "RenameAssetLambda",
            config=LambdaConfig(
                name="rename_asset",
                layers=[search_layer.layer],
                entry="lambdas/api/assets/rp_assets_id/rename/post_rename",
                environment_variables={
                    "X_ORIGIN_VERIFY_SECRET_ARN": props.x_origin_verify_secret.secret_arn,
                    "MEDIALAKE_ASSET_TABLE": props.asset_table.table_name,
                },
            ),
        )

        # Add DynamoDB and S3 permissions for rename Lambda
        rename_asset_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "dynamodb:GetItem",
                    "dynamodb:PutItem",
                ],
                resources=[props.asset_table.table_arn],
            )
        )
        rename_asset_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "kms:Encrypt",
                    "kms:Decrypt",
                    "kms:ReEncrypt*",
                    "kms:GenerateDataKey*",
                    "kms:DescribeKey",
                ],
                resources=["*"],
            )
        )

        # Update the policy to allow access to all S3 buckets
        rename_asset_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "s3:GetObject",
                    "s3:PutObject",
                    "s3:DeleteObject",
                    "s3:ListBucket",
                    "s3:PutObjectTagging",
                    "s3:GetObjectTagging",  # Add missing permission for reading object tags
                    "s3:CopyObject",  # Add missing permission for copying objects
                ],
                resources=[
                    "arn:aws:s3:::*/*",  # Access to all objects in all buckets
                    "arn:aws:s3:::*",  # Access to all buckets
                ],
            )
        )

        # Add POST method to /assets/{id}/rename
        rename_resource.add_method(
            "POST",
            api_gateway.LambdaIntegration(
                rename_asset_lambda.function,
                proxy=True,
                integration_responses=[
                    api_gateway.IntegrationResponse(
                        status_code="200",
                        response_parameters={
                            "method.response.header.Access-Control-Allow-Origin": "'*'",
                        },
                    )
                ],
            ),
            authorization_type=api_gateway.AuthorizationType.COGNITO,
            authorizer=props.cognito_authorizer,
            method_responses=[
                api_gateway.MethodResponse(
                    status_code="200",
                    response_parameters={
                        "method.response.header.Access-Control-Allow-Origin": True,
                    },
                )
            ],
        )

        # Add GET /assets/{id}/relatedversions endpoint
        related_versions_resource = asset_resource.add_resource("relatedversions")
        related_versions_lambda = Lambda(
            self,
            "RelatedVersionsLambda",
            config=LambdaConfig(
                name="related_versions_get",
                vpc=props.vpc,
                security_groups=[props.security_group],
                layers=[search_layer.layer],
                entry="lambdas/api/assets/rp_assets_id/related_versions",
                environment_variables={
                    "X_ORIGIN_VERIFY_SECRET_ARN": props.x_origin_verify_secret.secret_arn,
                    "MEDIALAKE_ASSET_TABLE": props.asset_table.table_name,
                    "OPENSEARCH_ENDPOINT": props.open_search_endpoint,
                    "OPENSEARCH_INDEX": props.opensearch_index,
                    "SCOPE": "es",
                },
            ),
        )

        related_versions_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "ec2:CreateNetworkInterface",
                    "ec2:DescribeNetworkInterfaces",
                    "ec2:DeleteNetworkInterface",
                ],
                resources=["*"],
            )
        )

        # Add DynamoDB and S3 permissions for rename Lambda
        related_versions_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "dynamodb:GetItem",
                    "dynamodb:PutItem",
                ],
                resources=[props.asset_table.table_arn],
            )
        )

        related_versions_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "kms:Encrypt",
                    "kms:Decrypt",
                    "kms:ReEncrypt*",
                    "kms:GenerateDataKey*",
                    "kms:DescribeKey",
                ],
                resources=["*"],
            )
        )

        # Update the policy to allow access to all S3 buckets
        related_versions_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "s3:GetObject",
                    "s3:PutObject",
                    "s3:DeleteObject",
                    "s3:ListBucket",
                    "s3:PutObjectTagging",
                    "s3:GetBucketLocation",
                ],
                resources=[
                    "arn:aws:s3:::*/*",
                    "arn:aws:s3:::*",
                ],
            )
        )

        related_versions_resource.add_method(
            "GET",
            api_gateway.LambdaIntegration(related_versions_lambda.function),
            authorization_type=api_gateway.AuthorizationType.COGNITO,
            authorizer=props.cognito_authorizer,
        )

        related_versions_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "es:ESHttpGet",
                    "es:ESHttpPost",
                    "es:ESHttpPut",
                    "es:ESHttpDelete",
                    "es:DescribeElasticsearchDomain",
                    "es:ListDomainNames",
                    "es:ESHttpHead",
                ],
                resources=[props.open_search_arn, f"{props.open_search_arn}/*"],
            )
        )

        # Add GET /assets/{id}/transcript endpoint
        transcript_resource = asset_resource.add_resource("transcript")
        transcript_asset_lambda = Lambda(
            self,
            "TranscriptAssetLambda",
            config=LambdaConfig(
                name="transcript_asset",
                entry="lambdas/api/assets/rp_assets_id/transcript",
                environment_variables={
                    # "X_ORIGIN_VERIFY_SECRET_ARN": props.x_origin_verify_secret.secret_arn,
                    "MEDIALAKE_ASSET_TABLE": props.asset_table.table_name,
                },
            ),
        )

        # Add DynamoDB and S3 permissions for transcript Lambda
        transcript_asset_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "dynamodb:GetItem",
                ],
                resources=[props.asset_table.table_arn],
            )
        )
        # transcript_asset_lambda.function.add_to_role_policy(
        #     iam.PolicyStatement(
        #         actions=[
        #             "kms:Encrypt",
        #             "kms:Decrypt",
        #             "kms:ReEncrypt*",
        #             "kms:GenerateDataKey*",
        #             "kms:DescribeKey",
        #         ],
        #         resources=["*"],
        #     )
        # )

        # Update the policy to allow access to all S3 buckets
        transcript_asset_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "s3:GetObject",
                ],
                resources=[
                    "arn:aws:s3:::*/*",  # Access to all objects in all buckets
                    "arn:aws:s3:::*",  # Access to all buckets
                ],
            )
        )

        # Add GET method to /assets/{id}/transcript
        transcript_resource.add_method(
            "GET",
            api_gateway.LambdaIntegration(
                transcript_asset_lambda.function,
                proxy=True,
                integration_responses=[
                    api_gateway.IntegrationResponse(
                        status_code="200",
                        response_parameters={
                            "method.response.header.Access-Control-Allow-Origin": "'*'",
                        },
                    )
                ],
            ),
            authorization_type=api_gateway.AuthorizationType.COGNITO,
            authorizer=props.cognito_authorizer,
            method_responses=[
                api_gateway.MethodResponse(
                    status_code="200",
                    response_parameters={
                        "method.response.header.Access-Control-Allow-Origin": True,
                    },
                )
            ],
        )

        # Add CORS support to all API resources
        add_cors_options_method(self._assets_resource)
        add_cors_options_method(asset_resource)
        add_cors_options_method(presigned_url_resource)
        add_cors_options_method(rename_resource)
        add_cors_options_method(related_versions_resource)
        add_cors_options_method(transcript_resource)
        add_cors_options_method(upload_resource)

        # Add bulk download functionality if required props are provided
        if props.media_assets_bucket and props.vpc and props.security_group:
            self._create_bulk_download_resources(props)

    def _create_bulk_download_resources(self, props: AssetsProps):
        """
        Create resources for bulk download functionality.

        This method creates and configures:
        - EFS filesystem for temporary storage
        - Lambda functions for processing downloads
        - Step Functions state machine for orchestration
        - API Gateway endpoints for client interaction

        Note: Bulk download jobs are now stored in the user table using the pattern:
        itemKey: "BULK_DOWNLOAD#{job_id}#{reverse_timestamp}"
        """
        # Use the existing user table for bulk download jobs
        self._bulk_download_table = props.user_table

        # Create EFS filesystem for temporary storage
        self._efs_filesystem = efs.FileSystem(
            self,
            "AssetsBulkDownloadEFS",
            vpc=props.vpc,
            lifecycle_policy=efs.LifecyclePolicy.AFTER_7_DAYS,
            performance_mode=efs.PerformanceMode.GENERAL_PURPOSE,
            throughput_mode=efs.ThroughputMode.BURSTING,
            removal_policy=RemovalPolicy.DESTROY,
            security_group=props.security_group,
        )

        # Create access point for Lambda functions
        self._efs_access_point = self._efs_filesystem.add_access_point(
            "AssetsBulkDownloadAccessPoint",
            path="/bulk-downloads",
            create_acl=efs.Acl(
                owner_uid="1001",
                owner_gid="1001",
                permissions="750",
            ),
            posix_user=efs.PosixUser(
                uid="1001",
                gid="1001",
            ),
        )

        # Create Lambda functions
        self._create_bulk_download_lambda_functions(props)

        # Create Step Functions state machine
        # Pass the asset table name to the step functions workflow
        self._create_bulk_download_step_functions_workflow(
            props.asset_table.table_name, props
        )

        # Create API Gateway endpoints
        self._create_bulk_download_api_endpoints(props)

    def _create_bulk_download_lambda_functions(self, props: AssetsProps):
        """Create Lambda functions for bulk download processing."""
        # Create the ZipmergeLayer for fast ZIP merging
        ZipmergeLayer(self, "ZipmergeLayer")

        # Create SQS queue for multipart upload parts
        self._multipart_upload_queue = sqs.Queue(
            self,
            "MultipartUploadQueue",
            visibility_timeout=Duration.seconds(900),  # 15 minutes
            retention_period=Duration.days(14),  # Maximum retention period
        )

        # Common environment variables for all Lambda functions
        common_env_vars = {
            "USER_TABLE_NAME": props.user_table.table_name,  # Using user table for bulk download jobs
            "MEDIA_ASSETS_BUCKET": props.media_assets_bucket.bucket_name,
            "EFS_MOUNT_PATH": "/mnt/bulk-downloads",
            "USE_ZIPMERGE": "true",  # Enable the use of zipmerge binary
            "BATCH_SIZE": "5",  # Reduce batch size to prevent timeouts
            "FILE_MERGE_TIMEOUT": "120",  # 2 minute timeout per file merge
        }

        # Create Lambda for initializing zip file
        self._init_zip_lambda = Lambda(
            self,
            "AssetsBulkDownloadInitZipLambda",
            config=LambdaConfig(
                name="assets_bulk_download_init_zip",
                entry="lambdas/api/assets/download/bulk/post_bulk/init_zip",
                environment_variables={
                    **common_env_vars,
                },
                vpc=props.vpc,
                security_groups=[props.security_group],
                timeout_minutes=1,
                memory_size=512,
                filesystem_access_point=self._efs_access_point,
                filesystem_mount_path="/mnt/bulk-downloads",
            ),
        )

        # Create Lambda for appending to zip file
        self._append_to_zip_lambda = Lambda(
            self,
            "AssetsBulkDownloadAppendToZipLambda",
            config=LambdaConfig(
                name="assets_bulk_download_append_to_zip",
                entry="lambdas/api/assets/download/bulk/post_bulk/append_to_zip",
                environment_variables={
                    **common_env_vars,
                    "ASSET_TABLE": props.asset_table.table_name,
                    "CHUNK_SIZE_MB": str(props.chunk_size_mb),
                },
                vpc=props.vpc,
                security_groups=[props.security_group],
                timeout_minutes=5,
                memory_size=1024,
                filesystem_access_point=self._efs_access_point,
                filesystem_mount_path="/mnt/bulk-downloads",
            ),
        )

        # Create Lambda for initializing multipart upload
        self._init_multipart_lambda = Lambda(
            self,
            "AssetsBulkDownloadInitMultipartLambda",
            config=LambdaConfig(
                name="assets_bulk_download_init_multipart",
                entry="lambdas/api/assets/download/bulk/post_bulk/init_multipart",
                environment_variables={
                    **common_env_vars,
                },
                vpc=props.vpc,
                security_groups=[props.security_group],
                timeout_minutes=5,
                memory_size=1024,
                filesystem_access_point=self._efs_access_point,
                filesystem_mount_path="/mnt/bulk-downloads",
            ),
        )

        # Create Lambda for uploading parts
        self._upload_part_lambda = Lambda(
            self,
            "AssetsBulkDownloadUploadPartLambda",
            config=LambdaConfig(
                name="assets_bulk_download_upload_part",
                entry="lambdas/api/assets/download/bulk/post_bulk/upload_part",
                environment_variables={
                    **common_env_vars,
                    "SQS_QUEUE_URL": self._multipart_upload_queue.queue_url,
                },
                vpc=props.vpc,
                security_groups=[props.security_group],
                timeout_minutes=15,
                memory_size=1024,
                filesystem_access_point=self._efs_access_point,
                filesystem_mount_path="/mnt/bulk-downloads",
            ),
        )

        # Add SQS event source to the upload part Lambda
        self._upload_part_lambda.function.add_event_source(
            lambda_event_sources.SqsEventSource(
                self._multipart_upload_queue,
                batch_size=10,
                max_batching_window=Duration.seconds(30),
            )
        )

        # Create Lambda for completing multipart upload
        self._complete_multipart_lambda = Lambda(
            self,
            "AssetsBulkDownloadCompleteMultipartLambda",
            config=LambdaConfig(
                name="assets_bulk_download_complete_multipart",
                entry="lambdas/api/assets/download/bulk/post_bulk/complete_multipart",
                environment_variables={
                    **common_env_vars,
                },
                vpc=props.vpc,
                security_groups=[props.security_group],
                timeout_minutes=15,
                memory_size=1024,
                filesystem_access_point=self._efs_access_point,
                filesystem_mount_path="/mnt/bulk-downloads",
            ),
        )

        # UNUSED: Create Lambda for finalizing zip file (keep for backward compatibility)
        # self._finalize_zip_lambda = Lambda(
        #     self,
        #     "AssetsBulkDownloadFinalizeZipLambda",
        #     config=LambdaConfig(
        #         name="assets_bulk_download_finalize_zip",
        #         entry="lambdas/api/assets/download/bulk/post_bulk/finalize_zip",
        #         environment_variables={
        #             **common_env_vars,
        #         },
        #         vpc=props.vpc,
        #         security_groups=[props.security_group],
        #         timeout_minutes=15,
        #         memory_size=1024,
        #         filesystem_access_point=self._efs_access_point,
        #         filesystem_mount_path="/mnt/bulk-downloads",
        #     ),
        # )

        # Create Lambda for getting parts manifest
        self._get_parts_manifest_lambda = Lambda(
            self,
            "AssetsBulkDownloadGetPartsManifestLambda",
            config=LambdaConfig(
                name="assets_bulk_download_get_parts_manifest",
                entry="lambdas/api/assets/download/bulk/post_bulk/get_parts_manifest",
                environment_variables={
                    **common_env_vars,
                },
                timeout_minutes=1,
                memory_size=512,
            ),
        )

        # Kickoff Lambda
        self._kickoff_lambda = Lambda(
            self,
            "AssetsBulkDownloadKickoffLambda",
            config=LambdaConfig(
                name="assets_bulk_download_kickoff",
                entry="lambdas/api/assets/download/bulk/post_bulk",
                environment_variables={
                    **common_env_vars,
                },
                timeout_minutes=1,  # 1 minute timeout
            ),
        )

        # Assess Scale Lambda
        self._assess_scale_lambda = Lambda(
            self,
            "AssetsBulkDownloadAssessScaleLambda",
            config=LambdaConfig(
                name="assets_bulk_download_assess_scale",
                entry="lambdas/api/assets/download/bulk/post_bulk/assess_scale",
                environment_variables={
                    **common_env_vars,
                    "ASSET_TABLE": props.asset_table.table_name,
                    "SMALL_FILE_THRESHOLD": "100",  # MB
                    "LARGE_JOB_THRESHOLD": "1000",  # MB
                    "SINGLE_FILE_CHECK": "true",  # Enable single file check
                },
                timeout_minutes=1,
                memory_size=512,
            ),
        )

        # UNUSED: Create a custom Lambda function with EFS filesystem
        # self._handle_small_lambda = Lambda(
        #     self,
        #     "AssetsBulkDownloadHandleSmallLambda",
        #     config=LambdaConfig(
        #         name="assets_bulk_download_handle_small",
        #         entry="lambdas/api/assets/download/bulk/post_bulk/handle_small",
        #         environment_variables={
        #             **common_env_vars,
        #             "ASSET_TABLE": props.asset_table.table_name,
        #             "RESOURCE_PREFIX": config.resource_prefix,
        #             "ENVIRONMENT": config.environment,
        #             "METRICS_NAMESPACE": config.resource_prefix,
        #         },
        #         vpc=props.vpc,
        #         security_groups=[props.security_group],
        #         timeout_minutes=15,
        #         memory_size=10240,  # Maximum memory for Lambda to handle large files
        #         filesystem_access_point=self._efs_access_point,
        #         filesystem_mount_path="/mnt/bulk-downloads",
        #     ),
        # )

        # UNUSED: Handle Large Files Lambda
        # self._handle_large_lambda = Lambda(
        #     self,
        #     "AssetsBulkDownloadHandleLargeLambda",
        #     config=LambdaConfig(
        #         name="assets_bulk_download_handle_large",
        #         entry="lambdas/api/assets/download/bulk/post_bulk/handle_large",
        #         environment_variables={
        #             **common_env_vars,
        #             "ASSET_TABLE": props.asset_table.table_name,
        #         },
        #         vpc=props.vpc,
        #         security_groups=[props.security_group],
        #         timeout_minutes=15,
        #         memory_size=10240,  # Maximum memory for Lambda to handle large files
        #         filesystem_access_point=self._efs_access_point,
        #         filesystem_mount_path="/mnt/bulk-downloads",
        #     ),
        # )

        # UNUSED: Create Lambda for merging batches of zip files with ZipmergeLayer
        # self._merge_batch_lambda = Lambda(
        #     self,
        #     "AssetsBulkDownloadMergeBatchLambda",
        #     config=LambdaConfig(
        #         name="assets_bulk_download_merge_batch",
        #         entry="lambdas/api/assets/download/bulk/post_bulk/merge_batch",
        #         environment_variables={
        #             **common_env_vars,
        #             "RESOURCE_PREFIX": config.resource_prefix,
        #             "ENVIRONMENT": config.environment,
        #             "METRICS_NAMESPACE": config.resource_prefix,
        #         },
        #         layers=[zipmerge_layer.layer],  # Add the ZipmergeLayer
        #         vpc=props.vpc,
        #         security_groups=[props.security_group],
        #         timeout_minutes=15,
        #         memory_size=10240,  # Maximum memory for Lambda to handle large files
        #         filesystem_access_point=self._efs_access_point,
        #         filesystem_mount_path="/mnt/bulk-downloads",
        #     ),
        # )

        # UNUSED: Create Lambda for final merge of batch results with ZipmergeLayer
        # self._final_merge_lambda = Lambda(
        #     self,
        #     "AssetsBulkDownloadFinalMergeLambda",
        #     config=LambdaConfig(
        #         name="assets_bulk_download_final_merge",
        #         entry="lambdas/api/assets/download/bulk/post_bulk/final_merge",
        #         environment_variables={
        #             **common_env_vars,
        #             "RESOURCE_PREFIX": config.resource_prefix,
        #             "ENVIRONMENT": config.environment,
        #             "METRICS_NAMESPACE": config.resource_prefix,
        #         },
        #         layers=[zipmerge_layer.layer],  # Add the ZipmergeLayer
        #         vpc=props.vpc,
        #         security_groups=[props.security_group],
        #         timeout_minutes=15,
        #         memory_size=10240,  # Maximum memory for Lambda to handle large files
        #         filesystem_access_point=self._efs_access_point,
        #         filesystem_mount_path="/mnt/bulk-downloads",
        #     ),
        # )

        # Status Lambda
        self._status_lambda = Lambda(
            self,
            "AssetsBulkDownloadStatusLambda",
            config=LambdaConfig(
                name="assets_bulk_download_status",
                entry="lambdas/api/assets/download/bulk/rp_jobId/get_status",
                environment_variables={
                    **common_env_vars,
                },
                timeout_minutes=1,
            ),
        )

        # Mark Downloaded Lambda
        self._mark_downloaded_lambda = Lambda(
            self,
            "AssetsBulkDownloadMarkDownloadedLambda",
            config=LambdaConfig(
                name="assets_bulk_download_mark_downloaded",
                entry="lambdas/api/assets/download/bulk/rp_jobId/put_downloaded",
                environment_variables={
                    **common_env_vars,
                },
                timeout_minutes=1,
            ),
        )

        # Handle Large Individual Lambda
        self._handle_large_individual_lambda = Lambda(
            self,
            "AssetsBulkDownloadHandleLargeIndividualLambda",
            config=LambdaConfig(
                name="assets_bulk_large_individual",
                entry="lambdas/api/assets/download/bulk/post_bulk/handle_large_individual",
                environment_variables={
                    **common_env_vars,
                    "ASSET_TABLE": props.asset_table.table_name,
                },
                timeout_minutes=5,
                memory_size=1024,
            ),
        )

        # UNUSED: Complete Mixed Job Lambda
        # self._complete_mixed_job_lambda = Lambda(
        #     self,
        #     "AssetsBulkDownloadCompleteMixedJobLambda",
        #     config=LambdaConfig(
        #         name="assets_bulk_complete_mixed",
        #         entry="lambdas/api/assets/download/bulk/post_bulk/complete_mixed_job",
        #         environment_variables={
        #             **common_env_vars,
        #         },
        #         timeout_minutes=1,
        #         memory_size=512,
        #     ),
        # )

        # Delete Lambda
        self._delete_bulk_download_lambda = Lambda(
            self,
            "AssetsBulkDownloadDeleteLambda",
            config=LambdaConfig(
                name="assets_bulk_download_delete",
                entry="lambdas/api/assets/download/bulk/rp_jobId/delete_job",
                environment_variables={
                    **common_env_vars,
                    "TEMP_BUCKET": props.media_assets_bucket.bucket_name,  # For S3 cleanup
                },
                timeout_minutes=2,
                memory_size=512,
            ),
        )

        # Add permissions to Lambda functions
        self._add_bulk_download_lambda_permissions(props)

    def _add_bulk_download_lambda_permissions(self, props: AssetsProps):
        """Add necessary permissions to Lambda functions."""
        # DynamoDB permissions
        for lambda_function in [
            self._kickoff_lambda,
            self._assess_scale_lambda,
            # self._handle_small_lambda,  # UNUSED
            # self._handle_large_lambda,  # UNUSED
            # self._merge_batch_lambda,  # UNUSED
            # self._final_merge_lambda,  # UNUSED
            self._status_lambda,
            self._mark_downloaded_lambda,
            self._init_zip_lambda,
            self._append_to_zip_lambda,
            # self._finalize_zip_lambda,  # UNUSED
            self._init_multipart_lambda,
            self._upload_part_lambda,
            self._complete_multipart_lambda,
            self._get_parts_manifest_lambda,
            self._handle_large_individual_lambda,
            # self._complete_mixed_job_lambda,  # UNUSED
            self._delete_bulk_download_lambda,
        ]:
            lambda_function.function.add_to_role_policy(
                iam.PolicyStatement(
                    actions=[
                        "dynamodb:GetItem",
                        "dynamodb:PutItem",
                        "dynamodb:UpdateItem",
                        "dynamodb:DeleteItem",
                        "dynamodb:Query",
                    ],
                    resources=[
                        self._bulk_download_table.table_arn,
                        f"{self._bulk_download_table.table_arn}/index/*",  # Allow access to all GSIs (user table)
                    ],
                )
            )

        # Asset table permissions for assess scale and handler lambdas
        for lambda_function in [
            self._assess_scale_lambda,
            # self._handle_small_lambda,  # UNUSED
            # self._handle_large_lambda,  # UNUSED
            self._append_to_zip_lambda,
            self._handle_large_individual_lambda,
        ]:
            lambda_function.function.add_to_role_policy(
                iam.PolicyStatement(
                    actions=["dynamodb:GetItem", "dynamodb:BatchGetItem"],
                    resources=[props.asset_table.table_arn],
                )
            )

        # S3 permissions for handler and merge lambdas
        # Add EC2 permissions for VPC access to Lambda functions
        for lambda_function in [
            # self._handle_small_lambda,  # UNUSED
            # self._handle_large_lambda,  # UNUSED
            # self._merge_batch_lambda,  # UNUSED
            # self._final_merge_lambda,  # UNUSED
            self._init_zip_lambda,
            self._append_to_zip_lambda,
            # self._finalize_zip_lambda,  # UNUSED
            self._init_multipart_lambda,
            self._upload_part_lambda,
            self._complete_multipart_lambda,
        ]:
            lambda_function.function.add_to_role_policy(
                iam.PolicyStatement(
                    actions=[
                        "ec2:CreateNetworkInterface",
                        "ec2:DescribeNetworkInterfaces",
                        "ec2:DeleteNetworkInterface",
                    ],
                    resources=["*"],
                )
            )

        # Add S3 GetObject permission for all resources to handle_small_lambda and handle_large_lambda
        for lambda_function in [
            # self._handle_small_lambda,  # UNUSED
            # self._handle_large_lambda,  # UNUSED
            self._append_to_zip_lambda,
            self._handle_large_individual_lambda,
        ]:
            lambda_function.function.add_to_role_policy(
                iam.PolicyStatement(
                    actions=[
                        "s3:GetObject",
                        "s3:HeadObject",
                    ],
                    resources=["*"],
                )
            )

        # KMS permissions are now consolidated below

        # Add S3 permissions for handler and merge lambdas
        for lambda_function in [
            # self._handle_small_lambda,  # UNUSED
            # self._handle_large_lambda,  # UNUSED
            # self._merge_batch_lambda,  # UNUSED
            # self._final_merge_lambda,  # UNUSED
            self._append_to_zip_lambda,
            # self._finalize_zip_lambda,  # UNUSED
            self._init_multipart_lambda,
            self._upload_part_lambda,
            self._complete_multipart_lambda,
            self._get_parts_manifest_lambda,
            self._delete_bulk_download_lambda,
        ]:
            lambda_function.function.add_to_role_policy(
                iam.PolicyStatement(
                    actions=[
                        "s3:GetObject",
                        "s3:PutObject",
                        "s3:DeleteObject",
                        "s3:ListBucket",
                    ],
                    resources=[
                        props.media_assets_bucket.bucket_arn,
                        f"{props.media_assets_bucket.bucket_arn}/*",
                    ],
                )
            )
        # Add comprehensive KMS permissions for all Lambda functions that interact with S3
        for lambda_function in [
            # self._handle_small_lambda,  # UNUSED
            # self._handle_large_lambda,  # UNUSED
            # self._merge_batch_lambda,  # UNUSED
            # self._final_merge_lambda,  # UNUSED
            self._append_to_zip_lambda,
            # self._finalize_zip_lambda,  # UNUSED
            self._init_multipart_lambda,
            self._upload_part_lambda,
            self._complete_multipart_lambda,
            self._get_parts_manifest_lambda,
            self._handle_large_individual_lambda,
        ]:
            lambda_function.function.add_to_role_policy(
                iam.PolicyStatement(
                    actions=[
                        "kms:GenerateDataKey",
                        "kms:Decrypt",
                        "kms:Encrypt",
                        "kms:ReEncrypt*",
                        "kms:DescribeKey",
                    ],
                    resources=["*"],
                )
            )

        # Step Functions permissions will be added after Step Function creation

        # Add SQS permissions for the upload part Lambda
        self._multipart_upload_queue.grant_send_messages(
            self._init_multipart_lambda.function
        )
        self._multipart_upload_queue.grant_consume_messages(
            self._upload_part_lambda.function
        )

        # Add Step Functions permissions for the upload part Lambda
        self._upload_part_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "states:SendTaskSuccess",
                    "states:SendTaskFailure",
                ],
                resources=["*"],  # Will be restricted after state machine creation
            )
        )

    def _create_bulk_download_step_functions_workflow(
        self, asset_table_name=None, props=None
    ):
        """Create Step Functions state machine for orchestrating the bulk download process."""
        # Define task states
        assess_scale_task = tasks.LambdaInvoke(
            self,
            "AssetsAssessScaleTask",
            lambda_function=self._assess_scale_lambda.function,
            output_path="$.Payload",
        )

        # Define task to initialize zip file
        init_zip_task = tasks.LambdaInvoke(
            self,
            "AssetsInitZipTask",
            lambda_function=self._init_zip_lambda.function,
            payload=sfn.TaskInput.from_object(
                {
                    "jobId.$": "$.jobId",
                    "userId.$": "$.userId",
                }
            ),
            result_path="$.zipInfo",
        )

        # Add a debug state to log the structure of the Lambda response
        debug_state = sfn.Pass(
            self,
            "DebugZipInfo",
            parameters={
                "zipInfo.$": "$.zipInfo",
                "debug": "Debugging zipInfo structure",
            },
            result_path="$.debug",
        )

        # Add a Pass state to extract zipPath from init_zip_task result and preserve context
        extract_zip_path = sfn.Pass(
            self,
            "ExtractZipPath",
            parameters={
                "jobId.$": "$.jobId",
                "userId.$": "$.userId",
                "zipPath.$": "$.zipInfo.Payload.zipPath",
                "smallFiles.$": "$.smallFiles",
                "largeFiles.$": "$.largeFiles",
                "jobType.$": "$.jobType",
                "totalSize.$": "$.totalSize",
                "smallFilesCount.$": "$.smallFilesCount",
                "largeFilesCount.$": "$.largeFilesCount",
                "foundAssets.$": "$.foundAssets",
                "missingAssets.$": "$.missingAssets",
                "options.$": "$.options",
            },
        )

        # Define Map state for small files with concurrency control
        small_files_map = sfn.Map(
            self,
            "ProcessSmallFilesMap",
            max_concurrency=1,  # Limit to 1 to prevent concurrent file access issues
            items_path="$.smallFiles",
            result_path="$.processedFiles",
            item_selector={
                "jobId.$": "$.jobId",
                "userId.$": "$.userId",
                "zipPath.$": "$.zipPath",
                "mapItem.$": "$$.Map.Item.Value",
            },
        ).item_processor(
            tasks.LambdaInvoke(
                self,
                "AppendSmallFileTask",
                lambda_function=self._append_to_zip_lambda.function,
                payload=sfn.TaskInput.from_object(
                    {
                        "jobId.$": "$.jobId",
                        "userId.$": "$.userId",
                        "assetId.$": "$.mapItem.assetId",
                        "options.$": "$.mapItem.options",
                        "zipPath.$": "$.zipPath",
                    }
                ),
                output_path="$.Payload",
            )
        )

        # Define Map state for large files - now generates presigned URLs instead of chunking
        large_files_map = sfn.Map(
            self,
            "ProcessLargeFilesMap",
            max_concurrency=5,  # Can process more in parallel since we're just generating URLs
            items_path="$.largeFiles",
            result_path="$.largeFileUrls",
            item_selector={
                "jobId.$": "$.jobId",
                "userId.$": "$.userId",
                "largeFile.$": "$$.Map.Item.Value",  # Pass individual large file
                "options.$": "$.options",
            },
        ).item_processor(
            tasks.LambdaInvoke(
                self,
                "GenerateLargeFileUrlTask",
                lambda_function=self._handle_large_individual_lambda.function,
                payload=sfn.TaskInput.from_object(
                    {
                        "jobId.$": "$.jobId",
                        "userId.$": "$.userId",
                        "largeFiles.$": "States.Array($.largeFile)",  # Convert single file to array format
                        "options.$": "$.options",
                    }
                ),
                output_path="$.Payload",
            )
        )

        # Define task to initialize multipart upload
        init_multipart_task = tasks.LambdaInvoke(
            self,
            "AssetsInitMultipartTask",
            lambda_function=self._init_multipart_lambda.function,
            payload=sfn.TaskInput.from_object(
                {
                    "jobId.$": "$.jobId",
                    "userId.$": "$.userId",
                    "zipPath.$": "$.zipPath",
                }
            ),
            result_path="$.multipartInfo",
        )

        # Define a Pass state to extract multipart upload info
        extract_multipart_info = sfn.Pass(
            self,
            "ExtractMultipartInfo",
            parameters={
                "jobId.$": "$.jobId",
                "userId.$": "$.userId",
                "zipPath.$": "$.zipPath",
                "uploadId.$": "$.multipartInfo.Payload.uploadId",
                "s3Key.$": "$.multipartInfo.Payload.s3Key",
                "manifestKey.$": "$.multipartInfo.Payload.manifestKey",
                "numParts.$": "$.multipartInfo.Payload.numParts",
                "partSize.$": "$.multipartInfo.Payload.partSize",
                "fileSize.$": "$.multipartInfo.Payload.fileSize",
                "largeFileUrls.$": "$.largeFileUrls",
            },
        )

        # Define a task to get parts from the manifest for the specified range
        get_batch_parts = tasks.LambdaInvoke(
            self,
            "GetBatchPartsTask",
            lambda_function=self._get_parts_manifest_lambda.function,
            payload=sfn.TaskInput.from_object(
                {
                    "jobId.$": "$.jobId",
                    "manifestKey.$": "$.manifestKey",
                    "startPart.$": "$.startPart",
                    "endPart.$": "$.endPart",
                }
            ),
            result_path="$.batchParts",
        )

        # Define a Map state for processing parts in parallel
        process_parts_map = sfn.Map(
            self,
            "ProcessPartsMap",
            max_concurrency=10,  # Process up to 10 parts in parallel
            items_path="$.batchParts.Payload.parts",
            result_path="$.completedParts",
            parameters={
                "jobId.$": "$.jobId",
                "userId.$": "$.userId",
                "uploadId.$": "$.uploadId",
                "s3Key.$": "$.s3Key",
                "manifestKey.$": "$.manifestKey",
                "part.$": "$$.Map.Item.Value",
            },
        ).iterator(
            tasks.SqsSendMessage(
                self,
                "SendPartMessage",
                queue=self._multipart_upload_queue,
                message_body=sfn.TaskInput.from_object(
                    {
                        "taskToken": sfn.JsonPath.task_token,
                        "part": {
                            "jobId.$": "$.jobId",
                            "userId.$": "$.userId",
                            "uploadId.$": "$.uploadId",
                            "s3Key.$": "$.s3Key",
                            "manifestKey.$": "$.manifestKey",
                            "partNumber.$": "$.part.partNumber",
                            "startByte.$": "$.part.startByte",
                            "endByte.$": "$.part.endByte",
                            "localPath.$": "$.part.localPath",
                        },
                    }
                ),
                integration_pattern=sfn.IntegrationPattern.WAIT_FOR_TASK_TOKEN,
                timeout=Duration.minutes(
                    5
                ),  # Set a 5-minute timeout for each part upload
            )
        )

        # Define task to complete multipart upload
        complete_multipart_task = tasks.LambdaInvoke(
            self,
            "AssetsCompleteMultipartTask",
            lambda_function=self._complete_multipart_lambda.function,
            payload=sfn.TaskInput.from_object(
                {
                    "jobId.$": "$.jobId",
                    "userId.$": "$.userId",
                    "uploadId.$": "$.uploadId",
                    "s3Key.$": "$.s3Key",
                    "manifestKey.$": "$.manifestKey",
                    "completedParts.$": "$.completedParts",
                    "largeFileUrls.$": "$.largeFileUrls",
                }
            ),
            output_path="$.Payload",
        )

        # Create a new Lambda for handling single file downloads
        self._single_file_lambda = Lambda(
            self,
            "AssetsBulkDownloadSingleFileLambda",
            config=LambdaConfig(
                name="assets_bulk_download_single_file",
                entry="lambdas/api/assets/download/bulk/post_bulk/single_file",
                environment_variables={
                    "USER_TABLE_NAME": self._bulk_download_table.table_name,
                    "ASSET_TABLE": asset_table_name,
                },
                timeout_minutes=1,
                memory_size=512,
            ),
        )

        # Add necessary permissions to the single file Lambda
        self._single_file_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "dynamodb:GetItem",
                    "dynamodb:UpdateItem",
                ],
                resources=[self._bulk_download_table.table_arn],
            )
        )

        self._single_file_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=["kms:Decrypt"],
                resources=[
                    "*"
                ],  # Use a wildcard for now since we don't have the exact ARN
            )
        )

        self._single_file_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=["dynamodb:GetItem"],
                resources=[
                    "*"
                ],  # Use a wildcard for now since we don't have the exact ARN
            )
        )

        self._single_file_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "s3:GetObject",
                    "s3:HeadObject",
                ],
                resources=["*"],
            )
        )

        # Create a task for the single file Lambda
        single_file_task = tasks.LambdaInvoke(
            self,
            "AssetsSingleFileTask",
            lambda_function=self._single_file_lambda.function,
            output_path="$.Payload",
        )

        # Create a task for handling large files individually
        handle_large_individual_task = tasks.LambdaInvoke(
            self,
            "AssetsHandleLargeIndividualTask",
            lambda_function=self._handle_large_individual_lambda.function,
            output_path="$.Payload",
        )

        # UNUSED: Create a task for completing mixed jobs
        # complete_mixed_job_task = tasks.LambdaInvoke(
        #     self,
        #     "AssetsCompleteMixedJobTask",
        #     lambda_function=self._complete_mixed_job_lambda.function,
        #     output_path="$.Payload",
        # )

        # Define choice state for job size decision
        job_size_choice = sfn.Choice(self, "AssetsJobSizeDecision")

        # Define success and failure states
        success_state = sfn.Succeed(self, "StreamingDownloadJobSucceeded")
        fail_state = sfn.Fail(
            self, "StreamingDownloadJobFailed", cause="Job processing failed"
        )

        # Define success and failure states
        success_state = sfn.Succeed(self, "AssetsDownloadJobSucceeded")
        fail_state = sfn.Fail(
            self, "AssetsDownloadJobFailed", cause="Job processing failed"
        )

        # For SMALL and LARGE job types, we need to process both small and large files
        # Create a workflow that initializes the zip file, processes files, and finalizes the zip
        # Add a Pass state to transform the output of the Parallel state
        restore_context = sfn.Pass(
            self,
            "RestoreContext",
            parameters={
                "jobId.$": "$.jobId",
                "userId.$": "$.userId",
                "zipPath.$": "$.zipPath",
                "parallelResults.$": "$.parallelResults",
            },
        )

        # Add a Choice state to conditionally extract largeFileUrls
        extract_large_file_urls = sfn.Choice(self, "ExtractLargeFileUrls")

        # Pass state for when large files exist
        extract_with_large_files = sfn.Pass(
            self,
            "ExtractWithLargeFiles",
            parameters={
                "jobId.$": "$.jobId",
                "userId.$": "$.userId",
                "zipPath.$": "$.zipPath",
                "largeFileUrls.$": "$.parallelResults[1].largeFileUrls[0].largeFileUrls",
            },
        )

        # Pass state for when no large files exist
        extract_without_large_files = sfn.Pass(
            self,
            "ExtractWithoutLargeFiles",
            parameters={
                "jobId.$": "$.jobId",
                "userId.$": "$.userId",
                "zipPath.$": "$.zipPath",
                "largeFileUrls": [],
            },
        )

        # Configure the choice logic - check if large file URLs actually exist and contain URLs
        extract_large_file_urls.when(
            sfn.Condition.and_(
                sfn.Condition.is_present("$.parallelResults[1].largeFileUrls"),
                sfn.Condition.is_present("$.parallelResults[1].largeFileUrls[0]"),
                sfn.Condition.is_present(
                    "$.parallelResults[1].largeFileUrls[0].largeFileUrls"
                ),
                sfn.Condition.is_present(
                    "$.parallelResults[1].largeFileUrls[0].largeFileUrls[0]"
                ),
            ),
            extract_with_large_files,
        ).otherwise(extract_without_large_files)

        # Both branches converge to init_multipart_task
        extract_with_large_files.next(init_multipart_task)
        extract_without_large_files.next(init_multipart_task)
        init_multipart_task.next(extract_multipart_info)

        # Define a new workflow for multipart upload
        multipart_workflow = (
            init_zip_task.next(debug_state)
            .next(extract_zip_path)
            .next(
                sfn.Parallel(
                    self,
                    "ProcessFilesInParallel",
                    result_path="$.parallelResults",  # Store results in a field to preserve original context
                )
                .branch(
                    # Process small files if there are any
                    sfn.Choice(self, "CheckSmallFiles")
                    .when(sfn.Condition.is_present("$.smallFiles[0]"), small_files_map)
                    .otherwise(sfn.Pass(self, "NoSmallFiles"))
                )
                .branch(
                    # Process large files if there are any
                    sfn.Choice(self, "CheckLargeFiles")
                    .when(sfn.Condition.is_present("$.largeFiles[0]"), large_files_map)
                    .otherwise(sfn.Pass(self, "NoLargeFiles"))
                )
            )
            .next(restore_context)
            .next(extract_large_file_urls)
        )

        # Get parts manifest using Lambda instead of direct S3 integration
        get_parts_manifest = tasks.LambdaInvoke(
            self,
            "GetPartsManifestTask",
            lambda_function=self._get_parts_manifest_lambda.function,
            payload=sfn.TaskInput.from_object(
                {
                    "jobId.$": "$.jobId",
                    "manifestKey.$": "$.manifestKey",
                }
            ),
            result_path="$.partsManifest",
        )

        # Add the parts manifest to the state
        add_parts_to_state = sfn.Pass(
            self,
            "AddPartsToState",
            parameters={
                "jobId.$": "$.jobId",
                "userId.$": "$.userId",
                "zipPath.$": "$.zipPath",
                "uploadId.$": "$.uploadId",
                "s3Key.$": "$.s3Key",
                "manifestKey.$": "$.manifestKey",
                "totalParts.$": "$.partsManifest.Payload.totalParts",
                "partBatches.$": "$.partsManifest.Payload.partBatches",
                "largeFileUrls.$": "$.largeFileUrls",
            },
        )

        # Define a Map state for processing part batches
        process_batches_map = sfn.Map(
            self,
            "ProcessBatchesMap",
            max_concurrency=5,  # Process up to 5 batches in parallel
            items_path="$.partBatches",
            result_path="$.batchResults",
            parameters={
                "jobId.$": "$.jobId",
                "userId.$": "$.userId",
                "uploadId.$": "$.uploadId",
                "s3Key.$": "$.s3Key",
                "manifestKey.$": "$.manifestKey",
                "batch.$": "$$.Map.Item.Value",
            },
        ).iterator(
            # For each batch, get the parts and process them
            sfn.Pass(
                self,
                "PrepareBatchParts",
                parameters={
                    "jobId.$": "$.jobId",
                    "userId.$": "$.userId",
                    "uploadId.$": "$.uploadId",
                    "s3Key.$": "$.s3Key",
                    "manifestKey.$": "$.manifestKey",
                    "startPart.$": "$.batch.startPart",
                    "endPart.$": "$.batch.endPart",
                },
            )
            .next(
                # Get parts from the manifest for the specified range
                get_batch_parts
            )
            .next(
                # Process the parts in the batch
                process_parts_map
            )
        )

        # Add a Pass state to flatten completed parts from all batches
        flatten_completed_parts = sfn.Pass(
            self,
            "FlattenCompletedParts",
            parameters={
                "jobId.$": "$.jobId",
                "userId.$": "$.userId",
                "uploadId.$": "$.uploadId",
                "s3Key.$": "$.s3Key",
                "manifestKey.$": "$.manifestKey",
                "completedParts.$": "$.batchResults[*].completedParts[*]",
                "largeFileUrls.$": "$.largeFileUrls",
            },
        )

        # Add Pass states for handling large file URLs
        flatten_with_large_files = sfn.Pass(
            self,
            "FlattenWithLargeFiles",
            parameters={
                "jobId.$": "$.jobId",
                "userId.$": "$.userId",
                "uploadId.$": "$.uploadId",
                "s3Key.$": "$.s3Key",
                "manifestKey.$": "$.manifestKey",
                "completedParts.$": "$.completedParts",
                "largeFileUrls.$": "$.largeFileUrls",
            },
        ).next(complete_multipart_task)

        no_large_file_urls = sfn.Pass(
            self,
            "NoLargeFileUrls",
            parameters={
                "jobId.$": "$.jobId",
                "userId.$": "$.userId",
                "uploadId.$": "$.uploadId",
                "s3Key.$": "$.s3Key",
                "manifestKey.$": "$.manifestKey",
                "completedParts.$": "$.completedParts",
                "largeFileUrls": [],
            },
        ).next(complete_multipart_task)

        # Add a Choice state to safely handle large file URLs
        check_large_file_urls = (
            sfn.Choice(self, "CheckForLargeFileUrls")
            .when(
                sfn.Condition.is_present("$.largeFileUrls[0]"), flatten_with_large_files
            )
            .otherwise(no_large_file_urls)
        )

        # Complete the workflow - start from extract_multipart_info since multipart_workflow ends with a Choice state
        extract_multipart_info.next(get_parts_manifest).next(add_parts_to_state).next(
            process_batches_map
        ).next(flatten_completed_parts)

        # Connect flatten_completed_parts to the choice state
        flatten_completed_parts.next(check_large_file_urls)

        # Connect complete multipart task to success state
        complete_multipart_task.next(success_state)

        # Simplified approach - reuse existing workflow structure
        # The key change is that ProcessLargeFilesMap now generates presigned URLs instead of chunking

        # Build the simplified main workflow
        # All job types except SINGLE_FILE use the same multipart workflow
        # The difference is in how ProcessLargeFilesMap handles large files (presigned URLs vs chunking)
        workflow = assess_scale_task.next(
            job_size_choice.when(
                sfn.Condition.string_equals("$.jobType", "SINGLE_FILE"),
                single_file_task.next(success_state),
            )
            .when(
                sfn.Condition.string_equals("$.jobType", "LARGE_INDIVIDUAL"),
                handle_large_individual_task.next(success_state),
            )
            .otherwise(
                multipart_workflow
            )  # Used for SMALL, MIXED, and legacy job types
        )

        # Note: single_file_task already connected to success_state in the workflow definition

        # Final merge task is already connected to success_state in the workflow definition

        # Create the state machine using the non-deprecated API
        self._state_machine = sfn.StateMachine(
            self,
            "AssetsBulkDownloadStateMachine",
            state_machine_name=f"{config.resource_prefix}_Asset-Bulk-Download",
            definition_body=sfn.DefinitionBody.from_chainable(workflow),
            timeout=Duration.hours(6),  # Increase timeout for large file processing
        )

        # Update the Kickoff Lambda with the state machine ARN
        self._kickoff_lambda.function.add_environment(
            "STEP_FUNCTION_ARN", self._state_machine.state_machine_arn
        )

        # Update the Step Functions permission in the Kickoff Lambda
        self._kickoff_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=["states:StartExecution"],
                resources=[self._state_machine.state_machine_arn],
            )
        )

        # Add permissions to the state machine
        self._add_state_machine_permissions()

    def _add_state_machine_permissions(self):
        """Add necessary permissions to the state machine role."""
        # Add KMS permissions to the state machine role
        self._state_machine.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "kms:Decrypt",
                    "kms:DescribeKey",
                    "kms:GenerateDataKey",
                    "kms:Encrypt",
                ],
                resources=[
                    "*"
                ],  # Use a wildcard for now since we don't have the exact ARN
            )
        )

        # Add S3 permissions to the state machine role
        self._state_machine.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "s3:GetObject",
                    "s3:PutObject",
                    "s3:ListBucket",
                ],
                resources=[
                    "arn:aws:s3:::*/*",  # Access to all objects in all buckets
                    "arn:aws:s3:::*",  # Access to all buckets
                ],
            )
        )

    def _create_bulk_download_api_endpoints(self, props: AssetsProps):
        """Create API Gateway endpoints for bulk download operations."""
        # Create download resource under assets
        download_resource = self._assets_resource.add_resource("download")
        bulk_resource = download_resource.add_resource("bulk")
        job_resource = bulk_resource.add_resource("{jobId}")

        # POST /assets/download/bulk - Start a new bulk download job
        bulk_resource.add_method(
            "POST",
            api_gateway.LambdaIntegration(self._kickoff_lambda.function),
            authorization_type=api_gateway.AuthorizationType.COGNITO,
            authorizer=props.cognito_authorizer,
        )

        # GET /assets/download/bulk/{jobId} - Get job status
        job_resource.add_method(
            "GET",
            api_gateway.LambdaIntegration(self._status_lambda.function),
            authorization_type=api_gateway.AuthorizationType.COGNITO,
            authorizer=props.cognito_authorizer,
        )

        # PUT /assets/download/bulk/{jobId} - Mark job as downloaded
        job_resource.add_method(
            "PUT",
            api_gateway.LambdaIntegration(self._mark_downloaded_lambda.function),
            authorization_type=api_gateway.AuthorizationType.COGNITO,
            authorizer=props.cognito_authorizer,
        )

        # DELETE /assets/download/bulk/{jobId} - Delete job and cleanup resources
        job_resource.add_method(
            "DELETE",
            api_gateway.LambdaIntegration(self._delete_bulk_download_lambda.function),
            authorization_type=api_gateway.AuthorizationType.COGNITO,
            authorizer=props.cognito_authorizer,
        )

        # GET /assets/download/bulk/user - List user's bulk download jobs
        user_resource = bulk_resource.add_resource("user")
        user_resource.add_method(
            "GET",
            api_gateway.LambdaIntegration(self._status_lambda.function),
            authorization_type=api_gateway.AuthorizationType.COGNITO,
            authorizer=props.cognito_authorizer,
        )

        # Add CORS support to bulk download API resources
        add_cors_options_method(download_resource)
        add_cors_options_method(bulk_resource)
        add_cors_options_method(job_resource)
        add_cors_options_method(user_resource)

    @property
    def bulk_download_table(self) -> dynamodb.Table:
        """Returns the user table that stores bulk download jobs."""
        return (
            self._bulk_download_table if hasattr(self, "_bulk_download_table") else None
        )

    @property
    def efs_filesystem(self) -> efs.FileSystem:
        return self._efs_filesystem if hasattr(self, "_efs_filesystem") else None

    @property
    def state_machine(self) -> sfn.StateMachine:
        return self._state_machine if hasattr(self, "_state_machine") else None
