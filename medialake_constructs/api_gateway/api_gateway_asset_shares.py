
from dataclasses import dataclass
from constructs import Construct
from aws_cdk import aws_apigateway as api_gateway
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_iam as iam
from cdk_logger import get_logger
from medialake_constructs.api_gateway.api_gateway_utils import add_cors_options_method
from medialake_constructs.shared_constructs.lambda_base import Lambda, LambdaConfig
from medialake_constructs.shared_constructs.lambda_layers import SearchLayer

def apply_custom_authorization(
    method: api_gateway.Method, authorizer: api_gateway.IAuthorizer
) -> None:
    """
    Apply custom authorization to an API Gateway method.

    Args:
        method: The API Gateway method to apply authorization to
        authorizer: The custom authorizer to use
    """
    cfn_method = method.node.default_child
    cfn_method.authorization_type = "CUSTOM"
    cfn_method.authorizer_id = authorizer.authorizer_id

@dataclass
class AssetSharesConstructProps:
    """Configuration for Asset Shares API endpoints."""

    api: api_gateway.RestApi
    asset_table: dynamodb.TableV2
    asset_shares_table: dynamodb.TableV2
    asset_resource: api_gateway.IResource
    public_resource: api_gateway.IResource
    authorizer: api_gateway.IAuthorizer

