"""
API Gateway Assets module for MediaLake.

This module defines the AssetsConstruct class which sets up API Gateway endpoints
for managing assets, including:
- GET /assets/{id} - Get asset details
- DELETE /assets/{id} - Delete an asset
"""

from dataclasses import dataclass
from aws_cdk import (
    aws_apigateway as apigateway,
    aws_secretsmanager as secretsmanager,
    aws_dynamodb as dynamodb,
    Duration,
    aws_iam as iam,
)
from aws_cdk import Fn, Stack
from constructs import Construct
from medialake_constructs.shared_constructs.lambda_base import (
    Lambda,
    LambdaConfig,
)


@dataclass
class AssetsProps:
    """Configuration for Assets API endpoints."""

    asset_table: dynamodb.TableV2
    api_resource: apigateway.IResource
    cognito_authorizer: apigateway.IAuthorizer
    x_origin_verify_secret: secretsmanager.Secret


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

        # Create assets resource and add {id} parameter
        assets_resource = props.api_resource.root.add_resource("assets")
        asset_resource = assets_resource.add_resource("{id}")

        # GET /assets/{id} Lambda
        get_asset_lambda = Lambda(
            self,
            "GetAssetLambda",
            config=LambdaConfig(
                name="get_asset_lambda",
                entry="lambdas/api/assets/rp_assets_id/get_assets",
                environment_variables={
                    "X_ORIGIN_VERIFY_SECRET_ARN": props.x_origin_verify_secret.secret_arn,
                    "MEDIALAKE_ASSET_TABLE": props.asset_table.table_name,
                },
            ),
        )

        # DELETE /assets/{id} Lambda
        delete_asset_lambda = Lambda(
            self,
            "DeleteAssetLambda",
            config=LambdaConfig(
                name="delete_asset_lambda",
                entry="lambdas/api/assets/rp_assets_id/del_assets",
                environment_variables={
                    "X_ORIGIN_VERIFY_SECRET_ARN": props.x_origin_verify_secret.secret_arn,
                    "MEDIALAKE_ASSET_TABLE": props.asset_table.table_name,
                },
            ),
        )

        # Add DynamoDB permissions for GET Lambda
        get_asset_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=["dynamodb:GetItem"],
                resources=[props.asset_table.table_arn],
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
            apigateway.LambdaIntegration(
                get_asset_lambda.function,
                proxy=True,
                integration_responses=[
                    apigateway.IntegrationResponse(
                        status_code="200",
                        response_parameters={
                            "method.response.header.Access-Control-Allow-Origin": "'*'",
                        },
                    )
                ],
            ),
            authorization_type=apigateway.AuthorizationType.COGNITO,
            authorizer=props.cognito_authorizer,
            method_responses=[
                apigateway.MethodResponse(
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
            apigateway.LambdaIntegration(
                delete_asset_lambda.function,
                proxy=True,
                integration_responses=[
                    apigateway.IntegrationResponse(
                        status_code="200",
                        response_parameters={
                            "method.response.header.Access-Control-Allow-Origin": "'*'",
                        },
                    )
                ],
            ),
            authorization_type=apigateway.AuthorizationType.COGNITO,
            authorizer=props.cognito_authorizer,
            method_responses=[
                apigateway.MethodResponse(
                    status_code="200",
                    response_parameters={
                        "method.response.header.Access-Control-Allow-Origin": True,
                    },
                )
            ],
        )

        # Add OPTIONS method for CORS
        # asset_resource.add_cors_preflight(
        #     allow_origins=["*"],
        #     allow_methods=["GET", "DELETE"],
        #     allow_headers=[
        #         "Content-Type",
        #         "X-Amz-Date",
        #         "Authorization",
        #         "X-Api-Key",
        #         "X-Origin-Verify",
        #     ],
        #     max_age=Duration.days(1),
        # )
