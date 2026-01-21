"""
Dashboard Stack for MediaLake.

This stack creates the Dashboard API infrastructure including:
- DynamoDB table for dashboard layouts and presets
- Lambda function for API handling
- API Gateway integration
"""

from dataclasses import dataclass

import aws_cdk as cdk
from aws_cdk import aws_apigateway as apigateway
from aws_cdk import aws_cognito as cognito
from aws_cdk import aws_secretsmanager as secretsmanager
from constructs import Construct

from medialake_constructs.api_gateway.api_gateway_dashboard import (
    DashboardApi,
    DashboardApiProps,
)


@dataclass
class DashboardStackProps:
    """Configuration for Dashboard API Stack."""

    cognito_user_pool: cognito.UserPool
    authorizer: apigateway.IAuthorizer
    api_resource: apigateway.RestApi
    x_origin_verify_secret: secretsmanager.Secret


class DashboardStack(cdk.NestedStack):
    """
    Stack for Dashboard API and management.

    This stack creates the Dashboard API endpoints and all related resources including:
    - Dashboard layout persistence
    - Layout presets management
    - Single-table DynamoDB design for optimal performance

    The stack follows MediaLake patterns and integrates with the existing
    authorization and API Gateway infrastructure.
    """

    def __init__(self, scope: Construct, id: str, props: DashboardStackProps, **kwargs):
        super().__init__(scope, id, **kwargs)

        # Create Dashboard API construct
        self._dashboard_api = DashboardApi(
            self,
            "DashboardApiGateway",
            props=DashboardApiProps(
                api_resource=props.api_resource,
                authorizer=props.authorizer,
                x_origin_verify_secret=props.x_origin_verify_secret,
            ),
        )

    @property
    def dashboard_api(self):
        """Return the Dashboard API construct."""
        return self._dashboard_api

    @property
    def dashboard_table(self):
        """Return the Dashboard DynamoDB table."""
        return self._dashboard_api.dashboard_table.table
