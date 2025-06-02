"""
API Gateway Assets module for MediaLake.

This module defines the AssetsConstruct class which sets up API Gateway endpoints
for managing assets, including:
- GET /assets/{id} - Get asset details
- DELETE /assets/{id} - Delete an asset
- GET /assets/{id}/relatedversions - Get related versions of an asset
"""

from dataclasses import dataclass
from aws_cdk import (
    aws_apigateway as api_gateway,
    aws_secretsmanager as secretsmanager,
    aws_dynamodb as dynamodb,
    Duration,
    aws_iam as iam,
    aws_ec2 as ec2,
    aws_s3 as s3,
    aws_efs as efs,
    aws_lambda as lambda_,
    aws_stepfunctions as sfn,
    aws_stepfunctions_tasks as tasks,
    RemovalPolicy,
    Fn,
    Stack,
)
from constructs import Construct
from medialake_constructs.shared_constructs.lambda_base import (
    Lambda,
    LambdaConfig,
)
from medialake_constructs.shared_constructs.dynamodb import DynamoDB, DynamoDBProps
from config import config
from medialake_constructs.shared_constructs.lambda_layers import SearchLayer
from medialake_constructs.api_gateway.api_gateway_utils import add_cors_options_method
from config import config
from typing import Optional

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
    vpc: Optional[ec2.IVpc] = None
    security_group: Optional[ec2.SecurityGroup] = None
    media_assets_bucket: Optional[s3.Bucket] = None
    
    # Bulk download parameters
    small_file_threshold_mb: int = 1024  # Max size for a file to be considered "small"
    chunk_size_mb: int = 100  # Size of each chunk for large file processing
    max_small_file_concurrency: int = 1000  # Max Lambdas for processing small files
    max_large_chunk_concurrency: int = 100  # Max Lambdas processing large file chunks
    merge_batch_size: int = 100  # Number of zip files merged at once in intermediate stage


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

        region = Stack.of(self).region
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
                layers=[search_layer.layer],
                environment_variables={
                    "X_ORIGIN_VERIFY_SECRET_ARN": props.x_origin_verify_secret.secret_arn,
                    "MEDIALAKE_ASSET_TABLE": props.asset_table.table_name,
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
        presigned_url_resource = self._assets_resource.add_resource("generate-presigned-url")
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
                name=f"{config.resource_prefix}_rename_asset_{config.environment}",
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
                name=f"{config.resource_prefix}_transcript_asset_{config.environment}",
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
        - DynamoDB table for tracking bulk download jobs
        - EFS filesystem for temporary storage
        - Lambda functions for processing downloads
        - Step Functions state machine for orchestration
        - API Gateway endpoints for client interaction
        """
        # Create DynamoDB table for bulk download jobs
        bulk_download_table = DynamoDB(
            self,
            "AssetsBulkDownloadJobsTable",
            props=DynamoDBProps(
                name=f"{config.resource_prefix}-assets-bulk-download-jobs-{config.environment}",
                partition_key_name="jobId",
                partition_key_type=dynamodb.AttributeType.STRING,
                point_in_time_recovery=True,
                ttl_attribute="expiresAt",
                removal_policy=RemovalPolicy.DESTROY,
            ),
        )
        self._bulk_download_table = bulk_download_table.table
        
        # Add GSI for querying by userId
        self._bulk_download_table.add_global_secondary_index(
            index_name="UserIdIndex",
            partition_key=dynamodb.Attribute(
                name="userId", type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="createdAt", type=dynamodb.AttributeType.STRING
            ),
            projection_type=dynamodb.ProjectionType.ALL,
        )
        
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
        self._create_bulk_download_step_functions_workflow(props.asset_table.table_name)
        
        # Create API Gateway endpoints
        self._create_bulk_download_api_endpoints(props)
    
    def _create_bulk_download_lambda_functions(self, props: AssetsProps):
        """Create Lambda functions for bulk download processing."""
        # Common environment variables for all Lambda functions
        common_env_vars = {
            "BULK_DOWNLOAD_TABLE": self._bulk_download_table.table_name,
            "MEDIA_ASSETS_BUCKET": props.media_assets_bucket.bucket_name,
            "EFS_MOUNT_PATH": "/mnt/bulk-downloads",
        }
        
        # Kickoff Lambda
        self._kickoff_lambda = Lambda(
            self,
            "AssetsBulkDownloadKickoffLambda",
            config=LambdaConfig(
                name=f"{config.resource_prefix}_assets_bulk_download_kickoff_{config.environment}",
                entry="lambdas/api/assets/download/bulk/kickoff",
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
                name=f"{config.resource_prefix}_assets_bulk_download_assess_scale_{config.environment}",
                entry="lambdas/api/assets/download/bulk/assess_scale",
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
        
        # Create a custom Lambda function with EFS filesystem
        self._handle_small_lambda = Lambda(
            self,
            "AssetsBulkDownloadHandleSmallLambda",
            config=LambdaConfig(
                name=f"{config.resource_prefix}_assets_bulk_download_handle_small_{config.environment}",
                entry="lambdas/api/assets/download/bulk/handle_small",
                environment_variables={
                    **common_env_vars,
                    "ASSET_TABLE": props.asset_table.table_name,
                    "RESOURCE_PREFIX": config.resource_prefix,
                    "ENVIRONMENT": config.environment,
                    "METRICS_NAMESPACE": config.resource_prefix,
                },
                vpc=props.vpc,
                security_groups=[props.security_group],
                timeout_minutes=15,
                memory_size=1024,
                filesystem_access_point=self._efs_access_point,
                filesystem_mount_path="/mnt/bulk-downloads",
            ),
        )
        
        # Handle Large Files Lambda
        self._handle_large_lambda = Lambda(
            self,
            "AssetsBulkDownloadHandleLargeLambda",
            config=LambdaConfig(
                name=f"{config.resource_prefix}_assets_bulk_download_handle_large_{config.environment}",
                entry="lambdas/api/assets/download/bulk/handle_large",
                environment_variables={
                    **common_env_vars,
                    "ASSET_TABLE": props.asset_table.table_name,
                },
                vpc=props.vpc,
                security_groups=[props.security_group],
                timeout_minutes=15,
                memory_size=1024,
                filesystem_access_point=self._efs_access_point,
                filesystem_mount_path="/mnt/bulk-downloads",
            ),
        )
        
        # Create a custom Lambda function with EFS filesystem
        self._merge_zips_lambda = Lambda(
            self,
            "AssetsBulkDownloadMergeZipsLambda",
            config=LambdaConfig(
                name=f"{config.resource_prefix}_assets_bulk_download_merge_zips_{config.environment}",
                entry="lambdas/api/assets/download/bulk/merge_zips",
                environment_variables={
                    **common_env_vars,
                    "RESOURCE_PREFIX": config.resource_prefix,
                    "ENVIRONMENT": config.environment,
                    "METRICS_NAMESPACE": config.resource_prefix,
                },
                vpc=props.vpc,
                security_groups=[props.security_group],
                timeout_minutes=15,
                memory_size=1024,
                filesystem_access_point=self._efs_access_point,
                filesystem_mount_path="/mnt/bulk-downloads",
            ),
        )
        
        # Status Lambda
        self._status_lambda = Lambda(
            self,
            "AssetsBulkDownloadStatusLambda",
            config=LambdaConfig(
                name=f"{config.resource_prefix}_assets_bulk_download_status_{config.environment}",
                entry="lambdas/api/assets/download/bulk/status",
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
                name=f"{config.resource_prefix}_assets_bulk_download_mark_downloaded_{config.environment}",
                entry="lambdas/api/assets/download/bulk/mark_downloaded",
                environment_variables={
                    **common_env_vars,
                },
                timeout_minutes=1,
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
            self._handle_small_lambda,
            self._handle_large_lambda,
            self._merge_zips_lambda,
            self._status_lambda,
            self._mark_downloaded_lambda,
        ]:
            lambda_function.function.add_to_role_policy(
                iam.PolicyStatement(
                    actions=[
                        "dynamodb:GetItem",
                        "dynamodb:PutItem",
                        "dynamodb:UpdateItem",
                        "dynamodb:Query",
                    ],
                    resources=[self._bulk_download_table.table_arn],
                )
            )
        
        # Asset table permissions for assess scale and handler lambdas
        for lambda_function in [
            self._assess_scale_lambda,
            self._handle_small_lambda,
            self._handle_large_lambda,
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
            self._handle_small_lambda,
            self._handle_large_lambda,
            self._merge_zips_lambda,
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
            self._handle_small_lambda,
            self._handle_large_lambda,
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
            self._handle_small_lambda,
            self._handle_large_lambda,
            self._merge_zips_lambda,
        ]:
            lambda_function.function.add_to_role_policy(
                iam.PolicyStatement(
                    actions=[
                        "s3:GetObject",
                        "s3:PutObject",
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
            self._handle_small_lambda,
            self._handle_large_lambda,
            self._merge_zips_lambda,
        ]:
            lambda_function.function.add_to_role_policy(
                iam.PolicyStatement(
                    actions=[
                        "kms:GenerateDataKey",
                        "kms:Decrypt",
                        "kms:Encrypt",
                        "kms:ReEncrypt*",
                        "kms:DescribeKey"
                    ],
                    resources=["*"],
                )
            )
        
        # Step Functions permissions will be added after Step Function creation
    
    def _create_bulk_download_step_functions_workflow(self, asset_table_name=None):
        """Create Step Functions state machine for orchestrating the bulk download process."""
        # Define task states
        assess_scale_task = tasks.LambdaInvoke(
            self,
            "AssetsAssessScaleTask",
            lambda_function=self._assess_scale_lambda.function,
            output_path="$.Payload",
        )
        
        # Define Map state for small files with concurrency control
        small_files_map = sfn.Map(
            self,
            "ProcessSmallFilesMap",
            max_concurrency=self.node.try_get_context("max_small_file_concurrency") or 1000,
            items_path="$.smallFiles",
            result_path="$.smallZipFiles",
        ).iterator(
            tasks.LambdaInvoke(
                self,
                "ProcessSmallFileTask",
                lambda_function=self._handle_small_lambda.function,
                output_path="$.Payload",
            )
        )
        
        # Define Map state for large file chunks with concurrency control
        large_files_map = sfn.Map(
            self,
            "ProcessLargeFilesMap",
            max_concurrency=self.node.try_get_context("max_large_chunk_concurrency") or 100,
            items_path="$.largeFiles",
            result_path="$.largeZipFiles",
        ).iterator(
            tasks.LambdaInvoke(
                self,
                "ProcessLargeFileTask",
                lambda_function=self._handle_large_lambda.function,
                output_path="$.Payload",
            )
        )
        
        merge_zips_task = tasks.LambdaInvoke(
            self,
            "AssetsMergeZipsTask",
            lambda_function=self._merge_zips_lambda.function,
            output_path="$.Payload",
        )
        
        # Create a new Lambda for handling single file downloads
        self._single_file_lambda = Lambda(
            self,
            "AssetsBulkDownloadSingleFileLambda",
            config=LambdaConfig(
                name=f"{config.resource_prefix}_assets_bulk_download_single_file_{config.environment}",
                entry="lambdas/api/assets/download/bulk/single_file",
                environment_variables={
                    "BULK_DOWNLOAD_TABLE": self._bulk_download_table.table_name,
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
                resources=["*"],  # Use a wildcard for now since we don't have the exact ARN
            )
        )
        
        self._single_file_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=["dynamodb:GetItem"],
                resources=["*"],  # Use a wildcard for now since we don't have the exact ARN
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
        
        # Define choice state for job size decision
        job_size_choice = sfn.Choice(self, "AssetsJobSizeDecision")
        
        # Define success and failure states
        success_state = sfn.Succeed(self, "AssetsDownloadJobSucceeded")
        fail_state = sfn.Fail(self, "AssetsDownloadJobFailed", cause="Job processing failed")
        
        # Define a pass state to combine results
        combine_results = sfn.Pass(
            self,
            "CombineResults",
            parameters={
                "jobId.$": "$.jobId",
                "userId.$": "$.userId",
                "smallZipFiles.$": "$.smallZipFiles",
                "largeZipFiles.$": "$.largeZipFiles",
                "options.$": "$.options"
            }
        )
        
        # For SMALL and LARGE job types, we need to process both small and large files
        # Create a parallel state to process both small and large files
        parallel_processing = sfn.Parallel(
            self,
            "ProcessFilesInParallel"
        ).branch(
            # Process small files if there are any
            sfn.Choice(self, "CheckSmallFiles")
            .when(
                sfn.Condition.is_present("$.smallFiles[0]"),
                small_files_map
            )
            .otherwise(
                sfn.Pass(self, "NoSmallFiles", result_path="$.smallZipFiles", result=sfn.Result.from_array([]))
            )
        ).branch(
            # Process large files if there are any
            sfn.Choice(self, "CheckLargeFiles")
            .when(
                sfn.Condition.is_present("$.largeFiles[0]"),
                large_files_map
            )
            .otherwise(
                sfn.Pass(self, "NoLargeFiles", result_path="$.largeZipFiles", result=sfn.Result.from_array([]))
            )
        ).next(combine_results).next(merge_zips_task)
        
        # Build the main workflow
        workflow = assess_scale_task.next(
            job_size_choice
            .when(sfn.Condition.string_equals("$.jobType", "SINGLE_FILE"), single_file_task.next(success_state))
            .otherwise(parallel_processing)
        )
        
        # Note: single_file_task already connected to success_state in the workflow definition
        
        # Complete the workflow
        merge_zips_task.next(success_state)
        
        # Create the state machine using the non-deprecated API
        self._state_machine = sfn.StateMachine(
            self,
            "AssetsBulkDownloadStateMachine",
            definition_body=sfn.DefinitionBody.from_chainable(workflow),
            timeout=Duration.hours(2),
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
            authorizer=props.cognito_authorizer
        )
        
        # GET /assets/download/bulk/{jobId} - Get job status
        job_resource.add_method(
            "GET",
            api_gateway.LambdaIntegration(self._status_lambda.function),
            authorization_type=api_gateway.AuthorizationType.COGNITO,
            authorizer=props.cognito_authorizer
        )
        
        # PUT /assets/download/bulk/{jobId} - Mark job as downloaded
        job_resource.add_method(
            "PUT",
            api_gateway.LambdaIntegration(self._mark_downloaded_lambda.function),
            authorization_type=api_gateway.AuthorizationType.COGNITO,
            authorizer=props.cognito_authorizer
        )
        
        # GET /assets/download/bulk/user - List user's bulk download jobs
        user_resource = bulk_resource.add_resource("user")
        user_resource.add_method(
            "GET",
            api_gateway.LambdaIntegration(self._status_lambda.function),
            authorization_type=api_gateway.AuthorizationType.COGNITO,
            authorizer=props.cognito_authorizer
        )
        
        # Add CORS support to bulk download API resources
        add_cors_options_method(download_resource)
        add_cors_options_method(bulk_resource)
        add_cors_options_method(job_resource)
        add_cors_options_method(user_resource)
    
    @property
    def bulk_download_table(self) -> dynamodb.TableV2:
        return self._bulk_download_table if hasattr(self, '_bulk_download_table') else None
    
    @property
    def efs_filesystem(self) -> efs.FileSystem:
        return self._efs_filesystem if hasattr(self, '_efs_filesystem') else None
    
    @property
    def state_machine(self) -> sfn.StateMachine:
        return self._state_machine if hasattr(self, '_state_machine') else None