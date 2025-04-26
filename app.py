#!/usr/bin/env python3
"""
This module serves as the entry point for the MediaLake CDK application.
"""
import os
import aws_cdk as cdk
from cdk_logger import CDKLogger, get_logger
from cdk_nag import AwsSolutionsChecks, NagSuppressions # Used for AWS Solutions checks ad-hoc
from config import config
from aws_cdk import aws_ssm as ssm
from constructs import Construct
from dataclasses import dataclass

from medialake_stacks.api_gateway_stack import ApiGatewayStack, ApiGatewayStackProps
from medialake_stacks.api_gateway_core_stack import ApiGatewayCoreStack, ApiGatewayCoreStackProps
from medialake_stacks.users_groups_roles_stack import UsersGroupsRolesStack, UsersGroupsRolesStackProps
from medialake_stacks.settings_stack import SettingsStack, SettingsStackProps
from medialake_stacks.settings_api_stack import SettingsApiStack, SettingsApiStackProps
from medialake_stacks.user_interface_stack import UserInterfaceStack, UserInterfaceStackProps
from medialake_stacks.clean_up_stack import CleanupStack, CleanupStackProps
from medialake_stacks.base_infrastructure import BaseInfrastructureStack
# from medialake_stacks.lambda_warmer_stack import LambdaWarmerStack - Development paused, commented out for now
from medialake_stacks.integrations_environment_stack import IntegrationsEnvironmentStack, IntegrationsEnvironmentStackProps
from medialake_stacks.pipeline_stack import (
    PipelineStack,
    PipelineStackProps,
)
from medialake_stacks.pipeline_nodes_stack import (
    PipelineNodesStack,
    PipelineNodesStackProps,
)
from medialake_stacks.nodes_stack import NodesStack, NodesStackProps
from medialake_stacks.asset_sync_stack import AssetSyncStack, AssetSyncStackProps
from medialake_stacks.cloudfront_waf_stack import CloudFrontWafStack
from medialake_constructs.api_gateway.api_gateway_deployment_construct import (
    ApiGatewayDeploymentConstruct,
ApiGatewayDeploymentProps,
)
from medialake_stacks.api_gateway_deployment_stack import ApiGatewayDeploymentStack, ApiGatewayDeploymentStackProps

# from medialake_stacks.monitoring_stack import MonitoringStack - Development paused, commented out for now

# Initialize global logger configuration
if hasattr(config, 'logging') and hasattr(config.logging, 'level'):
    CDKLogger.set_level(config.logging.level)

# Create application-level logger
logger = get_logger("CDKApp")
logger.info(f"Initializing MediaLake CDK App with log level: {config.logging.level}")

app = cdk.App()

# us-east-1 environment, required for the WAF, certain configuration has to be deployed in us-east-1
env_us_east_1 = cdk.Environment(account=app.account, region="us-east-1")

if "CDK_DEFAULT_ACCOUNT" in os.environ and "CDK_DEFAULT_REGION" in os.environ:
    env = cdk.Environment(account=os.environ["CDK_DEFAULT_ACCOUNT"], region=os.environ["CDK_DEFAULT_REGION"])
else:
    env = cdk.Environment(account=app.account, region=app.region)


## Create Lambda warmer stack if enabled ( ### Development paused, currently not used ###
# lambda_warmer = None
# if config.lambda_tail_warming:
#     lambda_warmer = LambdaWarmerStack(app, "MediaLakeLambdaWarmer", env=env)



cloudfront_waf_stack = CloudFrontWafStack(app, "MediaLakeCloudFrontWAF", env=env_us_east_1)


base_infrastructure = BaseInfrastructureStack(app, "MediaLakeBaseInfrastructure", env=env)


api_gateway_core_stack = ApiGatewayCoreStack(app, "MediaLakeApiGatewayCore", props=ApiGatewayCoreStackProps(
    access_log_bucket=base_infrastructure.access_log_bucket,
    ), env=env
)

waf_acl_ssm_param_name = "/medialake/cloudfront-waf-acl-arn"

api_gateway_core_stack.add_dependency(base_infrastructure)
        
@dataclass 
class MediaLakeStackProps:
    api_gateway_core_stack: ApiGatewayCoreStack
    base_infrastructure: BaseInfrastructureStack

