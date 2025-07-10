#!/usr/bin/env python3
"""Entry point for the MediaLake CDK application."""
import os
from dataclasses import dataclass

import aws_cdk as cdk
from aws_cdk import aws_ssm as ssm
from constructs import Construct
from cdk_nag import (
    AwsSolutionsChecks,
    NagSuppressions,
)

from cdk_logger import CDKLogger, get_logger
from config import config

from medialake_stacks.api_gateway_stack import ApiGatewayStack, ApiGatewayStackProps
from medialake_stacks.api_gateway_core_stack import (
    ApiGatewayCoreStack,
    ApiGatewayCoreStackProps,
)
from medialake_stacks.cognito_stack import (
    CognitoStack,
    CognitoStackProps,
)
from medialake_stacks.users_groups_stack import (
    UsersGroupsStack,
    UsersGroupsStackProps,
)
from medialake_stacks.authorization_stack import (
    AuthorizationStack,
    AuthorizationStackProps,
)
from medialake_stacks.cognito_update_stack import (
    CognitoUpdateStack,
    CognitoUpdateStackProps,
)
from medialake_stacks.permissions_stack import (
    PermissionsStack,
    PermissionsStackProps,
)
from medialake_stacks.groups_stack import (
    GroupsStack,
    GroupsStackProps,
)
from medialake_stacks.auth_lambda_stack import AuthLambdaStack, AuthLambdaStackProps
from medialake_stacks.settings_stack import SettingsStack, SettingsStackProps
from medialake_stacks.settings_api_stack import SettingsApiStack, SettingsApiStackProps
from medialake_stacks.user_interface_stack import (
    UserInterfaceStack,
    UserInterfaceStackProps,
)
from medialake_stacks.clean_up_stack import CleanupStack, CleanupStackProps
from medialake_stacks.base_infrastructure import BaseInfrastructureStack
from medialake_stacks.integrations_environment_stack import (
    IntegrationsEnvironmentStack,
    IntegrationsEnvironmentStackProps,
)
from medialake_stacks.pipeline_stack import (
    PipelineStack,
    PipelineStackProps,
)
from medialake_stacks.nodes_stack import NodesStack, NodesStackProps
from medialake_stacks.asset_sync_stack import AssetSyncStack, AssetSyncStackProps
from medialake_stacks.cloudfront_waf_stack import CloudFrontWafStack
from medialake_stacks.api_gateway_deployment_stack import (
    ApiGatewayDeploymentStack,
    ApiGatewayDeploymentStackProps,
)
from medialake_constructs.api_gateway.api_gateway_authorization import (
    AuthorizationApi,
    AuthorizationApiProps,
)

# Initialize global logger configuration
if hasattr(config, "logging") and hasattr(config.logging, "level"):
    CDKLogger.set_level(config.logging.level)

# Create application-level logger
logger = get_logger("CDKApp")
logger.info(f"Initializing media lake CDK code with log level: {config.logging.level}")

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


@dataclass
class MediaLakeStackProps:
    api_gateway_core_stack: ApiGatewayCoreStack
    base_infrastructure: BaseInfrastructureStack
    authorization_stack: AuthorizationStack
    cognito_stack: CognitoStack