class AssetSharesConstruct(Construct):
    """
    AWS CDK Construct for Asset Shares API endpoints.

    This construct creates and configures:
    - API Gateway endpoints for asset share operations
    - Lambda functions for handling asset requests

    """
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        props: AssetSharesConstructProps,
        **kwargs
    ):
        super().__init__(scope, construct_id, **kwargs)

        # Initialize logger for this construct
        self.logger = get_logger("AssetSharesConstruct")

        share_resource = props.asset_resource.add_resource("share")
        add_cors_options_method(share_resource)
        
        # Create search layer for Lambda functions
        search_layer = SearchLayer(self, "SearchLayer")
        
        # POST /asset_shares/{id}/share - Create a share
        create_share_lambda = Lambda(
            self,
            "CreateShareLambda",
            config=LambdaConfig(
                name="asset_share_create",
                entry="lambdas/api/assets/rp_assets_id/share/post_share",
                layers=[search_layer.layer],
                environment_variables={
                    "SHARES_TABLE_NAME": props.asset_shares_table.table_name,
                    "ASSETS_TABLE_NAME": props.asset_table.table_name,
                },
            ),
        )
        
        # Add DynamoDB permissions for create share Lambda
        create_share_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=["dynamodb:GetItem"],
                resources=[props.asset_table.table_arn],
            )
        )
        
        create_share_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=["dynamodb:PutItem"],
                resources=[props.asset_shares_table.table_arn],
            )
        )
        
        # Add POST method to /asset_shares/{id}/share
        create_share_method = share_resource.add_method(
            "POST",
            api_gateway.LambdaIntegration(
                create_share_lambda.function,
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
            method_responses=[
                api_gateway.MethodResponse(
                    status_code="200",
                    response_parameters={
                        "method.response.header.Access-Control-Allow-Origin": True,
                    },
                )
            ],
        )
        apply_custom_authorization(create_share_method, props.authorizer)
        
        # DELETE /asset_shares/{id}/share/{shareId} - Revoke a share
        delete_share_lambda = Lambda(
            self,
            "DeleteShareLambda",
            config=LambdaConfig(
                name="asset_share_delete",
                entry="lambdas/api/assets/rp_assets_id/share/del_share",
                layers=[search_layer.layer],
                environment_variables={
                    "SHARES_TABLE_NAME": props.asset_shares_table.table_name,
                },
            ),
        )
        
        # Add DynamoDB permissions for delete share Lambda
        delete_share_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=["dynamodb:GetItem", "dynamodb:UpdateItem"],
                resources=[props.asset_shares_table.table_arn],
            )
        )
        
        # Add DELETE method to /asset_shares/{id}/share/{shareToken}
        share_token_resource = share_resource.add_resource("{shareToken}")
        add_cors_options_method(share_token_resource)
        delete_share_method = share_token_resource.add_method(
            "DELETE",
            api_gateway.LambdaIntegration(
                delete_share_lambda.function,
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
            method_responses=[
                api_gateway.MethodResponse(
                    status_code="200",
                    response_parameters={
                        "method.response.header.Access-Control-Allow-Origin": True,
                    },
                )
            ],
        )
        apply_custom_authorization(delete_share_method, props.authorizer)

        # GET /api/assets/{id}/shares - Get shares
        get_shares_lambda = Lambda(
            self,
            "GetSharesLambda",
            config=LambdaConfig(
                name="asset_share_get",
                entry="lambdas/api/assets/rp_assets_id/share/get_shares",
                layers=[search_layer.layer],
                environment_variables={
                    "SHARES_TABLE_NAME": props.asset_shares_table.table_name,
                },
            ),
        )

        # Add DynamoDB permissions for get shares Lambda
        get_shares_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=["dynamodb:Query"],
                resources=[
                    props.asset_shares_table.table_arn,
                    f"{props.asset_shares_table.table_arn}/index/*",
                ],
            )
        )

        # Add GET method to /api/assets/{id}/shares
        shares_resource = props.asset_resource.add_resource("shares")
        add_cors_options_method(shares_resource)
        get_shares_method = shares_resource.add_method(
            "GET",
            api_gateway.LambdaIntegration(
                get_shares_lambda.function,
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
            method_responses=[
                api_gateway.MethodResponse(
                    status_code="200",
                    response_parameters={
                        "method.response.header.Access-Control-Allow-Origin": True,
                    },
                )
            ],
        )
        apply_custom_authorization(get_shares_method, props.authorizer)

        # GET /api/public/share/{token}
        public_share_token_lambda = Lambda(
            self,
            "PublicShareTokenLambda",
            config=LambdaConfig(
                name="public_share_token_get",
                entry="lambdas/api/public/share/rp_token/get_share",
                layers=[search_layer.layer],
                environment_variables={
                    "SHARES_TABLE_NAME": props.asset_shares_table.table_name,
                    "ASSETS_TABLE_NAME": props.asset_table.table_name,
                },
            ),
        )

        public_share_token_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "kms:Decrypt",
                    "kms:DescribeKey",
                ],
                resources=["*"],
            )
        )

        public_share_token_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "s3:GetObject",
                    "s3:GetObjectVersion",
                ],
                resources=[
                    "arn:aws:s3:::*/*"
                ],  # Access to all objects in all buckets
            )
        )

        # Add S3 bucket-level permissions for GetBucketLocation (required for region discovery)
        public_share_token_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=["s3:GetBucketLocation"],
                resources=[
                    "arn:aws:s3:::*"
                ],  # Access to all buckets for location queries
            )
        )

        # Add DynamoDB permissions for public share token Lambda
        public_share_token_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=["dynamodb:GetItem", "dynamodb:UpdateItem"],
                resources=[props.asset_shares_table.table_arn],
            )
        )

        public_share_token_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=["dynamodb:GetItem"],
                resources=[props.asset_table.table_arn],
            )
        )

        # Add GET method to /api/public/share/{token}
        public_share_token_resource = props.public_resource.add_resource("share").add_resource("{shareToken}")
        add_cors_options_method(public_share_token_resource)
        
        public_share_token_method = public_share_token_resource.add_method(
            "GET",
            api_gateway.LambdaIntegration(
                public_share_token_lambda.function,
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
            method_responses=[
                api_gateway.MethodResponse(
                    status_code="200",
                    response_parameters={
                        "method.response.header.Access-Control-Allow-Origin": True,
                    },
                )
            ],
            authorization_type=api_gateway.AuthorizationType.NONE,
        )

        public_share_generate_download_url_lambda = Lambda(
            self,
            "PublicShareGenerateDownloadUrlLambda",
            config=LambdaConfig(
                name="public_share_generate_download_url",
                entry="lambdas/api/public/share/rp_token/post_generate_download_url",
                layers=[search_layer.layer],
                environment_variables={
                    "SHARES_TABLE_NAME": props.asset_shares_table.table_name,
                    "ASSETS_TABLE_NAME": props.asset_table.table_name,
                },
            ),
        )

        public_share_generate_download_url_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "kms:Decrypt",
                    "kms:DescribeKey",
                ],
                resources=["*"],
            )
        )

        public_share_generate_download_url_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "s3:GetObject",
                    "s3:GetObjectVersion",
                ],
                resources=[
                    "arn:aws:s3:::*/*"
                ],
            )
        )

        # Add S3 bucket-level permissions for GetBucketLocation (required for region discovery)
        public_share_generate_download_url_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=["s3:GetBucketLocation"],
                resources=[
                    "arn:aws:s3:::*"
                ],
            )
        )

        public_share_generate_download_url_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=["dynamodb:GetItem", "dynamodb:UpdateItem"],
                resources=[props.asset_shares_table.table_arn],
            )
        )

        public_share_generate_download_url_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=["dynamodb:GetItem"],
                resources=[props.asset_table.table_arn],
            )
        )

        # Add GET method to /api/public/share/{token}/download-url
        public_share_generate_download_url_resource = public_share_token_resource.add_resource("generate-download-url")
        add_cors_options_method(public_share_generate_download_url_resource)

        public_share_generate_download_url_method = public_share_generate_download_url_resource.add_method(
            "POST",
            api_gateway.LambdaIntegration(
                public_share_generate_download_url_lambda.function,
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
            method_responses=[
                api_gateway.MethodResponse(
                    status_code="200",
                    response_parameters={
                        "method.response.header.Access-Control-Allow-Origin": True,
                    },
                )
            ],
            authorization_type=api_gateway.AuthorizationType.NONE,
        )

        # GET /api/public/embed/{token}
        public_embed_lambda = Lambda(
            self,
            "PublicEmbedLambda",
            config=LambdaConfig(
                name="public_embed_get",
                entry="lambdas/api/public/embed/rp_token/get_embed",
                layers=[search_layer.layer],
                environment_variables={
                    "SHARES_TABLE_NAME": props.asset_shares_table.table_name,
                    "ASSETS_TABLE_NAME": props.asset_table.table_name,
                },
            ),
        )

        public_embed_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=["dynamodb:GetItem", "dynamodb:UpdateItem"],
                resources=[props.asset_shares_table.table_arn],
            )
        )

        public_embed_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=["dynamodb:GetItem"],
                resources=[props.asset_table.table_arn],
            )
        )

        public_embed_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "kms:Decrypt",
                    "kms:DescribeKey",
                ],
                resources=["*"],
            )
        )

        public_embed_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "s3:GetObject",
                    "s3:GetObjectVersion",
                ],
                resources=[
                    "arn:aws:s3:::*/*"
                ],
            )
        )

        public_embed_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=["s3:GetBucketLocation"],
                resources=[
                    "arn:aws:s3:::*"
                ]
            )
        )

        public_embed_resource = props.public_resource.add_resource("embed").add_resource("{shareToken}")
        add_cors_options_method(public_embed_resource)

        public_embed_method = public_embed_resource.add_method(
            "GET",
            api_gateway.LambdaIntegration(
                public_embed_lambda.function,
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
            method_responses=[
                api_gateway.MethodResponse(
                    status_code="200",
                    response_parameters={
                        "method.response.header.Access-Control-Allow-Origin": True,
                    },
                )
            ],
            authorization_type=api_gateway.AuthorizationType.NONE,
        )

        self.logger.info("Asset Shares API endpoints created successfully")
