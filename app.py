#!/usr/bin/env python3
"""
This module serves as the entry point for the MediaLake CDK application.
"""
import aws_cdk as cdk

# from medialake_config import config
from config import config
from medialake_stacks.api_gateway_stack import ApiGatewayStack, ApiGatewayStackProps
from medialake_constructs.cognito import CognitoConstruct, CognitoProps
from medialake_constructs.api_gateway.api_gateway_main_construct import (
    ApiGatewayConstruct,
)
from medialake_constructs.api_gateway.api_gateway_connectors import (
    ConnectorsConstruct,
    ConnectorsProps,
)
from medialake_constructs.api_gateway.api_gateway_pipelines import (
    ApiGatewayPipelinesConstruct,
    ApiGatewayPipelinesProps,
)
from medialake_constructs.api_gateway.api_gateway_search import (
    SearchConstruct,
    SearchProps,
)
from medialake_constructs.api_gateway.api_gateway_assets import (
    AssetsConstruct,
    AssetsProps,
)
from medialake_constructs.api_gateway.api_gateway_settings import (
    SettingsConstruct,
    SettingsConstructProps,
)
from medialake_constructs.update_construct import UpdateConstruct, UpdateConstructProps
from medialake_stacks.clean_up_stack import CleanupStack, CleanupStackProps
from medialake_stacks.pipelines_executions_stack import (
    PipelinesExecutionsStack,
    PipelinesExecutionsStackProps,
)

from medialake_stacks.pipeline_nodes_stack import (
    PipelineNodesStack,
    PipelineNodesStackProps,
)
from medialake_constructs.userInterface import UIConstruct, UIConstructProps
from medialake_stacks.base_infrastructure import BaseInfrastructureStack
from medialake_stacks.medialake_monitoring_stack import MediaLakeMonitoringStack
from cdk_nag import AwsSolutionsChecks, NagSuppressions


