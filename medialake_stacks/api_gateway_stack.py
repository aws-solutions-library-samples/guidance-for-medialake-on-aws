from aws_cdk import (
    Stack,
    aws_cognito as cognito,
    aws_iam as iam,
    aws_dynamodb as dynamodb,
    aws_s3 as s3,
    aws_ec2 as ec2,
    aws_lambda as lambda_,
    aws_events as events,
    aws_apigateway as apigateway,
)
from constructs import Construct
from dataclasses import dataclass
from medialake_constructs.api_gateway.api_gateway_main_construct import (
    ApiGatewayConstruct,
    ApiGatewayProps,
)

from medialake_constructs.api_gateway.api_gateway_pipelines import (
    ApiGatewayPipelinesConstruct,
    ApiGatewayPipelinesProps,
)

from config import config
from medialake_constructs.cognito import CognitoConstruct, CognitoProps
from medialake_constructs.api_gateway.api_gateway_main_construct import (
    ApiGatewayConstruct,
)
from medialake_constructs.api_gateway.api_gateway_connectors import (
    ConnectorsConstruct,
    ConnectorsProps,
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
from medialake_stacks.pipelines_executions_stack import (
    PipelinesExecutionsStack,
    PipelinesExecutionsStackProps,
)
from medialake_constructs.userInterface import UIConstruct, UIConstructProps


@dataclass
class ApiGatewayStackProps:
    """Configuration for API Gateway Stack."""

    asset_table: dynamodb.Table
    iac_assets_bucket: s3.Bucket
    media_assets_bucket: s3.Bucket
    asset_table_file_hash_index_arn: str
    asset_table_asset_id_index_arn: str
    ingest_event_bus: events.EventBus
    vpc: ec2.Vpc
    security_group: ec2.SecurityGroup
    collection_endpoint: str
    collection_arn: str
    access_log_bucket: s3.Bucket
    pipeline_table: dynamodb.TableV2
    image_metadata_extractor_lambda: lambda_.Function
    image_proxy_lambda: lambda_.Function
    # api_gateway_endpoint: ec2.IInterfaceVpcEndpoint
    # cloudfront_vpc_endpoint: ec2.IVpcEndpoint
    # vpc_endpoint: ec2.IVpcEndpoint


class ApiGatewayStack(Stack):
    def __init__(
        self, scope: Construct, id: str, props: ApiGatewayStackProps, **kwargs
    ):
        super().__init__(scope, id, **kwargs)

        self._cognito_construct = CognitoConstruct(
            self,
            "Cognito",
            props=CognitoProps(),
        )

        # Create main API Gateway construct using provided user pool
        self._api_gateway = ApiGatewayConstruct(
            self,
            "ApiGateway",
            props=ApiGatewayProps(
                user_pool=self._cognito_construct.user_pool,
                access_log_bucket=props.access_log_bucket,
                # api_gateway_endpoint=props.api_gateway_endpoint,
                # cloudfront_vpc_endpoint=props.cloudfront_vpc_endpoint,
                # vpc_endpoint=props.vpc_endpoint,
            ),
        )

        self._connectors_api_gateway = ConnectorsConstruct(
            self,
            "ConnectorsApiGateway",
            props=ConnectorsProps(
                asset_table=props.asset_table,
                asset_table_file_hash_index_arn=props.asset_table_file_hash_index_arn,
                asset_table_asset_id_index_arn=props.asset_table_asset_id_index_arn,
                iac_assets_bucket=props.iac_assets_bucket,
                api_resource=self._api_gateway.rest_api,
                cognito_authorizer=self._api_gateway.cognito_authorizer,
                x_origin_verify_secret=self._api_gateway.x_origin_verify_secret,
                ingest_event_bus=props.ingest_event_bus,
            ),
        )

        self._pipelines_executions_stack = PipelinesExecutionsStack(
            self,
            "PipelinesExecutions",
            props=PipelinesExecutionsStackProps(
                x_origin_verify_secret=self._api_gateway.x_origin_verify_secret,
            ),
        )

        _ = ApiGatewayPipelinesConstruct(
            self,
            "Pipelines",
            api_resource=self._api_gateway.rest_api,
            cognito_authorizer=self._api_gateway.cognito_authorizer,
            ingest_event_bus=props.ingest_event_bus,
            x_origin_verify_secret=self._api_gateway.x_origin_verify_secret,
            iac_assets_bucket=props.iac_assets_bucket,
            media_assets_bucket=props.media_assets_bucket,
            props=ApiGatewayPipelinesProps(
                asset_table=props.asset_table,
                connector_table=self._connectors_api_gateway.connector_table,
                pipeline_table=props.pipeline_table,
                image_proxy_lambda=props.image_proxy_lambda,
                image_metadata_extractor_lambda=props.image_metadata_extractor_lambda,
                iac_assets_bucket=props.iac_assets_bucket,
                get_pipelines_executions_lambda=self._pipelines_executions_stack.get_pipelines_executions_lambda,
                post_retry_pipelines_executions_lambda=self._pipelines_executions_stack.post_retry_pipelines_executions_lambda,
            ),
        )

        _ = SearchConstruct(
            self,
            "SearchApiGateway",
            props=SearchProps(
                asset_table=props.asset_table,
                media_assets_bucket=props.media_assets_bucket,
                api_resource=self._api_gateway.rest_api,
                cognito_authorizer=self._api_gateway.cognito_authorizer,
                x_origin_verify_secret=self._api_gateway.x_origin_verify_secret,
                open_search_endpoint=props.collection_endpoint,
                open_search_arn=props.collection_arn,
                open_search_index="media",
                vpc=props.vpc,
                security_group=props.security_group,
            ),
        )

        _ = AssetsConstruct(
            self,
            "AssetsApiGateway",
            props=AssetsProps(
                asset_table=props.asset_table,
                api_resource=self._api_gateway.rest_api,
                cognito_authorizer=self._api_gateway.cognito_authorizer,
                x_origin_verify_secret=self._api_gateway.x_origin_verify_secret,
            ),
        )

        _ = SettingsConstruct(
            self,
            "SettingsApiGateway",
            props=SettingsConstructProps(
                api_resource=self._api_gateway.rest_api,
                cognito_authorizer=self._api_gateway.cognito_authorizer,
                cognito_user_pool=self._cognito_construct.user_pool,
                cognito_app_client=self._cognito_construct.user_pool_client,
                x_origin_verify_secret=self._api_gateway.x_origin_verify_secret,
            ),
        )

        self._ui = UIConstruct(
            self,
            "UserInterface",
            props=UIConstructProps(
                cognito_user_pool_id=self._cognito_construct.user_pool_id,
                cognito_user_pool_client_id=self._cognito_construct.user_pool_client,
                cognito_identity_pool=self._cognito_construct.identity_pool,
                api_gateway_rest_id=self._api_gateway.rest_api.rest_api_id,
                access_log_bucket=props.access_log_bucket,
            ),
        )

    @property
    def rest_api(self) -> apigateway.RestApi:
        return self._api_gateway.rest_api

    @property
    def connector_table(self) -> dynamodb.TableV2:
        return self._connectors_api_gateway.connector_table