class MediaLakeStack(cdk.Stack):
    def __init__(self, scope: Construct, id: str, props: MediaLakeStackProps, **kwargs):
        super().__init__(scope, id, **kwargs)
        
        settings_stack = SettingsStack(self, "MediaLakeSettings", props=SettingsStackProps())
        nodes_stack = NodesStack(self, "MediaLakeNodes", props=NodesStackProps(
            iac_bucket=props.base_infrastructure.iac_assets_bucket,
            ),
        )
        pipeline_nodes_stack = PipelineNodesStack(self, "MediaLakePipelineNodes", props=PipelineNodesStackProps(
            media_assets_bucket=props.base_infrastructure.media_assets_bucket,
            asset_table=props.base_infrastructure.asset_table,
            ),
        )
        asset_sync_stack = AssetSyncStack(self, "MediaLakeAssetSyncStack", props=AssetSyncStackProps(
            asset_table=props.base_infrastructure.asset_table,
            ingest_event_bus=props.base_infrastructure.ingest_event_bus,
            ),
        )

        settings_api_stack = SettingsApiStack(self, "MediaLakeSettingsApi", props=SettingsApiStackProps(
            cognito_user_pool=props.api_gateway_core_stack.user_pool,
            cognito_app_client=props.api_gateway_core_stack.user_pool_client,
            x_origin_verify_secret=props.api_gateway_core_stack.x_origin_verify_secret,
            system_settings_table_name=settings_stack.system_settings_table_name,
            system_settings_table_arn=settings_stack.system_settings_table_arn,
            ),
        )
        
        users_groups_roles_stack = UsersGroupsRolesStack(self, "MediaLakeUsersGroupsRolesStack", props=UsersGroupsRolesStackProps(
            cognito_user_pool=props.api_gateway_core_stack.user_pool,
            cognito_app_client=props.api_gateway_core_stack.user_pool_client,
            x_origin_verify_secret=props.api_gateway_core_stack.x_origin_verify_secret,
            ),
        )

        api_gateway_stack = ApiGatewayStack(self, "MediaLakeApiGatewayStack", props=ApiGatewayStackProps(
            iac_assets_bucket=props.base_infrastructure.iac_assets_bucket,
            external_payload_bucket=props.base_infrastructure.external_payload_bucket,
            media_assets_bucket=props.base_infrastructure.media_assets_s3_bucket,
            pipelines_nodes_templates_bucket=nodes_stack.pipelines_nodes_templates_bucket,
            asset_table_file_hash_index_arn=props.base_infrastructure.asset_table_file_hash_index_arn,
            asset_table_asset_id_index_arn=props.base_infrastructure.asset_table_asset_id_index_arn,
            asset_table_s3_path_index_arn=props.base_infrastructure.asset_table_s3_path_index_arn,
            ingest_event_bus=props.base_infrastructure.ingest_event_bus,
            asset_table=props.base_infrastructure.asset_table,
            vpc=props.base_infrastructure.vpc,
            security_group=props.base_infrastructure.security_group,
            collection_endpoint=props.base_infrastructure.collection_endpoint,
            collection_arn=props.base_infrastructure.collection_arn,
            access_log_bucket=props.base_infrastructure.access_log_bucket,
            pipeline_table=props.base_infrastructure.pipeline_table,
            image_metadata_extractor_lambda=pipeline_nodes_stack.image_metadata_extractor_lambda,
            image_proxy_lambda=pipeline_nodes_stack.image_proxy_lambda,
            pipelines_nodes_table=nodes_stack.pipelines_nodes_table,
            node_table=nodes_stack.pipelines_nodes_table,
            asset_sync_job_table=asset_sync_stack.asset_sync_job_table,
            asset_sync_engine_lambda=asset_sync_stack.asset_sync_engine_lambda,
            system_settings_table=settings_stack.system_settings_table_name,
            rest_api=props.api_gateway_core_stack.rest_api,
            x_origin_verify_secret=props.api_gateway_core_stack.x_origin_verify_secret,
            user_pool=props.api_gateway_core_stack.user_pool,
            identity_pool=props.api_gateway_core_stack.identity_pool,
            user_pool_client=props.api_gateway_core_stack.user_pool_client,
            waf_acl_arn=props.api_gateway_core_stack.waf_acl_arn,
            ),
        )
        
        pipeline_stack = PipelineStack(self, "MediaLakePipeline", props=PipelineStackProps(
            iac_assets_bucket=props.base_infrastructure.iac_assets_bucket,
            trigger_node_function_arn=pipeline_nodes_stack.trigger_node_function_arn,
            image_metadata_extractor_function_arn=pipeline_nodes_stack.image_metadata_extractor_function_arn,
            image_proxy_function_arn=pipeline_nodes_stack.image_proxy_function_arn,
            video_metadata_extractor_function_arn=pipeline_nodes_stack.video_metadata_extractor_function_arn,
            audio_metadata_extractor_function_arn=pipeline_nodes_stack.audio_metadata_extractor_function_arn,
            video_proxy_thumbnail_function_arn=pipeline_nodes_stack.video_proxy_thumbnail_function_arn,
            audio_proxy_thumbnail_function_arn=pipeline_nodes_stack.audio_proxy_thumbnail_function_arn,
            check_mediaconvert_status_function_arn=pipeline_nodes_stack.check_mediaconvert_status_function_arn,
            cognito_user_pool=props.api_gateway_core_stack.user_pool,
            cognito_app_client=props.api_gateway_core_stack.user_pool_client,
            asset_table=props.base_infrastructure.asset_table,
            connector_table=api_gateway_stack.connector_table,
            node_table=nodes_stack.pipelines_nodes_table,
            pipeline_table=props.base_infrastructure.pipeline_table,
            image_proxy_lambda=pipeline_nodes_stack.image_proxy_lambda,
            image_metadata_extractor_lambda=pipeline_nodes_stack.image_metadata_extractor_lambda,
            external_payload_bucket=props.base_infrastructure.external_payload_bucket,
            pipelines_nodes_templates_bucket=nodes_stack.pipelines_nodes_templates_bucket,
            open_search_endpoint=props.base_infrastructure.collection_endpoint,
            vpc=props.base_infrastructure.vpc,
            security_group=props.base_infrastructure.security_group,
            ingest_event_bus=props.base_infrastructure.ingest_event_bus,
            media_assets_bucket=props.base_infrastructure.media_assets_s3_bucket,
            x_origin_verify_secret=props.api_gateway_core_stack.x_origin_verify_secret,
            collection_endpoint=props.base_infrastructure.collection_endpoint,
            ),
        )
        
        integrations_environment_stack = IntegrationsEnvironmentStack(self, "MediaLakeIntegrationsEnvironment", props=IntegrationsEnvironmentStackProps(
            api_resource=props.api_gateway_core_stack.rest_api,
            cognito_user_pool=props.api_gateway_core_stack.user_pool,
            x_origin_verify_secret=props.api_gateway_core_stack.x_origin_verify_secret,
            pipelines_nodes_table=nodes_stack.pipelines_nodes_table,
            post_pipelines_v2_lambda=pipeline_stack.post_pipelinesv2_async_handler,
            ),
        )
        
        # Store api_gateway_stack as an instance variable so it can be accessed by the property
        self._api_gateway_stack = api_gateway_stack
        
    @property
    def connector_table(self):
        return self._api_gateway_stack.connector_table


