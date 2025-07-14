"""
Utility functions for creating consistent API Gateway authorizers.
"""

from typing import Optional

import aws_cdk as cdk
from aws_cdk import Duration, Fn
from aws_cdk import aws_apigateway as apigateway
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from constructs import Construct


def create_shared_custom_authorizer(
    scope: Construct,
    authorizer_id: str,
    cache_ttl_minutes: int = 5,
    api_gateway_id: Optional[str] = None,
) -> apigateway.RequestAuthorizer:
    """
    Create a RequestAuthorizer using the shared custom authorizer Lambda.

    Args:
        scope: The construct scope
        authorizer_id: Unique ID for this authorizer instance
        cache_ttl_minutes: TTL for authorization cache in minutes
        api_gateway_id: Optional specific API Gateway ID for more granular permissions

    Returns:
        apigateway.RequestAuthorizer: Configured authorizer
    """
    # Import the shared authorizer Lambda ARN
    authorizer_lambda_arn = Fn.import_value("MediaLake-SharedAuthorizerLambdaArn")

    # Import the Lambda function by ARN
    authorizer_lambda = lambda_.Function.from_function_arn(
        scope, f"{authorizer_id}ImportedLambda", authorizer_lambda_arn
    )

    # If a specific API Gateway ID is provided, add more granular permissions
    if api_gateway_id:
        try:
            authorizer_lambda.add_permission(
                f"{authorizer_id}InvokePermission",
                principal=iam.ServicePrincipal("apigateway.amazonaws.com"),
                action="lambda:InvokeFunction",
                source_arn=f"arn:aws:execute-api:{cdk.Aws.REGION}:{cdk.Aws.ACCOUNT_ID}:{api_gateway_id}/*/*",
            )
        except Exception:
            # Permission may already exist, continue
            pass

    # Create the RequestAuthorizer
    return apigateway.RequestAuthorizer(
        scope,
        authorizer_id,
        handler=authorizer_lambda,
        identity_sources=["method.request.header.Authorization"],
        results_cache_ttl=Duration.minutes(cache_ttl_minutes),
    )


def add_api_gateway_permission_to_shared_authorizer(
    scope: Construct, permission_id: str, api_gateway_id: str
) -> None:
    """
    Add specific API Gateway permission to the shared authorizer Lambda.

    Args:
        scope: The construct scope
        permission_id: Unique ID for this permission
        api_gateway_id: The API Gateway ID that needs permission
    """
    # Import the shared authorizer Lambda ARN
    authorizer_lambda_arn = Fn.import_value("MediaLake-SharedAuthorizerLambdaArn")

    # Import the Lambda function by ARN
    authorizer_lambda = lambda_.Function.from_function_arn(
        scope, f"{permission_id}ImportedLambda", authorizer_lambda_arn
    )

    # Add permission for this specific API Gateway
    try:
        authorizer_lambda.add_permission(
            permission_id,
            principal=iam.ServicePrincipal("apigateway.amazonaws.com"),
            action="lambda:InvokeFunction",
            source_arn=f"arn:aws:execute-api:{cdk.Aws.REGION}:{cdk.Aws.ACCOUNT_ID}:{api_gateway_id}/*/*",
        )
    except Exception:
        # Permission may already exist, continue
        pass


def ensure_shared_authorizer_permissions(
    scope: Construct, construct_id: str, api_gateway: apigateway.RestApi
) -> None:
    """
    Ensure the shared authorizer Lambda has permissions for the given API Gateway.

    This function adds the necessary resource-based policy to allow the API Gateway
    to invoke the shared authorizer Lambda function.

    Args:
        scope: The construct scope
        construct_id: Unique ID for this permission setup
        api_gateway: The API Gateway that needs permission to invoke the authorizer
    """
    # Import the shared authorizer Lambda ARN
    authorizer_lambda_arn = Fn.import_value("MediaLake-SharedAuthorizerLambdaArn")

    # Import the Lambda function by ARN
    authorizer_lambda = lambda_.Function.from_function_arn(
        scope, f"{construct_id}AuthorizerLambda", authorizer_lambda_arn
    )

    # Add permission for this specific API Gateway
    authorizer_lambda.add_permission(
        f"{construct_id}AuthorizerPermission",
        principal=iam.ServicePrincipal("apigateway.amazonaws.com"),
        action="lambda:InvokeFunction",
        source_arn=f"{api_gateway.arn_for_execute_api()}/*/*",
    )
