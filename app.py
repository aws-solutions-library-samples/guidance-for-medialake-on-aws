#!/usr/bin/env python3
"""Entry point for the MediaLake CDK application."""
import os
from dataclasses import dataclass

import aws_cdk as cdk
from aws_cdk import Fn
from aws_cdk import aws_apigateway as apigateway
from aws_cdk import aws_secretsmanager as secretsmanager
from constructs import Construct

from cdk_logger import CDKLogger, get_logger
from config import config
from medialake_stacks.api_gateway_core_stack import (
    ApiGatewayCoreStack,
    ApiGatewayCoreStackProps,
)
from medialake_stacks.api_gateway_deployment_stack import (
    ApiGatewayDeploymentStack,
    ApiGatewayDeploymentStackProps,
)
from medialake_stacks.api_gateway_stack import ApiGatewayStack, ApiGatewayStackProps
from medialake_stacks.asset_sync_stack import AssetSyncStack, AssetSyncStackProps
from medialake_stacks.authorization_stack import (
    AuthorizationStack,
    AuthorizationStackProps,
)
from medialake_stacks.base_infrastructure import BaseInfrastructureStack
from medialake_stacks.clean_up_stack import CleanupStack, CleanupStackProps
from medialake_stacks.cloudfront_waf_stack import CloudFrontWafStack
from medialake_stacks.cognito_stack import CognitoStack, CognitoStackProps
from medialake_stacks.cognito_update_stack import (
    CognitoUpdateStack,
    CognitoUpdateStackProps,
)
from medialake_stacks.collection_types_stack import (
    CollectionTypesStack,
    CollectionTypesStackProps,
)
from medialake_stacks.collections_stack import CollectionsStack, CollectionsStackProps
from medialake_stacks.edge_lambda_stack import EdgeLambdaStack
from medialake_stacks.groups_stack import GroupsStack, GroupsStackProps
from medialake_stacks.integrations_environment_stack import (
    IntegrationsEnvironmentStack,
    IntegrationsEnvironmentStackProps,
)
from medialake_stacks.nodes_stack import NodesStack, NodesStackProps
from medialake_stacks.pipeline_stack import PipelineStack, PipelineStackProps

# from medialake_stacks.settings_api_stack import SettingsApiStack, SettingsApiStackProps  # Deprecated - now using CollectionTypesStack
from medialake_stacks.settings_stack import SettingsStack, SettingsStackProps
from medialake_stacks.updates_api_stack import UpdatesApiStack, UpdatesApiStackProps
from medialake_stacks.user_interface_stack import (
    UserInterfaceStack,
    UserInterfaceStackProps,
)
from medialake_stacks.users_groups_stack import UsersGroupsStack, UsersGroupsStackProps

# from medialake_stacks.monitoring_stack import MonitoringStack - Development paused, commented out for now

# Initialize global logger configuration
if hasattr(config, "logging") and hasattr(config.logging, "level"):
    CDKLogger.set_level(config.logging.level)

# Create application-level logger
logger = get_logger("CDKApp")
logger.info(f"Initializing MediaLake CDK App with log level: {config.logging.level}")

app = cdk.App()

# us-east-1 environment, required for the WAF, webACL configuration has to be deployed in us-east-1
env_us_east_1 = cdk.Environment(account=app.account, region="us-east-1")

if "CDK_DEFAULT_ACCOUNT" in os.environ and "CDK_DEFAULT_REGION" in os.environ:
    env = cdk.Environment(
        account=os.environ["CDK_DEFAULT_ACCOUNT"],
        region=os.environ["CDK_DEFAULT_REGION"],
    )
else:
    env = cdk.Environment(account=app.account, region=app.region)

cloudfront_waf_stack = CloudFrontWafStack(
    app, "MediaLakeCloudFrontWAF", env=env_us_east_1
)

# Create Edge Lambda Stack in us-east-1 (required for Lambda@Edge)
# Lambda@Edge functions must be deployed in us-east-1 regardless of main stack region
edge_lambda_stack = EdgeLambdaStack(
    app, "MediaLakeEdgeLambda", env=env_us_east_1  # Must be us-east-1
)

