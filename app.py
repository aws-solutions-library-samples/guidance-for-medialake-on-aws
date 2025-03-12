#!/usr/bin/env python3
"""
This module serves as the entry point for the MediaLake CDK application.
"""
import os
import aws_cdk as cdk
from cdk_logger import CDKLogger, get_logger
from cdk_nag import AwsSolutionsChecks, NagSuppressions
from config import config

from medialake_stacks.api_gateway_stack import ApiGatewayStack, ApiGatewayStackProps
from medialake_stacks.clean_up_stack import CleanupStack, CleanupStackProps
from medialake_stacks.base_infrastructure import BaseInfrastructureStack
from medialake_stacks.lambda_warmer_stack import LambdaWarmerStack
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
import os

# Initialize global logger configuration
if hasattr(config, 'logging') and hasattr(config.logging, 'level'):
    CDKLogger.set_level(config.logging.level)

# Create application-level logger
logger = get_logger("CDKApp")
logger.info(f"Initializing MediaLake CDK App with log level: {config.logging.level}")

app = cdk.App()

# Define environment once
if "CDK_DEFAULT_ACCOUNT" in os.environ and "CDK_DEFAULT_REGION" in os.environ:
    env = cdk.Environment(account=os.environ["CDK_DEFAULT_ACCOUNT"], region=os.environ["CDK_DEFAULT_REGION"])
else:
    env = cdk.Environment(account=app.account, region=app.region)

# Create Lambda warmer stack if enabled
lambda_warmer = None
if config.lambda_tail_warming:
    lambda_warmer = LambdaWarmerStack(app, "MediaLakeLambdaWarmer", env=env)

# Create base infrastructure stack first
base_infrastructure = BaseInfrastructureStack(
    app, "MediaLakeBaseInfrastructure", env=env
)

# Create nodes stack
nodes_stack = NodesStack(
    app,
    "MediaLakeNodes",
    props=NodesStackProps(
        iac_bucket=base_infrastructure.iac_assets_bucket,
    ),
    env=env,
)

pipeline_nodes_stack = PipelineNodesStack(
    app,
    "MediaLakePipelineNodes",
    props=PipelineNodesStackProps(
        media_assets_bucket=base_infrastructure.media_assets_bucket,
        asset_table=base_infrastructure.asset_table,
    ),
    env=env,
)

asset_sync_stack = AssetSyncStack(
    app,
    "MediaLakeAssetSyncStack",
    props=AssetSyncStackProps(
        asset_table=base_infrastructure.asset_table,
        ingest_event_bus=base_infrastructure.ingest_event_bus,
    ),
    env=env,
)

# Create API Gateway Stack - includes auth and ui
api_gateway_stack = ApiGatewayStack(
    app,
    "MediaLakeApiGatewayStack",
    props=ApiGatewayStackProps(
        iac_assets_bucket=base_infrastructure.iac_assets_bucket,
        external_payload_bucket=base_infrastructure.external_payload_bucket,
        media_assets_bucket=base_infrastructure.media_assets_s3_bucket,
        pipelines_nodes_templates_bucket=nodes_stack.pipelines_nodes_templates_bucket,
        asset_table_file_hash_index_arn=base_infrastructure.asset_table_file_hash_index_arn,
        asset_table_asset_id_index_arn=base_infrastructure.asset_table_asset_id_index_arn,
        ingest_event_bus=base_infrastructure.ingest_event_bus,
        asset_table=base_infrastructure.asset_table,
        vpc=base_infrastructure.vpc,
        security_group=base_infrastructure.security_group,
        collection_endpoint=base_infrastructure.collection_endpoint,
        collection_arn=base_infrastructure.collection_arn,
        access_log_bucket=base_infrastructure.access_log_bucket,
        pipeline_table=base_infrastructure.pipeline_table,
        image_metadata_extractor_lambda=pipeline_nodes_stack.image_metadata_extractor_lambda,
        image_proxy_lambda=pipeline_nodes_stack.image_proxy_lambda,
        pipelines_nodes_table=nodes_stack.pipelines_nodes_table,
        node_table=nodes_stack.pipelines_nodes_table,
        asset_sync_state_machine=asset_sync_stack.asset_sync_state_machine,
        asset_sync_job_table=asset_sync_stack.asset_sync_job_table,
    ),
    env=env,
)

# Add Lambda warming to API Gateway functions if enabled
if lambda_warmer:
    for function in api_gateway_stack.get_functions():
        lambda_warmer.add_function_to_warming(function)

pipeline_stack = PipelineStack(
    app,
    "MediaLakePipeline",
    props=PipelineStackProps(
        iac_assets_bucket=base_infrastructure.iac_assets_bucket,
        trigger_node_function_arn=pipeline_nodes_stack.trigger_node_function_arn,
        image_metadata_extractor_function_arn=pipeline_nodes_stack.image_metadata_extractor_function_arn,
        image_proxy_function_arn=pipeline_nodes_stack.image_proxy_function_arn,
        video_metadata_extractor_function_arn=pipeline_nodes_stack.video_metadata_extractor_function_arn,
        audio_metadata_extractor_function_arn=pipeline_nodes_stack.video_metadata_extractor_function_arn,
        video_proxy_thumbnail_function_arn=pipeline_nodes_stack.video_proxy_thumbnail_function_arn,
        audio_proxy_thumbnail_function_arn=pipeline_nodes_stack.audio_proxy_thumbnail_function_arn,
        check_mediaconvert_status_function_arn=pipeline_nodes_stack.check_mediaconvert_status_function_arn,
        post_pipeline_lambda=api_gateway_stack.pipelines_create_handler,
    ),
    env=env,
)

cleanup_stack = CleanupStack(
    app,
    "MediaLakeCleanupStack",
    props=CleanupStackProps(
        ingest_event_bus=base_infrastructure.ingest_event_bus,
        pipeline_table=base_infrastructure.pipeline_table,
        connector_table=api_gateway_stack.connector_table,
    ),
    env=env,
)

api_gateway_stack.add_dependency(asset_sync_stack)
cleanup_stack.add_dependency(api_gateway_stack)
cleanup_stack.add_dependency(base_infrastructure)
cleanup_stack.add_dependency(pipeline_nodes_stack)
cleanup_stack.add_dependency(pipeline_stack)
cleanup_stack.add_dependency(nodes_stack)

if lambda_warmer:
    cleanup_stack.add_dependency(lambda_warmer)

if config.resource_application_tag:
    cdk.Tags.of(app).add("Application", config.resource_application_tag)

# AWS Solutions checks
# cdk.Aspects.of(app).add(AwsSolutionsChecks())

cdk.CfnOutput(
    api_gateway_stack,
    "UserInterfaceUrl",
    value=api_gateway_stack.user_interface_url,
    description="URL for the MediaLake User Interface",
)

app.synth()
