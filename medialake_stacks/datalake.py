from aws_cdk import (
    Stack,
    RemovalPolicy,
    CfnOutput,
)

from constructs import Construct

from medialake_constructs.cognito import CognitoConstruct, CognitoProps

from medialake_constructs.apiGateway import ApiGatewayConstruct, ApiGatewayProps

from medialake_constructs.userInterface import UIConstruct, UIConstructProps


class DataLake(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # # User auth with Cognito
        self._cognito = CognitoConstruct(
            self,
            "Cognito",
            props=CognitoProps(assets_bucket_arn="arn:aws:s3:::mne-mscdemo-testevent"),
        )

        # # APIGateway
        self._rest_api = ApiGatewayConstruct(
            self,
            "ApiGateway",
            self._cognito.user_pool,
            ApiGatewayProps(collection_endpoint="seendpoint"),
        )

        self._ui = UIConstruct(
            self,
            "UserInterface",
            self._rest_api.rest_api_id,
            self._cognito.user_pool,
            self._cognito.user_pool_client,
            self._cognito.identity_pool,
            props=UIConstructProps(),
        )

        # Export the User Interface CloudFront URL
        CfnOutput(
            self,
            "UserInterfaceCloudFrontURL",
            value=self._ui.distribution_url,
            export_name=f"{construct_id}-user-interface-url",
        )