# Create the BaseInfrastructureStack
base_infrastructure = BaseInfrastructureStack(
    app, "MediaLakeBaseInfrastructure", env=env
)

cognito_stack = CognitoStack(
    app,
    "MediaLakeCognito",
    props=CognitoStackProps(),
    env=env,
)

api_gateway_core_stack = ApiGatewayCoreStack(
    app,
    "MediaLakeApiGatewayCore",
    props=ApiGatewayCoreStackProps(
        access_log_bucket=base_infrastructure.access_log_bucket,
        cognito_user_pool=cognito_stack.user_pool,
    ),
    env=env,
)

waf_acl_ssm_param_name = "/medialake/cloudfront-waf-acl-arn"

api_gateway_core_stack.add_dependency(base_infrastructure)
api_gateway_core_stack.add_dependency(cognito_stack)

# Create the Authorization Stack (depends on Cognito, NOT on ApiGatewayCore)
authorization_stack = AuthorizationStack(
    app,
    "MediaLakeAuthorizationStack",
    props=AuthorizationStackProps(
        cognito_user_pool=cognito_stack.user_pool,
        cognito_construct=cognito_stack.cognito_construct,
        cognito_user_pool_client=cognito_stack.user_pool_client,
    ),
    env=env,
)
authorization_stack.add_dependency(cognito_stack)


# Create a separate resource collector that doesn't create circular dependencies
class ApiResourceCollector:
    """Collects API resources from various stacks without creating circular dependencies."""

    def __init__(self):
        self.resources = []

    def add_resource(self, resource):
        """Add a resource to the collection."""
        if resource is not None:
            self.resources.append(resource)
            print(
                f"Resource collector: Added resource {type(resource).__name__} (total: {len(self.resources)})"
            )
        else:
            print("Resource collector: Skipping None resource")

    def get_resources(self):
        """Get all collected resources."""
        valid_resources = [r for r in self.resources if r is not None]
        print(
            f"Resource collector: Returning {len(valid_resources)} valid resources out of {len(self.resources)} total"
        )
        return valid_resources.copy()

    def get_resource_count(self):
        """Get the count of collected resources."""
        return len(self.resources)

    # TODO: Remove debug prints once implementation is working


# Create the collector before the stacks
api_resource_collector = ApiResourceCollector()


# Create a resource importer to break circular dependencies
class ResourceImporter:

    @staticmethod
    def get_rest_api():
        """Get the REST API from CloudFormation export."""
        # We need to return the actual RestApi object, not just the ID
        # This will be handled by the individual stacks that need it
        raise NotImplementedError(
            "get_rest_api() should not be called directly. Use get_rest_api_id() instead."
        )

    @staticmethod
    def get_rest_api_id():
        """Get the REST API ID from CloudFormation export."""
        return Fn.import_value("MediaLakeApiGatewayCore-ApiGatewayId")

    @staticmethod
    def get_root_resource_id():
        """Get the root resource ID from CloudFormation export."""
        return Fn.import_value("MediaLakeApiGatewayCore-RootResourceId")

    @staticmethod
    def get_x_origin_verify_secret_arn():
        """Get the X-Origin verify secret ARN from CloudFormation export."""
        return Fn.import_value("MediaLakeApiGatewayCore-XOriginVerifySecretArn")

    @staticmethod
    def get_waf_acl_arn():
        """Get the WAF ACL ARN from CloudFormation export."""
        return Fn.import_value("MediaLakeApiGatewayCore-ApiGatwayWAFACLARN")


@dataclass
class MediaLakeStackProps:
    # api_gateway_core_stack: ApiGatewayCoreStack  # Removed to break circular dependency
    base_infrastructure: BaseInfrastructureStack
    authorization_stack: AuthorizationStack
    cognito_stack: CognitoStack
    resource_collector: ApiResourceCollector
    cloudfront_domain: str  # CloudFront distribution domain for CORS configuration
    ui_origin_host: str | None = None  # Custom domain for UI, if configured