class MediaLakeStack(cdk.Stack):
    def __init__(self, scope: cdk.App, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        # Create cleanup stack first, this stack is used to cleanup resources that have been created within MediaLake and haven't been deleted in the UI prior to deleting MediaLake.
        cleanup_stack = CleanupStack(
            self, "CleanupStack", props=CleanupStackProps(stub="test")
        )

        # Create base infrastructure with cleanup dependency
        base_infrastructure = BaseInfrastructureStack(
            self, "BaseInfrastructure", env=kwargs.get("env")
        )
        base_infrastructure.add_dependency(cleanup_stack)

        # Create monitoring stack with base infrastructure dependency
        # monitoring_stack = MediaLakeMonitoringStack(
        #     self,
        #     "Monitoring",
        #     domain_name=f"{config.global_prefix}-os-{config.primary_region}-{config.environment}",
        #     table_name="medialake-asset-table",
        #     env=kwargs.get("env"),
        # )
        # monitoring_stack.add_dependency(base_infrastructure)

        # api_gateway_stack = ApiGatewayStack(
        #     self,
        #     "ApiGatewayStack",
        #     props=ApiGatewayStackProps(
        #         cognit_user_pool=self._cognito.user_pool,
        #         iac_assets_bucket=base_infrastructure.iac_assets_bucket,
        #         media_assets_bucket=base_infrastructure.media_assets_bucket,
        #         asset_table_file_hash_index_arn=base_infrastructure.asset_table_file_hash_index_arn,
        #         asset_table_asset_id_index_arn=base_infrastructure.asset_table_asset_id_index_arn,
        #         resource_table=cleanup_stack.resource_table,
        #         ingest_event_bus=base_infrastructure.ingest_event_bus,
        #     ),
        # )

        # api_gateway_stack.node.add_dependency(cleanup_stack)

        # User auth with Cognito
        self._cognito = CognitoConstruct(
            self,
            "Cognito",
            props=CognitoProps(),
        )
        self._cognito.node.add_dependency(cleanup_stack)

        # Create main API Gateway construct
        self.api_gateway = ApiGatewayConstruct(
            self,
            "ApiGateway",
            user_pool=self._cognito.user_pool,
        )
        self.api_gateway.node.add_dependency(cleanup_stack)

        # Create User Interface
        self._ui = UIConstruct(
            self,
            "UserInterface",
            self.api_gateway.rest_api.rest_api_id,
            self._cognito.user_pool,
            self._cognito.user_pool_client,
            self._cognito.identity_pool,
            props=UIConstructProps(),
        )
        self._ui.node.add_dependency(cleanup_stack)

        self._pipelines_executions_stack = PipelinesExecutionsStack(
            self,
            "PipelinesExecutions",
            props=PipelinesExecutionsStackProps(
                x_origin_verify_secret=self.api_gateway.x_origin_verify_secret,
            ),
        )
        self._pipelines_executions_stack.node.add_dependency(cleanup_stack)

        self._pipeline_nodes_stack = PipelineNodesStack(
            self,
            "PipelineNodes",
            props=PipelineNodesStackProps(
                asset_table=base_infrastructure.asset_table,
            ),
        )
        self._pipeline_nodes_stack.node.add_dependency(base_infrastructure)

        # Create connectors construct
        connectors = ConnectorsConstruct(
            self,
            "Connectors",
            props=ConnectorsProps(
                asset_table=base_infrastructure.asset_table,
                asset_table_file_hash_index_arn=base_infrastructure.asset_table_file_hash_index_arn,
                asset_table_asset_id_index_arn=base_infrastructure.asset_table_asset_id_index_arn,
                iac_assets_bucket=base_infrastructure.iac_assets_bucket,
                resource_table=cleanup_stack.resource_table,
                api_resource=self.api_gateway.rest_api,
                cognito_authorizer=self.api_gateway.cognito_authorizer,
                x_origin_verify_secret=self.api_gateway.x_origin_verify_secret,
                ingest_event_bus=base_infrastructure.ingest_event_bus,
            ),
        )

        connectors.node.add_dependency(cleanup_stack)

        # Create pipelines construct

        pipelines = ApiGatewayPipelinesConstruct(
            self,
            "Pipelines",
            api_resource=self.api_gateway.rest_api,
            cognito_authorizer=self.api_gateway.cognito_authorizer,
            ingest_event_bus=base_infrastructure.ingest_event_bus,
            x_origin_verify_secret=self.api_gateway.x_origin_verify_secret,
            iac_assets_bucket=base_infrastructure.iac_assets_bucket,
            media_assets_bucket=base_infrastructure.media_assets_bucket,
            props=ApiGatewayPipelinesProps(
                asset_table=base_infrastructure.asset_table,
                connector_table=connectors.connector_table,
                pipeline_table=base_infrastructure.pipeline_table,
                image_proxy_lambda=self._pipeline_nodes_stack.image_proxy_lambda,
                image_metadata_extractor_lambda=self._pipeline_nodes_stack.image_metadata_extractor_lambda,
                iac_assets_bucket=base_infrastructure.iac_assets_bucket,
                get_pipelines_executions_lambda=self._pipelines_executions_stack.get_pipelines_executions_lambda,
                post_retry_pipelines_executions_lambda=self._pipelines_executions_stack.post_retry_pipelines_executions_lambda,
            ),
        )
        pipelines.node.add_dependency(cleanup_stack)

        search = SearchConstruct(
            self,
            "Search",
            props=SearchProps(
                asset_table=base_infrastructure.asset_table,
                media_assets_bucket=base_infrastructure.media_assets_bucket,
                api_resource=self.api_gateway.rest_api,
                cognito_authorizer=self.api_gateway.cognito_authorizer,
                x_origin_verify_secret=self.api_gateway.x_origin_verify_secret,
                open_search_endpoint=base_infrastructure.collection_endpoint,
                open_search_arn=base_infrastructure.collection_arn,
                open_search_index="media",
                vpc=base_infrastructure.vpc,
                security_group=base_infrastructure.security_group,
            ),
        )

        search.node.add_dependency(cleanup_stack)

        assets = AssetsConstruct(
            self,
            "ApiGatewayAssets",
            props=AssetsProps(
                asset_table=base_infrastructure.asset_table,
                api_resource=self.api_gateway.rest_api,
                cognito_authorizer=self.api_gateway.cognito_authorizer,
                x_origin_verify_secret=self.api_gateway.x_origin_verify_secret,
            ),
        )
        assets.node.add_dependency(cleanup_stack)

        settings = SettingsConstruct(
            self,
            "ApiSettingsConstruct",
            props=SettingsConstructProps(
                api_resource=self.api_gateway.rest_api,
                cognito_authorizer=self.api_gateway.cognito_authorizer,
                cognito_user_pool=self._cognito.user_pool,
                cognito_app_client=self._cognito.user_pool_client,
                x_origin_verify_secret=self.api_gateway.x_origin_verify_secret,
            ),
        )
        settings.node.add_dependency(cleanup_stack)

        update_config = UpdateConstruct(
            self,
            "UpdateConfiguration",
            props=UpdateConstructProps(
                user_pool=self._cognito.user_pool,
                distribution_url=self._ui.distribution_url,
            ),
        )

        update_config.node.add_dependency(cleanup_stack)

        # Export the User Interface CloudFront URL
        cdk.CfnOutput(
            self,
            "UserInterfaceCloudFrontURL",
            value=self._ui.distribution_url,
            export_name=f"{id}-user-interface-url",
        )

        # Add CDK-nag suppressions for the stack
        NagSuppressions.add_stack_suppressions(
            self,
            [
                {
                    "id": "AwsSolutions-S1",
                    "reason": "S3 bucket does not require server-side encryption for this use case",
                },
                {
                    "id": "AwsSolutions-IAM4",
                    "reason": "IAM role uses AWSLambdaBasicExecutionRole which is required for Lambda function",
                },
            ],
        )


app = cdk.App()


primary_stack = MediaLakeStack(
    app,
    "MediaLake",
    env=cdk.Environment(region=config.primary_region, account=app.account),
)

if config.enable_ha and config.secondary_region:
    secondary_stack = MediaLakeStack(
        app,
        "MediaLakeSecondary",
        env=cdk.Environment(region=config.secondary_region, account=app.account),
    )

# # Add AWS Solutions checks to the entire app
# cdk.Aspects.of(app).add(AwsSolutionsChecks())

app.synth()
