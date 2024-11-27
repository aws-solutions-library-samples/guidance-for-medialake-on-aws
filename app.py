#!/usr/bin/env python3
"""
This module serves as the entry point for the MediaLake CDK application.
"""
import aws_cdk as cdk

# from medialake_config import config
from config import config
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
from medialake_constructs.userInterface import UIConstruct, UIConstructProps
from medialake_stacks.base_infrastructure import BaseInfrastructureStack
from cdk_nag import AwsSolutionsChecks, NagSuppressions


class MediaLakeStack(cdk.Stack):
    def __init__(self, scope: cdk.App, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        # Create base infrastructure
        base_infrastructure = BaseInfrastructureStack(
            self, "BaseInfrastructure", env=kwargs.get("env")
        )

        cleanup_stack = CleanupStack(
            self, "CleanupStack", props=CleanupStackProps(stub="test")
        )

        # User auth with Cognito
        self._cognito = CognitoConstruct(
            self,
            "Cognito",
            props=CognitoProps(),
        )

        # Create main API Gateway construct
        api_gateway = ApiGatewayConstruct(
            self,
            "ApiGateway",
            user_pool=self._cognito.user_pool,
        )

        # Create User Interface
        self._ui = UIConstruct(
            self,
            "UserInterface",
            api_gateway.rest_api.rest_api_id,
            self._cognito.user_pool,
            self._cognito.user_pool_client,
            self._cognito.identity_pool,
            props=UIConstructProps(),
        )

        self._pipelines_executions_stack = PipelinesExecutionsStack(
            self,
            "PipelinesExecutions",
            props=PipelinesExecutionsStackProps(
                # x_origin_verify_secret=api_gateway.x_origin_verify_secret,
                test="test",
            ),
        )

        # Create connectors construct
        _ = ConnectorsConstruct(
            self,
            "Connectors",
            api_resource=api_gateway.api_resource,
            cognito_authorizer=api_gateway.cognito_authorizer,
            x_origin_verify_secret=api_gateway.x_origin_verify_secret,
            ingest_event_bus=base_infrastructure.ingest_event_bus,
            iac_assets_bucket=base_infrastructure.iac_assets_bucket,
            props=ConnectorsProps(
                asset_table=base_infrastructure.asset_table,
                asset_table_file_hash_index_arn=base_infrastructure.asset_table_file_hash_index_arn,
                asset_table_asset_id_index_arn=base_infrastructure.asset_table_asset_id_index_arn,
                iac_assets_bucket=base_infrastructure.iac_assets_bucket,
                resource_table=cleanup_stack.resource_table,
            ),
        )

        # Create pipelines construct
        _ = ApiGatewayPipelinesConstruct(
            self,
            "Pipelines",
            api_resource=api_gateway.api_resource,
            cognito_authorizer=api_gateway.cognito_authorizer,
            ingest_event_bus=base_infrastructure.ingest_event_bus,
            x_origin_verify_secret=api_gateway.x_origin_verify_secret,
            iac_assets_bucket=base_infrastructure.iac_assets_bucket,
            media_assets_bucket=base_infrastructure.media_assets_bucket,
            props=ApiGatewayPipelinesProps(
                asset_table=base_infrastructure.asset_table,
                iac_assets_bucket=base_infrastructure.iac_assets_bucket,
                get_pipelines_executions_lambda=self._pipelines_executions_stack.get_pipelines_executions_lambda,
                post_retry_pipelines_executions_lambda=self._pipelines_executions_stack.post_retry_pipelines_executions_lambda,
            ),
        )

        _ = SearchConstruct(
            self,
            "Search",
            props=SearchProps(
                asset_table=base_infrastructure.asset_table,
                api_resource=api_gateway.api_resource,
                cognito_authorizer=api_gateway.cognito_authorizer,
                x_origin_verify_secret=api_gateway.x_origin_verify_secret,
                open_search_endpoint=base_infrastructure.collection_endpoint,
                open_search_arn=base_infrastructure.collection_arn,
                open_search_index="media",
                vpc=base_infrastructure.vpc.vpc,
            ),
        )

        _ = AssetsConstruct(
            self,
            "ApiGatewayAssets",
            props=AssetsProps(
                asset_table=base_infrastructure.asset_table,
                api_resource=api_gateway.api_resource,
                cognito_authorizer=api_gateway.cognito_authorizer,
                x_origin_verify_secret=api_gateway.x_origin_verify_secret,
            ),
        )

        _ = SettingsConstruct(
            self,
            "ApiSettingsConstruct",
            props=SettingsConstructProps(
                api_resource=api_gateway.api_resource,
                cognito_authorizer=api_gateway.cognito_authorizer,
                cognito_user_pool=self._cognito.user_pool,
                cognito_app_client=self._cognito.user_pool_client,
                x_origin_verify_secret=api_gateway.x_origin_verify_secret,
            ),
        )

        _ = UpdateConstruct(
            self,
            "UpdateConfiguration",
            props=UpdateConstructProps(
                user_pool=self._cognito.user_pool,
                distribution_url=self._ui.distribution_url,
            ),
        )

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

# Optionally, add HIPAA Security checks
# cdk.Aspects.of(app).add(cdk_nag.HIPAASecurityChecks())

# Optionally, add NIST 800-53 rev 5 checks
# cdk.Aspects.of(app).add(cdk_nag.NIST80053R5Checks())

# Optionally, add PCI DSS 3.2.1 checks
# cdk.Aspects.of(app).add(cdk_nag.PCIDSS321Checks())

app.synth()