class MediaLakeStack(cdk.Stack):
    def __init__(self, scope: Construct, id: str, props: MediaLakeStackProps, **kwargs):
        super().__init__(scope, id, **kwargs)

        # NOTE: This stack no longer depends on api_gateway_core_stack directly.
        # Instead, it imports resources from CloudFormation exports to break circular dependencies.
        # See ResourceImporter class for details.

        # Create shared RestApi and Secret objects to avoid circular dependencies
        # These will be passed to all child stacks that need them
        self.shared_rest_api = apigateway.RestApi.from_rest_api_attributes(
            self,
            "SharedRestApi",
            rest_api_id=ResourceImporter.get_rest_api_id(),
            root_resource_id=ResourceImporter.get_root_resource_id(),
        )

        self.shared_x_origin_secret = secretsmanager.Secret.from_secret_name_v2(
            self,
            "SharedXOriginSecret",
            ResourceImporter.get_x_origin_verify_secret_arn(),
        )

        nodes_stack = NodesStack(
            self,
            "MediaLakeNodes",
            props=NodesStackProps(
                iac_bucket=props.base_infrastructure.iac_assets_bucket,
            ),
        )

        asset_sync_stack = AssetSyncStack(
            self,
            "MediaLakeAssetSyncStack",
            props=AssetSyncStackProps(
                asset_table=props.base_infrastructure.asset_table,
                pipelines_event_bus=props.base_infrastructure.pipelines_event_bus,
            ),
        )

        settings_stack = SettingsStack(
            self,
            "MediaLakeSettings",
            props=SettingsStackProps(
                access_logs_bucket_name=props.base_infrastructure.access_logs_bucket.bucket_name,
                media_assets_bucket_name=props.base_infrastructure.media_assets_s3_bucket.bucket_name,
                iac_assets_bucket_name=props.base_infrastructure.iac_assets_bucket.bucket_name,
                external_payload_bucket_name=props.base_infrastructure.external_payload_bucket.bucket_name,
                ddb_export_bucket_name=props.base_infrastructure.ddb_export_bucket.bucket_name,
                pipelines_nodes_templates_bucket_name=nodes_stack.pipelines_nodes_templates_bucket.bucket_name,
                asset_sync_results_bucket_name=asset_sync_stack.results_bucket.bucket_name,
                user_interface_bucket_name=f"{config.resource_prefix}-user-interface-{self.account}-{config.environment}",
            ),
        )
        # Add dependencies to ensure stacks are created before settings_stack
        settings_stack.add_dependency(nodes_stack)
        settings_stack.add_dependency(asset_sync_stack)

        api_gateway_stack = ApiGatewayStack(
            self,
            "MediaLakeApiGatewayStack",
            props=ApiGatewayStackProps(
                iac_assets_bucket=props.base_infrastructure.iac_assets_bucket,
                external_payload_bucket=props.base_infrastructure.external_payload_bucket,
                media_assets_bucket=props.base_infrastructure.media_assets_s3_bucket,
                pipelines_nodes_templates_bucket=nodes_stack.pipelines_nodes_templates_bucket,
                asset_table_file_hash_index_arn=props.base_infrastructure.asset_table_file_hash_index_arn,
                asset_table_asset_id_index_arn=props.base_infrastructure.asset_table_asset_id_index_arn,
                asset_table_s3_path_index_arn=props.base_infrastructure.asset_table_s3_path_index_arn,
                pipelines_event_bus=props.base_infrastructure.pipelines_event_bus,
                asset_table=props.base_infrastructure.asset_table,
                vpc=props.base_infrastructure.vpc,
                security_group=props.base_infrastructure.security_group,
                collection_endpoint=props.base_infrastructure.collection_endpoint,
                collection_arn=props.base_infrastructure.collection_arn,
                access_log_bucket=props.base_infrastructure.access_log_bucket,
                pipeline_table=props.base_infrastructure.pipeline_table,
                pipelines_nodes_table=nodes_stack.pipelines_nodes_table,
                node_table=nodes_stack.pipelines_nodes_table,
                asset_sync_job_table=asset_sync_stack.asset_sync_job_table,
                asset_sync_engine_lambda=asset_sync_stack.asset_sync_engine_lambda,
                system_settings_table=settings_stack.system_settings_table_name,
                auth_table_name=props.authorization_stack._auth_table.table_name,
                avp_policy_store_id=props.authorization_stack._policy_store.attr_policy_store_id,
                avp_policy_store_arn=f"arn:aws:verifiedpermissions::{cdk.Aws.ACCOUNT_ID}:policy-store/{props.authorization_stack._policy_store.attr_policy_store_id}",
                api_keys_table_arn=settings_stack.api_keys_table_arn,
                cognito_user_pool_id=props.cognito_stack.user_pool_id,
                api_keys_table_name=settings_stack.api_keys_table_name,
                rest_api_id=ResourceImporter.get_rest_api_id(),  # Pass the ID instead of the object
                x_origin_verify_secret_arn=ResourceImporter.get_x_origin_verify_secret_arn(),  # Pass the ARN instead of the object
                user_pool=props.cognito_stack.user_pool,
                identity_pool=props.cognito_stack.identity_pool,
                user_pool_client=props.cognito_stack.user_pool_client,
                waf_acl_arn=ResourceImporter.get_waf_acl_arn(),  # Use importer instead of direct access
                cloudfront_domain=props.cloudfront_domain,  # CloudFront domain passed from UserInterfaceStack
                # user_table=users_groups_roles_stack.user_table,
                s3_vector_bucket_name=props.base_infrastructure.s3_vector_bucket_name,
                ui_origin_host=props.ui_origin_host,  # Custom UI origin host, if configured
            ),
        )

        users_groups_roles_stack = UsersGroupsStack(
            self,
            "MediaLakeUsersGroupsRolesStack",
            props=UsersGroupsStackProps(
                cognito_user_pool=props.cognito_stack.user_pool,
                cognito_app_client=props.cognito_stack.user_pool_client,
                x_origin_verify_secret=self.shared_x_origin_secret,
                auth_table_name=props.authorization_stack._auth_table.table_name,
                avp_policy_store_id=props.authorization_stack._policy_store.attr_policy_store_id,
                authorizer=api_gateway_stack.authorizer,
                api_resource=self.shared_rest_api,
            ),
        )
        users_groups_roles_stack.add_dependency(props.authorization_stack)

        # Store reference to users_groups_roles_stack
        self._users_groups_roles_stack = users_groups_roles_stack

        # Create the Collections Stack
        collections_stack = CollectionsStack(
            self,
            "MediaLakeCollectionsStack",
            props=CollectionsStackProps(
                cognito_user_pool=props.cognito_stack.user_pool,
                x_origin_verify_secret=self.shared_x_origin_secret,
                authorizer=api_gateway_stack.authorizer,
                api_resource=self.shared_rest_api,
                collection_endpoint=props.base_infrastructure.collection_endpoint,
                collection_arn=props.base_infrastructure.collection_arn,
                opensearch_index="media",
                vpc=props.base_infrastructure.vpc,
                security_group=props.base_infrastructure.security_group,
                media_assets_bucket=props.base_infrastructure.media_assets_s3_bucket,
            ),
        )
        collections_stack.add_dependency(props.authorization_stack)

        # Store reference to collections_stack
        self._collections_stack = collections_stack

        # Create the Collection Types Settings Stack
        collection_types_stack = CollectionTypesStack(
            self,
            "MediaLakeCollectionTypesSettings",
            props=CollectionTypesStackProps(
                cognito_user_pool=props.cognito_stack.user_pool,
                authorizer=api_gateway_stack.authorizer,
                api_resource=self.shared_rest_api,
                x_origin_verify_secret=self.shared_x_origin_secret,
                collections_table=collections_stack.collections_table,
                system_settings_table=settings_stack.system_settings_table.table,
                api_keys_table=settings_stack.api_keys_table.table,
            ),
        )
        collection_types_stack.add_dependency(collections_stack)
        collection_types_stack.add_dependency(api_gateway_stack)
        collection_types_stack.add_dependency(settings_stack)

        # Store reference to collection_types_stack
        self._collection_types_stack = collection_types_stack

        groups_stack = GroupsStack(
            self,
            "MediaLakeGroups",
            props=GroupsStackProps(
                # x_origin_verify_secret=props.api_gateway_core_stack.x_origin_verify_secret,
                cognito_user_pool=props.cognito_stack.user_pool,
                auth_table=props.authorization_stack.auth_table,
                authorizer=api_gateway_stack.authorizer,
                api_resource=self.shared_rest_api,  # Use shared object
            ),
        )
        groups_stack.add_dependency(props.authorization_stack)

        # Store reference to groups_stack
        self._groups_stack = groups_stack

        # Add dependency to ensure authorization stack is created before API Gateway stack
        api_gateway_stack.add_dependency(props.authorization_stack)

        # Create integrations stack first so we can pass its table to pipeline stack
        integrations_stack = IntegrationsEnvironmentStack(
            self,
            "MediaLakeIntegrationsEnvironment",
            props=IntegrationsEnvironmentStackProps(
                api_resource=self.shared_rest_api,
                cognito_user_pool=props.cognito_stack.user_pool,
                x_origin_verify_secret=self.shared_x_origin_secret,
                pipelines_nodes_table=nodes_stack.pipelines_nodes_table,
                post_pipelines_lambda=None,
                authorizer=api_gateway_stack.authorizer,
            ),
        )

        # Store reference to integrations_stack
        self._integrations_stack = integrations_stack

        pipeline_stack = PipelineStack(
            self,
            "MediaLakePipeline",
            props=PipelineStackProps(
                iac_assets_bucket=props.base_infrastructure.iac_assets_bucket,
                cognito_user_pool=props.cognito_stack.user_pool,
                cognito_app_client=props.cognito_stack.user_pool_client,
                asset_table=props.base_infrastructure.asset_table,
                connector_table=api_gateway_stack.connector_table,
                node_table=nodes_stack.pipelines_nodes_table,
                pipeline_table=props.base_infrastructure.pipeline_table,
                integrations_table=integrations_stack.integrations_table,
                external_payload_bucket=props.base_infrastructure.external_payload_bucket,
                pipelines_nodes_templates_bucket=nodes_stack.pipelines_nodes_templates_bucket,
                open_search_endpoint=props.base_infrastructure.collection_endpoint,
                vpc=props.base_infrastructure.vpc,
                security_group=props.base_infrastructure.security_group,
                pipelines_event_bus=props.base_infrastructure.pipelines_event_bus,
                media_assets_bucket=props.base_infrastructure.media_assets_s3_bucket,
                x_origin_verify_secret=self.shared_x_origin_secret,
                collection_endpoint=props.base_infrastructure.collection_endpoint,
                mediaconvert_queue_arn=nodes_stack.mediaconvert_queue_arn,
                mediaconvert_role_arn=nodes_stack.mediaconvert_role_arn,
                # S3 Vector configuration
                s3_vector_bucket_name=props.base_infrastructure.s3_vector_bucket_name,
                s3_vector_index_name=props.base_infrastructure.s3_vector_index_name,
                s3_vector_dimension=props.base_infrastructure.s3_vector_dimension,
                authorizer=api_gateway_stack.authorizer,
                api_resource=self.shared_rest_api,
            ),
        )

        # Store reference to pipeline_stack
        self._pipeline_stack = pipeline_stack

        # Now that pipeline_stack is created, configure the integrations stack with the pipeline lambda
        integrations_stack.set_post_pipelines_lambda(
            pipeline_stack.post_pipelines_async_handler
        )

        # NOTE: SettingsApiStack is now deprecated and replaced by CollectionTypesStack
        # which consolidates all settings endpoints (collection-types, system settings, API keys)
        # into a single Lambda function for better maintainability
        #
        # _ = SettingsApiStack(
        #     self,
        #     "MediaLakeSettingsApi",
        #     props=SettingsApiStackProps(
        #         authorizer=api_gateway_stack.authorizer.authorizer_id,
        #         api_resource=self.shared_rest_api,
        #         cognito_user_pool=props.cognito_stack.user_pool,
        #         cognito_app_client=props.cognito_stack.user_pool_client_id,
        #         x_origin_verify_secret=self.shared_x_origin_secret,
        #         system_settings_table_name=settings_stack.system_settings_table_name,
        #         system_settings_table_arn=settings_stack.system_settings_table_arn,
        #         api_keys_table_name=settings_stack.api_keys_table_name,
        #         api_keys_table_arn=settings_stack.api_keys_table_arn,
        #     ),
        # )
        # self._settings_api_stack = _

        # Create Updates API Stack for auto-upgrade system
        updates_api_stack = UpdatesApiStack(
            self,
            "MediaLakeUpdatesApi",
            props=UpdatesApiStackProps(
                authorizer=api_gateway_stack.authorizer,
                api_resource=self.shared_rest_api,
                cognito_user_pool=props.cognito_stack.user_pool,
                cognito_app_client=props.cognito_stack.user_pool_client_id,
                x_origin_verify_secret=self.shared_x_origin_secret,
                system_settings_table_name=settings_stack.system_settings_table_name,
                system_settings_table_arn=settings_stack.system_settings_table_arn,
            ),
        )

        # Store the UpdatesApiStack reference
        self._updates_api_stack = updates_api_stack

        # # Create the Permissions Stack as a nested stack
        # _ = PermissionsStack(
        #     "MediaLakePermissionsStack",
        #     props=PermissionsStackProps(
        #         api_resource=props.api_gateway_core_stack.rest_api,
        #         x_origin_verify_secret=props.api_gateway_core_stack.x_origin_verify_secret,
        #         cognito_user_pool=props.cognito_stack.user_pool,
        #         auth_table=props.authorization_stack.auth_table,
        #     ),
        # )

        # Store the API Gateway stack reference
        self._api_gateway_stack = api_gateway_stack

        # Register resources with the collector to avoid circular dependencies
        props.resource_collector.add_resource(api_gateway_stack)

        # Register individual resources if they exist
        if hasattr(api_gateway_stack, "api_resources"):
            api_resources = api_gateway_stack.api_resources
            if api_resources:
                for resource in api_resources:
                    if resource is not None:
                        props.resource_collector.add_resource(resource)

        # Register other important resources that might be needed for deployment
        if hasattr(api_gateway_stack, "health_lambda"):
            props.resource_collector.add_resource(api_gateway_stack.health_lambda)

        if hasattr(api_gateway_stack, "connector_sync_lambda"):
            props.resource_collector.add_resource(
                api_gateway_stack.connector_sync_lambda
            )

        # Register the settings API stack if it has resources
        # NOTE: SettingsApiStack is now deprecated - using CollectionTypesStack instead
        # if hasattr(self, "_settings_api_stack"):
        #     props.resource_collector.add_resource(self._settings_api_stack)

        # Register the updates API stack if it has resources
        if hasattr(self, "_updates_api_stack"):
            props.resource_collector.add_resource(self._updates_api_stack)

        # Register other important stacks that might have resources
        if hasattr(self, "_users_groups_roles_stack"):
            props.resource_collector.add_resource(self._users_groups_roles_stack)

        if hasattr(self, "_groups_stack"):
            props.resource_collector.add_resource(self._groups_stack)

        if hasattr(self, "_integrations_stack"):
            props.resource_collector.add_resource(self._integrations_stack)

        if hasattr(self, "_pipeline_stack"):
            props.resource_collector.add_resource(self._pipeline_stack)

        if hasattr(self, "_collections_stack"):
            props.resource_collector.add_resource(self._collections_stack)

        if hasattr(self, "_collection_types_stack"):
            props.resource_collector.add_resource(self._collection_types_stack)

    @property
    def connector_table(self):
        return self._api_gateway_stack.connector_table


