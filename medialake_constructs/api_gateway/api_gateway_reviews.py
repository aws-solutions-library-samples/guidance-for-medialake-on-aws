"""
API Gateway reviews module for MediaLake.

This module defines the reviewsConstruct class which sets up API Gateway endpoints
for managing reviews, including:
- GET /reviews/{id} - Get asset details
- DELETE /reviews/{id} - Delete an asset
"""

from dataclasses import dataclass

from aws_cdk import aws_apigateway as apigateway
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_secretsmanager as secretsmanager
from constructs import Construct

from medialake_constructs.api_gateway.api_gateway_utils import add_cors_options_method
from medialake_constructs.shared_constructs.lambda_base import Lambda, LambdaConfig
from medialake_constructs.shared_constructs.lambda_layers import SearchLayer


@dataclass
class ReviewsApiProps:
    """Configuration for reviews API endpoints."""

    asset_table: dynamodb.TableV2
    api_resource: apigateway.IResource
    cognito_authorizer: apigateway.IAuthorizer
    x_origin_verify_secret: secretsmanager.Secret


class ReviewsApiConstruct(Construct):
    """
    AWS CDK Construct for managing MediaLake reviews API endpoints.

    This construct creates and configures:
    - API Gateway endpoints for asset operations
    - Lambda functions for handling asset requests
    - IAM roles and permissions for secure access
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        props: reviewsProps,
    ) -> None:
        super().__init__(scope, construct_id)

        # Create reviews resource and add {id} parameter
        reviews_resource = props.api_resource.root.add_resource("reviews")
        review_id_resource = reviews_resource.add_resource("{id}")
        review_resource = reviews_resource.add_resource("review")

        search_layer = SearchLayer(self, "SearchLayer")

        # GET /reviews/{id} Lambda
        get_reviews_review_id_lambda = Lambda(
            self,
            "GetReviewsReviewID",
            config=LambdaConfig(
                name="get_asset_lambda",
                entry="lambdas/api/reviews/rp_reviews_id/get_reviews",
                layers=[search_layer.layer],
                environment_variables={
                    "X_ORIGIN_VERIFY_SECRET_ARN": props.x_origin_verify_secret.secret_arn,
                    "MEDIALAKE_ASSET_TABLE": props.asset_table.table_name,
                },
            ),
        )

        # Add GET method to /reviews/{id}
        review_id_resource.add_method(
            "GET",
            apigateway.LambdaIntegration(
                get_reviews_review_id_lambda.function,
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

        # DELETE /reviews/{id} Lambda
        del_reviews_review_id_lambda = Lambda(
            self,
            "DeleteReviewsReviewID",
            config=LambdaConfig(
                name="delete_review",
                entry="lambdas/api/reviews/rp_reviews_id/del_reviews",
                layers=[search_layer.layer],
                environment_variables={
                    "X_ORIGIN_VERIFY_SECRET_ARN": props.x_origin_verify_secret.secret_arn,
                    "MEDIALAKE_ASSET_TABLE": props.asset_table.table_name,
                },
            ),
        )

        # Add DELETE method to /reviews/{id}
        review_id_resource.add_method(
            "DELETE",
            apigateway.LambdaIntegration(
                del_reviews_review_id_lambda.function,
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

        # Add POST /reviews/{id} endpoint
        create_review_lambda = Lambda(
            self,
            "CreateReview",
            config=LambdaConfig(
                name="rename_asset_lambda",
                layers=[search_layer.layer],
                entry="lambdas/api/reviews/rp_reviews_id/rename/post_rename",
                environment_variables={
                    "X_ORIGIN_VERIFY_SECRET_ARN": props.x_origin_verify_secret.secret_arn,
                    "MEDIALAKE_ASSET_TABLE": props.asset_table.table_name,
                },
            ),
        )

        # Add POST method to /reviews/{id}/rename
        review_resource.add_method(
            "POST",
            apigateway.LambdaIntegration(
                create_review_lambda.function,
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

        # Add CORS support
        add_cors_options_method(review_id_resource)
        add_cors_options_method(review_resource)
