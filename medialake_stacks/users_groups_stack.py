from dataclasses import dataclass

import aws_cdk as cdk
from aws_cdk import Fn
from aws_cdk import aws_apigateway as apigateway
from aws_cdk import aws_cognito as cognito
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_secretsmanager as secretsmanager
from constructs import Construct

from config import config
from medialake_constructs.api_gateway.api_gateway_upsf import UPSFApi, UPSFApiProps
from medialake_constructs.api_gateway.api_gateway_users import UsersApi, UsersApiProps
from medialake_constructs.shared_constructs.dynamodb import DynamoDB, DynamoDBProps


@dataclass
class UsersGroupsStackProps:
    """Configuration for Users, Groups, and Roles Stack."""

    cognito_user_pool: cognito.UserPool
    cognito_app_client: str
    x_origin_verify_secret: secretsmanager.Secret
    auth_table_name: str
    avp_policy_store_id: str


class UsersGroupsStack(cdk.NestedStack):
    """
    Stack for Users, Groups, and Roles API and management.
    This stack creates the users, groups, and roles API endpoints and all related resources.
    """

    def __init__(
        self, scope: Construct, id: str, props: UsersGroupsStackProps, **kwargs
    ):
        super().__init__(scope, id, **kwargs)

        # Import the API Gateway Core components
        api_id = Fn.import_value("MediaLakeApiGatewayCore-ApiGatewayId")
        root_resource_id = Fn.import_value("MediaLakeApiGatewayCore-RootResourceId")

        api = apigateway.RestApi.from_rest_api_attributes(
            self,
            "UsersGroupsRolesImportedApi",
            rest_api_id=api_id,
            root_resource_id=root_resource_id,
        )

        # Create Cognito User Pool authorizer for standard authentication
        self._cognito_user_pool_authorizer = apigateway.CognitoUserPoolsAuthorizer(
            self,
            "UsersGroupsRolesCognitoAuthorizer",
            cognito_user_pools=[props.cognito_user_pool],
        )

        # 1. User Table
        user_table_props = DynamoDBProps(
            name=f"{config.resource_prefix}-user-{config.environment}",
            partition_key_name="userId",
            partition_key_type=dynamodb.AttributeType.STRING,
            sort_key_name="itemKey",
            sort_key_type=dynamodb.AttributeType.STRING,
            point_in_time_recovery=True,
            billing_mode=dynamodb.Billing.on_demand(),
            global_secondary_indexes=[
                # GSI1 (FavoritesByType)
                dynamodb.GlobalSecondaryIndexPropsV2(
                    index_name="GSI1",
                    partition_key=dynamodb.Attribute(
                        name="userId", type=dynamodb.AttributeType.STRING
                    ),
                    sort_key=dynamodb.Attribute(
                        name="gsi1Sk", type=dynamodb.AttributeType.STRING
                    ),
                    projection_type=dynamodb.ProjectionType.ALL,
                ),
                # GSI2 (FavoritesAcrossUsers)
                dynamodb.GlobalSecondaryIndexPropsV2(
                    index_name="GSI2",
                    partition_key=dynamodb.Attribute(
                        name="gsi2Pk", type=dynamodb.AttributeType.STRING
                    ),
                    sort_key=dynamodb.Attribute(
                        name="gsi2Sk", type=dynamodb.AttributeType.STRING
                    ),
                    projection_type=dynamodb.ProjectionType.ALL,
                ),
                # GSI3 (BulkDownloadJobLookup)
                dynamodb.GlobalSecondaryIndexPropsV2(
                    index_name="GSI3",
                    partition_key=dynamodb.Attribute(
                        name="gsi3Pk", type=dynamodb.AttributeType.STRING
                    ),
                    sort_key=dynamodb.Attribute(
                        name="gsi3Sk", type=dynamodb.AttributeType.STRING
                    ),
                    projection_type=dynamodb.ProjectionType.ALL,
                ),
            ],
        )
        self._user_table = DynamoDB(self, "UserTable", user_table_props)

        # 2. Sharing Table
        sharing_table_props = DynamoDBProps(
            name=f"{config.resource_prefix}-collections-{config.environment}",
            partition_key_name="pk",
            partition_key_type=dynamodb.AttributeType.STRING,
            sort_key_name="sk",
            sort_key_type=dynamodb.AttributeType.STRING,
            point_in_time_recovery=True,
            billing_mode=dynamodb.Billing.on_demand(),
            ttl_attribute="expiresAt",
            global_secondary_indexes=[
                # GSI1 (ResourceTypeGSI)
                dynamodb.GlobalSecondaryIndexPropsV2(
                    index_name="GSI1",
                    partition_key=dynamodb.Attribute(
                        name="resourceType", type=dynamodb.AttributeType.STRING
                    ),
                    sort_key=dynamodb.Attribute(
                        name="pk", type=dynamodb.AttributeType.STRING
                    ),
                    projection_type=dynamodb.ProjectionType.ALL,
                ),
                # GSI2 (PrincipalTypeGSI)
                dynamodb.GlobalSecondaryIndexPropsV2(
                    index_name="GSI2",
                    partition_key=dynamodb.Attribute(
                        name="principalType", type=dynamodb.AttributeType.STRING
                    ),
                    sort_key=dynamodb.Attribute(
                        name="pk", type=dynamodb.AttributeType.STRING
                    ),
                    projection_type=dynamodb.ProjectionType.ALL,
                ),
                # GSI3 (CreatedByGSI)
                dynamodb.GlobalSecondaryIndexPropsV2(
                    index_name="GSI3",
                    partition_key=dynamodb.Attribute(
                        name="createdBy", type=dynamodb.AttributeType.STRING
                    ),
                    sort_key=dynamodb.Attribute(
                        name="createdAt", type=dynamodb.AttributeType.STRING
                    ),
                    projection_type=dynamodb.ProjectionType.ALL,
                ),
            ],
        )
        self._sharing_table = DynamoDB(self, "SharingTable", sharing_table_props)

        # 3. Permissions Table
        permissions_table_props = DynamoDBProps(
            name=f"{config.resource_prefix}-permissions-{config.environment}",
            partition_key_name="pk",
            partition_key_type=dynamodb.AttributeType.STRING,
            sort_key_name="sk",
            sort_key_type=dynamodb.AttributeType.STRING,
            point_in_time_recovery=True,
            billing_mode=dynamodb.Billing.on_demand(),
        )
        self._permissions_table = DynamoDB(
            self, "PermissionsTable", permissions_table_props
        )

        # 4. Settings Table
        settings_table_props = DynamoDBProps(
            name=f"{config.resource_prefix}-settings-{config.environment}",
            partition_key_name="pk",
            partition_key_type=dynamodb.AttributeType.STRING,
            sort_key_name="sk",
            sort_key_type=dynamodb.AttributeType.STRING,
            point_in_time_recovery=True,
            billing_mode=dynamodb.Billing.on_demand(),
        )
        self._settings_table = DynamoDB(self, "SettingsTable", settings_table_props)

        # Create Users API construct
        self._users_api = UsersApi(
            self,
            "UsersApiGateway",
            props=UsersApiProps(
                api_resource=api.root,
                cognito_authorizer=self._cognito_user_pool_authorizer,
                cognito_user_pool=props.cognito_user_pool,
                x_origin_verify_secret=props.x_origin_verify_secret,
            ),
        )

        # Create the UPSF API construct
        self._upsf_api = UPSFApi(
            self,
            "UPSFApi",
            props=UPSFApiProps(
                api_resource=api.root,
                cognito_authorizer=self._cognito_user_pool_authorizer,
                cognito_user_pool=props.cognito_user_pool,
                x_origin_verify_secret=props.x_origin_verify_secret,
                user_table=self._user_table.table,
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

    # @property
    # def roles_metrics_table(self):
    #     """Return the roles metrics table from the construct"""
    #     return self._roles_api._roles_metrics_table

    @property
    def user_table(self):
        """Return the user table"""
        return self._user_table.table

    @property
    def sharing_table(self):
        """Return the sharing table"""
        return self._sharing_table.table

    # @property
    def permissions_table(self):
        """Return the permissions table"""
        return self._permissions_table.table

    @property
    def settings_table(self):
        """Return the settings table"""
        return self._settings_table.table

    # @property
    # def api_authorizer(self):
    #     """Return the API authorizer"""
    #     return self._api_authorizer