medialake_stack = MediaLakeStack(
    app,
    "MediaLakeStack",
    props=MediaLakeStackProps(
        # api_gateway_core_stack=api_gateway_core_stack,  # Removed to break circular dependency
        base_infrastructure=base_infrastructure,
        authorization_stack=authorization_stack,
        cognito_stack=cognito_stack,
        resource_collector=api_resource_collector,  # Pass the resource collector
        cloudfront_domain="",  # Will be set after UI stack is created
        ui_origin_host=None,  # Will be set after UI stack is created
    ),
    env=env,
)
# medialake_stack.add_dependency(api_gateway_core_stack)

# Use the collector instead of accessing the stack directly
resource_count = api_resource_collector.get_resource_count()
print(f"Creating deployment stack with {resource_count} resources")

if resource_count == 0:
    print(
        "Warning: No resources collected. Deployment stack may not have proper dependencies."
    )

# Create API Gateway Deployment Stack BEFORE User Interface Stack
# This ensures the SSM parameter for stage name is created before UI stack tries to read it
api_gateway_deployment_stack = ApiGatewayDeploymentStack(
    app,
    "MediaLakeApiGatewayDeployment",
    props=ApiGatewayDeploymentStackProps(
        api_dependencies=api_resource_collector.get_resources(),  # Use the collector
    ),
    env=env,
)
api_gateway_deployment_stack.add_dependency(api_gateway_core_stack)
api_gateway_deployment_stack.add_dependency(medialake_stack)

