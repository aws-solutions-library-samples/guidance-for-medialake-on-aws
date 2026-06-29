"""
Users API Stack for MediaLake.

Top-level stack that hosts the Users API (/users/*). It is split out of
UsersGroupsStack so its API Gateway Resource/Method/Permission resources land
in THIS template instead of the MediaLakeStack parent, keeping every template
under the 500-resource CloudFormation limit.

It creates NO stateful resources: the user table (and the other Users/Groups
tables) stay in UsersGroupsStack and are only referenced here by name, so
nothing is reprovisioned. The shared REST API is imported by ID and the shared
authorizer instance is reused.
"""

from dataclasses import dataclass

import aws_cdk as cdk
from aws_cdk import aws_apigateway as apigateway
from aws_cdk import aws_cognito as cognito
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_secretsmanager as secretsmanager
from constructs import Construct

from medialake_constructs.api_gateway.api_gateway_users import UsersApi, UsersApiProps


@dataclass
class UsersApiStackProps:
    """Configuration for the (top-level) Users API Stack."""

    cognito_user_pool: cognito.UserPool
    authorizer: apigateway.IAuthorizer
    rest_api_id: str
    root_resource_id: str
    x_origin_verify_secret_arn: str
    # User table referenced by name (it stays in UsersGroupsStack). The ARN is
    # derived from this stack's account/region by from_table_attributes.
    user_table_name: str
    # Collections table referenced by name so the users Lambda can migrate a
    # deleted user's collections to the deleting administrator.
    collections_table_name: str


class UsersApiStack(cdk.Stack):
    """Top-level stack for the Users API."""

    def __init__(
        self, scope: Construct, id: str, props: UsersApiStackProps, **kwargs
    ) -> None:
        super().__init__(scope, id, **kwargs)

        # Import the shared REST API by ID/root so methods/resources created
        # below are emitted into this stack's own template.
        api = apigateway.RestApi.from_rest_api_attributes(
            self,
            "UsersImportedApi",
            rest_api_id=props.rest_api_id,
            root_resource_id=props.root_resource_id,
        )

        x_origin_verify_secret = secretsmanager.Secret.from_secret_complete_arn(
            self, "XOriginVerifySecret", props.x_origin_verify_secret_arn
        )

        # User table referenced by name/ARN. grant_index_permissions=True so the
        # users Lambda can query the user table's GSIs. Tables use a
        # DynamoDB-owned key, so no KMS grant is needed.
        user_table = dynamodb.TableV2.from_table_attributes(
            self,
            "UserTableRef",
            table_name=props.user_table_name,
            grant_index_permissions=True,
        )

        # Create Users API construct (profile, settings, favorites, CRUD).
        self._users_api = UsersApi(
            self,
            "UsersApiGateway",
            props=UsersApiProps(
                api_resource=api,
                authorizer=props.authorizer,
                cognito_user_pool=props.cognito_user_pool,
                x_origin_verify_secret=x_origin_verify_secret,
                user_table=user_table,
            ),
        )

        # Re-create the cross-feature wiring that previously lived in
        # MediaLakeStack: the users Lambda migrates a deleted user's collections
        # to the deleting administrator. Referenced by name/ARN to avoid a
        # cross-stack export to the collections data tier.
        collections_table = dynamodb.TableV2.from_table_attributes(
            self,
            "CollectionsTableRef",
            table_name=props.collections_table_name,
            grant_index_permissions=True,
        )
        self._users_api.users_lambda.function.add_environment(
            "COLLECTIONS_TABLE_NAME", props.collections_table_name
        )
        collections_table.grant_read_write_data(self._users_api.users_lambda.function)

    @property
    def users_api(self):
        """Return the Users API construct."""
        return self._users_api
