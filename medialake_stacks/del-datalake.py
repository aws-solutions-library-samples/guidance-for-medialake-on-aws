from aws_cdk import (
    Stack,
    CfnOutput,
    aws_iam as iam,
)

from constructs import Construct

from medialake_constructs.cognito import CognitoConstruct, CognitoProps
from medialake_constructs.api_gateway_main_construct import (
    ApiGatewayConstruct,
)
from medialake_constructs.api_gateway_connectors import (
    ConnectorsConstruct,
)
from medialake_constructs.api_gateway_pipelines import PipelinesConstruct
from medialake_constructs.userInterface import UIConstruct, UIConstructProps
from medialake_stacks.base_infrastructure import BaseInfrastructureStack

class DataLake(Stack):

    def __init__(self, scope: Construct, construct_id: str, base_infrastructure: BaseInfrastructureStack, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        self.base_infrastructure = base_infrastructure

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

        # # Create Lambda execution role
        # lambda_execution_role = iam.Role(
        #     self,
        #     "LambdaExecutionRole",
        #     assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
        # )

        # # Add necessary permissions to Lambda role
        # lambda_execution_role.add_to_principal_policy(
        #     iam.PolicyStatement(
        #         effect=iam.Effect.ALLOW,
        #         actions=["s3:ListAllMyBuckets"],
        #         resources=["*"],
        #     )
        # )


        # Create connectors construct
        _ = ConnectorsConstruct(
            self,
            "Connectors",
            api_resource=api_gateway.api_resource,
            cognito_authorizer=api_gateway.cognito_authorizer,
            x_origin_verify_secret=api_gateway.x_origin_verify_secret,
            ingest_event_bus=self.base_infrastructure.ingest_event_bus
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
        CfnOutput(
            self,
            "UserInterfaceCloudFrontURL",
            value=self._ui.distribution_url,
            export_name=f"{construct_id}-user-interface-url",
        )
