from aws_cdk import (
    Stack,
    aws_apigateway as apigateway,
    aws_cognito as cognito,
    aws_secretsmanager as secretsmanager,
    Fn
)
from constructs import Construct
from dataclasses import dataclass

from medialake_constructs.api_gateway.api_gateway_users import (
    UsersApi,
    UsersApiProps,
)
from medialake_constructs.api_gateway.api_gateway_roles import (
    RolesApi,
    RolesApiProps,
)
from medialake_constructs.api_gateway.api_gateway_utils import add_cors_options_method


@dataclass
class UsersGroupsRolesStackProps:
    """Configuration for Users, Groups, and Roles Stack."""
    cognito_user_pool: cognito.UserPool
    cognito_app_client: str
    x_origin_verify_secret: secretsmanager.Secret


class UsersGroupsRolesStack(Stack):
    """
    Stack for Users, Groups, and Roles API and management.
    This stack creates the users, groups, and roles API endpoints and all related resources.
    """

    def __init__(
        self, scope: Construct, id: str, props: UsersGroupsRolesStackProps, **kwargs
    ):
        super().__init__(scope, id, **kwargs)

        # Import the API Gateway Core components
        api_id = Fn.import_value("MediaLakeApiGatewayCore-ApiGatewayId")
        root_resource_id = Fn.import_value("MediaLakeApiGatewayCore-RootResourceId")
        
        api = apigateway.RestApi.from_rest_api_attributes(self, "UsersGroupsRolesImportedApi",
            rest_api_id=api_id,
            root_resource_id=root_resource_id
        )
        
        self._api_authorizer = apigateway.CognitoUserPoolsAuthorizer(
            self, 
            "UsersGroupsRolesApiAuthorizer",
            identity_source="method.request.header.Authorization",
            cognito_user_pools=[props.cognito_user_pool],
        )

        # Create Users API construct
        self._users_api = UsersApi(
            self,
            "UsersApiGateway",
            props=UsersApiProps(
                api_resource=api.root,
                cognito_authorizer=self._api_authorizer,
                cognito_user_pool=props.cognito_user_pool,
                x_origin_verify_secret=props.x_origin_verify_secret,
            ),
        )

        # Create the Roles API construct
        self._roles_api = RolesApi(
            self,
            "RolesApi",
            props=RolesApiProps(
                api_resource=api.root,
                cognito_authorizer=self._api_authorizer,
                cognito_user_pool=props.cognito_user_pool,
                x_origin_verify_secret=props.x_origin_verify_secret,
            ),
        )
    
    @property
    def users_api(self):
        """Return the users API from the construct"""
        return self._users_api
    
    @property
    def roles_table(self):
        """Return the roles table from the construct"""
        return self._roles_api._roles_table.table
    
    @property
    def roles_metrics_table(self):
        """Return the roles metrics table from the construct"""
        return self._roles_api._roles_metrics_table 