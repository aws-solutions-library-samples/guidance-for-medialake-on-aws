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
)
from aws_cdk import Fn, Stack
from constructs import Construct
from medialake_constructs.shared_constructs.lambda_base import (
    Lambda,
    LambdaConfig,
)
from medialake_constructs.shared_constructs.lambda_layers import SearchLayer
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
        assets_resource = props.api_resource.root.add_resource("assets")
        asset_resource = assets_resource.add_resource("{id}")

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

        assets_resource.add_method(
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
        presigned_url_resource = assets_resource.add_resource("generate-presigned-url")
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
