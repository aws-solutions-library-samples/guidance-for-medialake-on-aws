"""
Collection Types Settings Stack for MediaLake.

This stack creates the Settings API endpoints for managing all settings including:
- Collection types management (CRUD + migration)
- System settings
- API keys management
- Users listing from Cognito

Top-level stack: it imports the shared REST API by ID and references its data
tables / the portal Lambda BY NAME so that all of its API Gateway
Resource/Method/Permission resources are emitted into THIS stack's template
(not the MediaLakeStack parent), keeping every template well under the
500-resource CloudFormation limit. It creates NO stateful resources — the
system-settings / api-keys / collections tables stay in their owning stacks and
are only referenced here, so nothing is reprovisioned.
"""

from dataclasses import dataclass

import aws_cdk as cdk
from aws_cdk import aws_apigateway as apigateway
from aws_cdk import aws_cognito as cognito
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_secretsmanager as secretsmanager
from constructs import Construct

from medialake_constructs.api_gateway.api_gateway_settings import (
    SettingsApi,
    SettingsApiProps,
)


@dataclass
class CollectionTypesStackProps:
    """Configuration for the (top-level) Collection Types / Settings API Stack."""

    cognito_user_pool: cognito.UserPool
    authorizer: apigateway.IAuthorizer
    # Shared REST API imported by ID/root so this stack owns its API surface.
    rest_api_id: str
    root_resource_id: str
    x_origin_verify_secret_arn: str
    # Data tables referenced by name (they stay in their owning stacks). The
    # ARN is derived from this stack's account/region by from_table_attributes.
    collections_table_name: str
    system_settings_table_name: str
    api_keys_table_name: str
    # Portal management Lambda referenced by name for the optional
    # /settings/portals proxy route (it stays in the Portal API stack).
    portal_management_lambda_name: str


class CollectionTypesStack(cdk.Stack):
    """
    Top-level stack for Collection Types and Settings API.

    Imports the shared REST API by ID and owns its own Resource/Method handles
    so its API surface lives in this template instead of the parent.
    """

    def __init__(
        self, scope: Construct, id: str, props: CollectionTypesStackProps, **kwargs
    ):
        super().__init__(scope, id, **kwargs)

        # Import the shared REST API by ID/root so methods/resources created
        # below are emitted into this stack's own template.
        api = apigateway.RestApi.from_rest_api_attributes(
            self,
            "CollectionTypesImportedApi",
            rest_api_id=props.rest_api_id,
            root_resource_id=props.root_resource_id,
        )

        # Import the x-origin-verify secret by ARN (no cross-stack object ref).
        x_origin_verify_secret = secretsmanager.Secret.from_secret_complete_arn(
            self, "XOriginVerifySecret", props.x_origin_verify_secret_arn
        )

        # Import the data tables by name/ARN. grant_index_permissions=True so the
        # settings Lambda can query the tables' GSIs. The tables use a
        # DynamoDB-owned encryption key, so no KMS grant is required.
        collections_table = dynamodb.TableV2.from_table_attributes(
            self,
            "CollectionsTableRef",
            table_name=props.collections_table_name,
            grant_index_permissions=True,
        )
        system_settings_table = dynamodb.TableV2.from_table_attributes(
            self,
            "SystemSettingsTableRef",
            table_name=props.system_settings_table_name,
            grant_index_permissions=True,
        )
        api_keys_table = dynamodb.TableV2.from_table_attributes(
            self,
            "ApiKeysTableRef",
            table_name=props.api_keys_table_name,
            grant_index_permissions=True,
        )

        # Import the portal management Lambda by name for the optional
        # /settings/portals route. same_environment=True so add_permission works.
        portal_management_lambda = lambda_.Function.from_function_attributes(
            self,
            "PortalManagementLambdaRef",
            function_arn=(
                f"arn:aws:lambda:{self.region}:{self.account}:function:"
                f"{props.portal_management_lambda_name}"
            ),
            same_environment=True,
        )

        # Create Settings API construct
        self._settings_api = SettingsApi(
            self,
            "SettingsApiGateway",
            props=SettingsApiProps(
                api_resource=api,
                authorizer=props.authorizer,
                x_origin_verify_secret=x_origin_verify_secret,
                collections_table=collections_table,
                system_settings_table=system_settings_table,
                api_keys_table=api_keys_table,
                cognito_user_pool=props.cognito_user_pool,
                portal_settings_integration_lambda=portal_management_lambda,
            ),
        )

    @property
    def settings_api(self):
        """Return the Settings API construct."""
        return self._settings_api

    @property
    def lambda_function(self):
        """Return the Settings Lambda function."""
        return self._settings_api.lambda_function