# NOW create User Interface Stack after deployment stack has created the SSM parameter
# This stack reads the API Gateway stage name from SSM Parameter Store
user_interface_stack = UserInterfaceStack(
    app,
    "MediaLakeUserInterface",
    props=UserInterfaceStackProps(
        cognito_user_pool_id=cognito_stack.user_pool_id,
        cognito_user_pool_client_id=cognito_stack.user_pool_client_id,
        cognito_identity_pool=cognito_stack.identity_pool,
        cognito_user_pool_arn=cognito_stack.user_pool_arn,
        cognito_domain_prefix=cognito_stack.cognito_domain_prefix,
        # Use CloudFormation imports to avoid circular dependencies
        api_gateway_rest_id="",  # Will be imported from CloudFormation
        api_gateway_stage="",  # Will be read from SSM Parameter Store
        # Buckets will be imported from BaseInfrastructureStack exports
        cloudfront_waf_acl_arn=waf_acl_ssm_param_name,
    ),
    env=env,
)
user_interface_stack.add_dependency(base_infrastructure)
user_interface_stack.add_dependency(api_gateway_core_stack)
user_interface_stack.add_dependency(edge_lambda_stack)
user_interface_stack.add_dependency(
    api_gateway_deployment_stack
)  # Must wait for SSM parameter