medialake_stack = MediaLakeStack(app, "MediaLakeStack",props=MediaLakeStackProps(
    api_gateway_core_stack=api_gateway_core_stack,
    base_infrastructure=base_infrastructure,
    ), env=env)
medialake_stack.add_dependency(api_gateway_core_stack)

# Get API resources for dependencies
api_resources = medialake_stack._api_gateway_stack.api_resources

api_gateway_deployment_stack = ApiGatewayDeploymentStack(
    app,
    "MediaLakeApiGatewayDeployment",
    props=ApiGatewayDeploymentStackProps(
        api_dependencies=[medialake_stack._api_gateway_stack] + api_resources,
    ), env=env
)
api_gateway_deployment_stack.add_dependency(api_gateway_core_stack)
api_gateway_deployment_stack.add_dependency(medialake_stack)

user_interface_stack = UserInterfaceStack(
    app,
    "MediaLakeUserInterface",
            props=UserInterfaceStackProps(
                cognito_user_pool_id=api_gateway_core_stack.user_pool_id,
                cognito_user_pool_client_id=api_gateway_core_stack.user_pool_client,
                cognito_identity_pool=api_gateway_core_stack.identity_pool,
                cognito_user_pool_arn=api_gateway_core_stack.user_pool_arn,
                cognito_domain_prefix=api_gateway_core_stack.cognito_domain_prefix,
                api_gateway_rest_id=api_gateway_core_stack.rest_api.rest_api_id,
                api_gateway_stage=api_gateway_deployment_stack.api_deployment_stage.stage_name,
                access_log_bucket=base_infrastructure.access_log_bucket,
                cloudfront_waf_acl_arn=waf_acl_ssm_param_name,
    ), env=env
)
user_interface_stack.add_dependency(medialake_stack)

if config.resource_application_tag:
    cdk.Tags.of(app).add("Application", config.resource_application_tag)

# cdk.CfnOutput(
#     user_interface_stack,
#     "UserInterfaceUrl",
#     value=user_interface_stack.user_interface_url,
#     description="URL for the MediaLake User Interface",
# )

medialake_stack.add_dependency(cloudfront_waf_stack)

cleanup_stack = CleanupStack(
    app,
    "MediaLakeCleanupStack",
    props=CleanupStackProps(
        ingest_event_bus=base_infrastructure.ingest_event_bus,
        pipeline_table=base_infrastructure.pipeline_table,
        connector_table=medialake_stack.connector_table,
    ), env=env
)

app.synth()


# AWS Solutions checks
# cdk.Aspects.of(app).add(AwsSolutionsChecks())

# cleanup_stack.add_dependency(monitoring_stack)

# Create the monitoring stack
# monitoring_stack = MonitoringStack(
#     app,
#     "MediaLakeMonitoringStack",
#     config_path="config.json",
#     env=env,
# )

# if lambda_warmer:
#     cleanup_stack.add_dependency(lambda_warmer)

# cdk.CfnOutput(
#     monitoring_stack,
#     "MonitoringDashboardUrl",
#     value=f"https://{app.region}.console.aws.amazon.com/cloudwatch/home?region={app.region}#dashboards:name={monitoring_stack.dashboard.dashboard_name}",
#     description="URL for the MediaLake Monitoring Dashboard",
# )