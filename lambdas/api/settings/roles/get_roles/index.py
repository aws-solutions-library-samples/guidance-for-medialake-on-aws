import os
from typing import Dict, List

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.event_handler import APIGatewayRestResolver
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.typing import LambdaContext
from botocore.exceptions import ClientError

# Initialize PowerTools
logger = Logger(service="get_roles")
tracer = Tracer(service="get_roles")
metrics = Metrics(namespace="GetRoles", service="get_roles")
app = APIGatewayRestResolver()

# Initialize AWS clients with X-Ray tracing
session = boto3.Session()
cognito_idp = session.client("cognito-idp")


@tracer.capture_method
def get_cognito_roles(user_pool_id: str) -> List[Dict]:
    """
    Retrieve all roles associated with the Cognito User Pool.

    Args:
        user_pool_id (str): The Cognito User Pool ID

    Returns:
        List[Dict]: List of role objects containing role information
    """
    try:
        roles = []
        paginator = cognito_idp.get_paginator("list_groups")

        for page in paginator.paginate(UserPoolId=user_pool_id):
            roles.extend(page.get("Roles", []))

        metrics.add_metric(
            name="SuccessfulRolesFetch", unit=MetricUnit.Count, value=len(roles)
        )
        return roles

    except ClientError:
        logger.exception("Failed to fetch Cognito roles")
        metrics.add_metric(name="FailedRolesFetch", unit=MetricUnit.Count, value=1)
        raise


@app.get("/settings/roles")
@tracer.capture_method
def get_roles():
    """Handle GET request to fetch Cognito roles"""
    try:
        # Get User Pool ID from environment variable
        user_pool_id = os.environ["USER_POOL_ID"]

        roles = get_cognito_roles(user_pool_id)

        return {"statusCode": 200, "body": {"roles": roles}}

    except Exception:
        logger.exception("Error processing request")
        return {"statusCode": 500, "body": {"message": "Internal server error"}}


@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: Dict, context: LambdaContext) -> Dict:
    """
    Lambda handler for getting Cognito roles.

    Args:
        event (Dict): API Gateway event
        context (LambdaContext): Lambda context

    Returns:
        Dict: API Gateway response
    """
    return app.resolve(event, context)