class MediaLakeStack(cdk.Stack):
    def __init__(self, scope: Construct, id: str, props: MediaLakeStackProps, **kwargs):
        super().__init__(scope, id, **kwargs)

        users_groups_roles_stack = UsersGroupsStack(
            self,
            "UsersGroupsRolesStack",
            props=UsersGroupsStackProps(
                cognito_user_pool=props.cognito_stack.user_pool,
                cognito_app_client=props.cognito_stack.user_pool_client,
                x_origin_verify_secret=props.api_gateway_core_stack.x_origin_verify_secret,
                auth_table_name=props.authorization_stack._auth_table.table_name,
                avp_policy_store_id=props.authorization_stack._policy_store.attr_policy_store_id,
            ),
        )
        users_groups_roles_stack.add_dependency(props.authorization_stack)

        groups_stack = GroupsStack(
            self,
            "GroupsStack",
            props=GroupsStackProps(
                cognito_user_pool=props.cognito_stack.user_pool,
                auth_table=props.authorization_stack.auth_table,
            ),
        )
        groups_stack.add_dependency(props.authorization_stack)

        nodes_stack = NodesStack(
            self,
            "Nodes",
            props=NodesStackProps(
                iac_bucket=props.base_infrastructure.iac_assets_bucket,
            ),
        )

        asset_sync_stack = AssetSyncStack(
            self,
            "AssetSyncStack",
            props=AssetSyncStackProps(
                asset_table=props.base_infrastructure.asset_table,
                pipelines_event_bus=props.base_infrastructure.pipelines_event_bus,
            ),
        )

        settings_stack = SettingsStack(
            self, "Settings", props=SettingsStackProps(
                access_logs_bucket_name=props.base_infrastructure.access_logs_bucket.bucket_name,
                media_assets_bucket_name=props.base_infrastructure.media_assets_s3_bucket.bucket_name,
                iac_assets_bucket_name=props.base_infrastructure.iac_assets_bucket.bucket_name,
                external_payload_bucket_name=props.base_infrastructure.external_payload_bucket.bucket_name,
                ddb_export_bucket_name=props.base_infrastructure.ddb_export_bucket.bucket_name,
                pipelines_nodes_templates_bucket_name=nodes_stack.pipelines_nodes_templates_bucket.bucket_name,
                asset_sync_results_bucket_name=asset_sync_stack.results_bucket.bucket_name,
            )
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
                rest_api=props.api_gateway_core_stack.rest_api,
                x_origin_verify_secret=props.api_gateway_core_stack.x_origin_verify_secret,
                user_pool=props.cognito_stack.user_pool,
                identity_pool=props.cognito_stack.identity_pool,
                user_pool_client=props.cognito_stack.user_pool_client,
                waf_acl_arn=props.api_gateway_core_stack.waf_acl_arn,
                user_table=users_groups_roles_stack.user_table,
            ),
        )

        pipeline_stack = PipelineStack(self, "MediaLakePipeline", props=PipelineStackProps(
            iac_assets_bucket=props.base_infrastructure.iac_assets_bucket,
            cognito_user_pool=props.cognito_stack.user_pool,
            cognito_app_client=props.cognito_stack.user_pool_client,
            asset_table=props.base_infrastructure.asset_table,
            connector_table=api_gateway_stack.connector_table,
            node_table=nodes_stack.pipelines_nodes_table,
            pipeline_table=props.base_infrastructure.pipeline_table,
            external_payload_bucket=props.base_infrastructure.external_payload_bucket,
            pipelines_nodes_templates_bucket=nodes_stack.pipelines_nodes_templates_bucket,
            open_search_endpoint=props.base_infrastructure.collection_endpoint,
            vpc=props.base_infrastructure.vpc,
            security_group=props.base_infrastructure.security_group,
            pipelines_event_bus=props.base_infrastructure.pipelines_event_bus,
            media_assets_bucket=props.base_infrastructure.media_assets_s3_bucket,
            x_origin_verify_secret=props.api_gateway_core_stack.x_origin_verify_secret,
            collection_endpoint=props.base_infrastructure.collection_endpoint,
            mediaconvert_queue_arn=nodes_stack.mediaconvert_queue_arn,
            mediaconvert_role_arn=nodes_stack.mediaconvert_role_arn,
            ),
        )
        
        _ = SettingsApiStack(
            self,
            "MediaLakeSettingsApi",
            props=SettingsApiStackProps(
                cognito_user_pool=props.cognito_stack.user_pool,
                cognito_app_client=props.cognito_stack.user_pool_client_id,
                x_origin_verify_secret=props.api_gateway_core_stack.x_origin_verify_secret,
                system_settings_table_name=settings_stack.system_settings_table_name,
                system_settings_table_arn=settings_stack.system_settings_table_arn,
            ),
        )

        # Create the Permissions Stack as a nested stack
        _ = PermissionsStack(
            self,
            "MediaLakePermissionsStack",
            props=PermissionsStackProps(
                api_resource=props.api_gateway_core_stack.rest_api,
                x_origin_verify_secret=props.api_gateway_core_stack.x_origin_verify_secret,
                cognito_user_pool=props.cognito_stack.user_pool,
                auth_table=props.authorization_stack.auth_table,
            ),
        )

        _ = IntegrationsEnvironmentStack(self, "MediaLakeIntegrationsEnvironment", props=IntegrationsEnvironmentStackProps(
            api_resource=props.api_gateway_core_stack.rest_api,
            cognito_user_pool=props.cognito_stack.user_pool,
            x_origin_verify_secret=props.api_gateway_core_stack.x_origin_verify_secret,
            pipelines_nodes_table=nodes_stack.pipelines_nodes_table,
            post_pipelines_lambda=pipeline_stack.post_pipelines_async_handler,
            ),
        )

        self._api_gateway_stack = api_gateway_stack

    @property
    def connector_table(self):
        return self._api_gateway_stack.connector_table

medialake_stack = MediaLakeStack(
    app,
    "MediaLakeStack",
    props=MediaLakeStackProps(
        api_gateway_core_stack=api_gateway_core_stack,
        base_infrastructure=base_infrastructure,
        authorization_stack=authorization_stack,
        cognito_stack=cognito_stack,
    ),
    env=env,
)
medialake_stack.add_dependency(api_gateway_core_stack)

# Get API resources for dependencies
api_resources = medialake_stack._api_gateway_stack.api_resources

api_gateway_deployment_stack = ApiGatewayDeploymentStack(
    app,
    "MediaLakeApiGatewayDeployment",
    props=ApiGatewayDeploymentStackProps(
        api_dependencies=[medialake_stack._api_gateway_stack] + api_resources,
    ),
    env=env,
)
api_gateway_deployment_stack.add_dependency(api_gateway_core_stack)
api_gateway_deployment_stack.add_dependency(medialake_stack)

user_interface_stack = UserInterfaceStack(
    app,
    "MediaLakeUserInterface",
    props=UserInterfaceStackProps(
        cognito_user_pool_id=cognito_stack.user_pool_id,
        cognito_user_pool_client_id=cognito_stack.user_pool_client_id,
        cognito_identity_pool=cognito_stack.identity_pool,
        cognito_user_pool_arn=cognito_stack.user_pool_arn,
        cognito_domain_prefix=cognito_stack.cognito_domain_prefix,
        api_gateway_rest_id=api_gateway_core_stack.rest_api.rest_api_id,
        api_gateway_stage=api_gateway_deployment_stack.api_deployment_stage.stage_name,
        access_log_bucket=base_infrastructure.access_log_bucket,
        cloudfront_waf_acl_arn=waf_acl_ssm_param_name,
    ),
    env=env,
)
user_interface_stack.add_dependency(medialake_stack)

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