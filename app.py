#!/usr/bin/env python3
"""
This module serves as the entry point for the MediaLake CDK application.
"""
import aws_cdk as cdk
from cdk_nag import AwsSolutionsChecks, NagSuppressions
from config import config

from medialake_stacks.api_gateway_stack import ApiGatewayStack, ApiGatewayStackProps
from medialake_stacks.clean_up_stack import CleanupStack, CleanupStackProps
from medialake_stacks.base_infrastructure import BaseInfrastructureStack
from medialake_stacks.pipeline_nodes_stack import (
    PipelineNodesStack,
    PipelineNodesStackProps,
)

app = cdk.App()

# Create base infrastructure stack first
base_infrastructure = BaseInfrastructureStack(
    app,
    "MediaLakeBaseInfrastructure",
    env=cdk.Environment(region=config.primary_region, account=app.account),
)

pipeline_nodes_stack = PipelineNodesStack(
    app,
    "MediaLakePipelineNodes",
    props=PipelineNodesStackProps(asset_table=base_infrastructure.asset_table),
)

# Create API Gateway Stack - includes auth and ui
api_gateway_stack = ApiGatewayStack(
    app,
    "MediaLakeApiGatewayStack",
    props=ApiGatewayStackProps(
        iac_assets_bucket=base_infrastructure.iac_assets_bucket,
        media_assets_bucket=base_infrastructure.media_assets_bucket,
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
    ),
    env=cdk.Environment(region=config.primary_region, account=app.account),
)

cleanup_stack = CleanupStack(
    app,
    "MediaLakeCleanupStack",
    props=CleanupStackProps(
        ingest_event_bus=base_infrastructure.ingest_event_bus,
        pipeline_table=base_infrastructure.pipeline_table,
        connector_table=api_gateway_stack.connector_table,
    ),
)

cleanup_stack.add_dependency(api_gateway_stack)
cleanup_stack.add_dependency(base_infrastructure)
cleanup_stack.add_dependency(pipeline_nodes_stack)

cdk.Tags.of(app).add("Application", "MediaLake")

# Add AWS Solutions checks to the entire app
# cdk.Aspects.of(app).add(AwsSolutionsChecks())

cdk.CfnOutput(
    api_gateway_stack,
    "UserInterfaceUrl",
    value=api_gateway_stack.user_interface_url,
    description="URL for the MediaLake User Interface",
)

app.synth()
