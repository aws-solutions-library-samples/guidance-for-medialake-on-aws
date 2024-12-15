from aws_cdk import (
    Stack,
    aws_cognito as cognito,
    aws_iam as iam,
    aws_dynamodb as dynamodb,
    aws_s3 as s3,
    aws_events as events,
)
from constructs import Construct
from dataclasses import dataclass
from medialake_constructs.api_gateway.api_gateway_main_construct import (
    ApiGatewayConstruct,
)

from medialake_constructs.api_gateway.api_gateway_pipelines import (
    ApiGatewayPipelinesConstruct,
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
    """Configuration for Lambda function creation."""

    cognit_user_pool: cognito.UserPool
    iac_assets_bucket: s3.Bucket
    media_assets_bucket: s3.Bucket
    asset_table_file_hash_index_arn: str
    asset_table_asset_id_index_arn: str
    resource_table: dynamodb.Table
    ingest_event_bus: events.EventBus


class ApiGatewayStack(Stack):
    def __init__(
        self, scope: Construct, id: str, props: ApiGatewayStackProps, **kwargs
    ):
        super().__init__(scope, id, **kwargs)

        # Create main API Gateway construct using provided user pool
        self.api_gateway = ApiGatewayConstruct(
            self,
            "ApiGateway",
            user_pool=props.cognit_user_pool,
        )

        self._pipelines_executions_stack = PipelinesExecutionsStack(
            self,
            "PipelinesExecutions",
            props=PipelinesExecutionsStackProps(
                x_origin_verify_secret=self.api_gateway.x_origin_verify_secret,
            ),
        )

        # connectors = ConnectorsConstruct(
        #     self,
        #     "Connectors",
        #     props=ConnectorsProps(
        #         asset_table=props.asset_table,
        #         asset_table_file_hash_index_arn=props.asset_table_file_hash_index_arn,
        #         asset_table_asset_id_index_arn=props.asset_table_asset_id_index_arn,
        #         iac_assets_bucket=props.iac_assets_bucket,
        #         resource_table=props.resource_table,
        #         api_resource=self.api_gateway.rest_api,
        #         cognito_authorizer=self.api_gateway.cognito_authorizer,
        #         x_origin_verify_secret=self.api_gateway.x_origin_verify_secret,
        #         ingest_event_bus=props.ingest_event_bus,
        #     ),
        # )

        # pipelines = ApiGatewayPipelinesConstruct(
        #     self,
        #     "Pipelines",
        #     api_resource=self.api_gateway.rest_api,
        #     cognito_authorizer=self.api_gateway.cognito_authorizer,
        #     ingest_event_bus=props.ingest_event_bus,
        #     x_origin_verify_secret=self.api_gateway.x_origin_verify_secret,
        #     iac_assets_bucket=props.iac_assets_bucket,
        #     media_assets_bucket=props.media_assets_bucket,
        #     props=ApiGatewayPipelinesProps(
        #         asset_table=props.asset_table,
        #         iac_assets_bucket=props.iac_assets_bucket,
        #         get_pipelines_executions_lambda=self._pipelines_executions_stack.get_pipelines_executions_lambda,
        #         post_retry_pipelines_executions_lambda=self._pipelines_executions_stack.post_retry_pipelines_executions_lambda,
        #     ),
        # )

        # search = SearchConstruct(
        #     self,
        #     "Search",
        #     props=SearchProps(
        #         asset_table=props.asset_table,
        #         api_resource=self.api_gateway.rest_api,
        #         cognito_authorizer=self.api_gateway.cognito_authorizer,
        #         x_origin_verify_secret=self.api_gateway.x_origin_verify_secret,
        #         open_search_endpoint=props.collection_endpoint,
        #         open_search_arn=props.collection_arn,
        #         open_search_index="media",
        #         vpc=props.vpc,
        #         security_group=props.security_group,
        #     ),
        # )

        # assets = AssetsConstruct(
        #     self,
        #     "ApiGatewayAssets",
        #     props=AssetsProps(
        #         asset_table=props.asset_table,
        #         api_resource=self.api_gateway.rest_api,
        #         cognito_authorizer=self.api_gateway.cognito_authorizer,
        #         x_origin_verify_secret=self.api_gateway.x_origin_verify_secret,
        #     ),
        # )

        # settings = SettingsConstruct(
        #     self,
        #     "ApiSettingsConstruct",
        #     props=SettingsConstructProps(
        #         api_resource=self.api_gateway.rest_api,
        #         cognito_authorizer=self.api_gateway.cognito_authorizer,
        #         cognito_user_pool=self._cognito.user_pool,
        #         cognito_app_client=self._cognito.user_pool_client,
        #         x_origin_verify_secret=self.api_gateway.x_origin_verify_secret,
        #     ),
        # )

        # update_config = UpdateConstruct(
        #     self,
        #     "UpdateConfiguration",
        #     props=UpdateConstructProps(
        #         user_pool=self._cognito.user_pool,
        #         distribution_url=self._ui.distribution_url,
        #     ),
        # )
