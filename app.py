#!/usr/bin/env python3
"""
This module serves as the entry point for the MediaLake CDK application.
"""
import aws_cdk as cdk
from config import config
from medialake_constructs.cognito import CognitoConstruct, CognitoProps
from medialake_constructs.api_gateway_main_construct import ApiGatewayConstruct
from medialake_constructs.api_gateway_connectors import ConnectorsConstruct
from medialake_constructs.api_gateway_pipelines import PipelinesConstruct
from medialake_constructs.userInterface import UIConstruct, UIConstructProps
from medialake_stacks.base_infrastructure import BaseInfrastructureStack

class MediaLakeStack(cdk.Stack):
    def __init__(self, scope: cdk.App, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        # Create base infrastructure
        base_infrastructure = BaseInfrastructureStack(
            self,
            "BaseInfrastructure",
            env=kwargs.get('env')
        )

        # User auth with Cognito
        self._cognito = CognitoConstruct(
            self,
            "Cognito",
            props=CognitoProps(
                assets_bucket_arn="arn:aws:s3:::mne-mscdemo-testevent"
            ),
        )

        # Create main API Gateway construct
        api_gateway = ApiGatewayConstruct(
            self,
            "ApiGateway",
            user_pool=self._cognito.user_pool,
        )

        # Create connectors construct
        _ = ConnectorsConstruct(
            self,
            "Connectors",
            api_resource=api_gateway.api_resource,
            cognito_authorizer=api_gateway.cognito_authorizer,
            x_origin_verify_secret=api_gateway.x_origin_verify_secret,
            ingest_event_bus=base_infrastructure.ingest_event_bus
        )

        # Create pipelines construct
        _ = PipelinesConstruct(
            self,
            "Pipelines",
            api_resource=api_gateway.api_resource,
            cognito_authorizer=api_gateway.cognito_authorizer,
            x_origin_verify_secret=api_gateway.x_origin_verify_secret,
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

        # Export the User Interface CloudFront URL
        cdk.CfnOutput(
            self,
            "UserInterfaceCloudFrontURL",
            value=self._ui.distribution_url,
            export_name=f"{id}-user-interface-url",
        )

app = cdk.App()

primary_stack = MediaLakeStack(
    app, 
    "MediaLake", 
    env=cdk.Environment(
        region=config.primary_region,
        account=app.account
    )
)

if config.enable_ha and config.secondary_region:
    secondary_stack = MediaLakeStack(
        app, 
        "MediaLakeSecondary", 
        env=cdk.Environment(
            region=config.secondary_region,
            account=app.account
        )
    )

app.synth()
