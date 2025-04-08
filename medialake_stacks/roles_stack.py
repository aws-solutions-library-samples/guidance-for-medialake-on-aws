from aws_cdk import (
    Stack,
    aws_apigateway as apigateway,
    aws_cognito as cognito,
    aws_secretsmanager as secretsmanager,
)
from constructs import Construct
from dataclasses import dataclass

from medialake_constructs.api_gateway.api_gateway_roles import (
    RolesApi,
    RolesApiProps,
)


@dataclass
class RolesStackProps:
    """Configuration for Roles Stack."""
    api_resource: apigateway.RestApi
    cognito_authorizer: apigateway.CognitoUserPoolsAuthorizer
    cognito_user_pool: cognito.UserPool
    x_origin_verify_secret: secretsmanager.Secret


class RolesStack(Stack):
    """
    Stack for Roles API and management.
    This stack creates the roles API endpoints and all related resources.
    """

    def __init__(
        self, scope: Construct, id: str, props: RolesStackProps, **kwargs
    ):
        super().__init__(scope, id, **kwargs)

        # Create the Roles API construct
        self._roles_api = RolesApi(
            self,
            "RolesApi",
            props=RolesApiProps(
                api_resource=props.api_resource,
                cognito_authorizer=props.cognito_authorizer,
                cognito_user_pool=props.cognito_user_pool,
                x_origin_verify_secret=props.x_origin_verify_secret,
            ),
        )
    
    @property
    def roles_table(self):
        """Return the roles table from the construct"""
        return self._roles_api._roles_table.table
    
    @property
    def roles_metrics_table(self):
        """Return the roles metrics table from the construct"""
        return self._roles_api._roles_metrics_table 