# Create the Cognito Update Stack (between user_interface_stack and cleanup_stack)
cognito_update_stack = CognitoUpdateStack(
    app,
    "MediaLakeCognitoUpdate",
    props=CognitoUpdateStackProps(
        cognito_user_pool=cognito_stack.user_pool,
        cognito_user_pool_id=cognito_stack.user_pool_id,
        cognito_user_pool_arn=cognito_stack.user_pool_arn,
        auth_table_name=authorization_stack._auth_table.table_name,
    ),
    env=env,
)
cognito_update_stack.add_dependency(user_interface_stack)
cognito_update_stack.add_dependency(authorization_stack)

cleanup_stack = CleanupStack(
    app,
    "MediaLakeCleanupStack",
    props=CleanupStackProps(
        pipelines_event_bus=base_infrastructure.pipelines_event_bus,
        pipeline_table=base_infrastructure.pipeline_table,
        connector_table=medialake_stack.connector_table,
    ),
    env=env,
)
cleanup_stack.add_dependency(medialake_stack)
cleanup_stack.add_dependency(user_interface_stack)
cleanup_stack.add_dependency(cognito_update_stack)
cleanup_stack.add_dependency(api_gateway_deployment_stack)
cleanup_stack.add_dependency(api_gateway_core_stack)

if config.resource_application_tag:
    cdk.Tags.of(app).add("Application", config.resource_application_tag)

app.synth()

# AWS Solutions checks
# cdk.Aspects.of(app).add(AwsSolutionsChecks())
