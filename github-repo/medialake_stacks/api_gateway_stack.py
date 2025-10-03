from dataclasses import dataclass

import aws_cdk as cdk
from aws_cdk import Fn
from aws_cdk import aws_apigateway as apigateway
from aws_cdk import aws_cognito as cognito
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_events as events
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_secretsmanager as secretsmanager
from constructs import Construct

from medialake_constructs.api_gateway.api_gateway_assets import (
    AssetsConstruct,
    AssetsProps,
)
from medialake_constructs.api_gateway.api_gateway_connectors import (
    ConnectorsConstruct,
    ConnectorsProps,
)
from medialake_constructs.api_gateway.api_gateway_nodes import (
    ApiGatewayNodesConstruct,
    ApiGatewayNodesProps,
)
from medialake_constructs.api_gateway.api_gateway_search import (
    SearchConstruct,
    SearchProps,
)
from medialake_constructs.shared_constructs.s3bucket import S3Bucket


@dataclass
class ApiGatewayStackProps:
    """Configuration for API Gateway Stack."""

    asset_table: dynamodb.TableV2
    iac_assets_bucket: s3.Bucket
    media_assets_bucket: S3Bucket
    external_payload_bucket: s3.Bucket
    pipelines_nodes_templates_bucket: s3.Bucket
    asset_table_file_hash_index_arn: str
    asset_table_asset_id_index_arn: str
    asset_table_s3_path_index_arn: str
    pipelines_event_bus: events.EventBus
    vpc: ec2.Vpc
    security_group: ec2.SecurityGroup
    collection_endpoint: str
    collection_arn: str
    access_log_bucket: s3.Bucket
    pipeline_table: dynamodb.TableV2
    pipelines_nodes_table: dynamodb.TableV2
    node_table: dynamodb.TableV2
    asset_sync_job_table: dynamodb.TableV2
    asset_sync_engine_lambda: lambda_.Function
    system_settings_table: str
    rest_api: apigateway.RestApi
    x_origin_verify_secret: secretsmanager.Secret
    user_pool: cognito.UserPool
    identity_pool: str
    user_pool_client: str
    waf_acl_arn: str
    user_table: dynamodb.TableV2
    s3_vector_bucket_name: str


class ApiGatewayStack(cdk.NestedStack):
    def __init__(
        self, scope: Construct, id: str, props: ApiGatewayStackProps, **kwargs
    ):
        super().__init__(scope, id, **kwargs)

        # Store props for later use in property accessors
        self._props = props

        api_id = Fn.import_value("MediaLakeApiGatewayCore-ApiGatewayId")
        root_resource_id = Fn.import_value("MediaLakeApiGatewayCore-RootResourceId")

        api = apigateway.RestApi.from_rest_api_attributes(
            self,
            "ApiGatewayImportedApi",
            rest_api_id=api_id,
            root_resource_id=root_resource_id,
        )

        self._api_gateway_authorizer = apigateway.CognitoUserPoolsAuthorizer(
            self,
            "ApiGatewayAuthorizer",
            identity_source="method.request.header.Authorization",
            cognito_user_pools=[props.user_pool],
        )

        self._connectors_api_gateway = ConnectorsConstruct(
            self,
            "ConnectorsApiGateway",
            props=ConnectorsProps(
                asset_table=props.asset_table,
                asset_table_file_hash_index_arn=props.asset_table_file_hash_index_arn,
                asset_table_asset_id_index_arn=props.asset_table_asset_id_index_arn,
                asset_table_s3_path_index_arn=props.asset_table_s3_path_index_arn,
                iac_assets_bucket=props.iac_assets_bucket,
                media_assets_bucket=props.media_assets_bucket,  # Added for cross-bucket deletion
                api_resource=api,
                cognito_authorizer=self._api_gateway_authorizer,
                x_origin_verify_secret=props.x_origin_verify_secret,
                pipelines_event_bus=props.pipelines_event_bus.event_bus_name,
                asset_sync_job_table=props.asset_sync_job_table,
                asset_sync_engine_lambda=props.asset_sync_engine_lambda,
                open_search_endpoint=props.collection_endpoint,
                opensearch_index="media",
                vpc_subnet_ids=",".join(
                    [subnet.subnet_id for subnet in props.vpc.private_subnets]
                ),
                security_group_id=props.security_group.security_group_id,
                system_settings_table_name=props.system_settings_table,
                system_settings_table_arn=f"arn:aws:dynamodb:{self.region}:{self.account}:table/{props.system_settings_table}",
                s3_vector_bucket_name=props.s3_vector_bucket_name,
            ),
        )

        # Update the SearchConstruct to include the system settings table
        self._search_construct = SearchConstruct(
            self,
            "SearchApiGateway",
            props=SearchProps(
                asset_table=props.asset_table,
                media_assets_bucket=props.media_assets_bucket,
                api_resource=api,
                cognito_authorizer=self._api_gateway_authorizer,
                x_origin_verify_secret=props.x_origin_verify_secret,
                open_search_endpoint=props.collection_endpoint,
                open_search_arn=props.collection_arn,
                open_search_index="media",
                vpc=props.vpc,
                security_group=props.security_group,
                system_settings_table=props.system_settings_table,
                s3_vector_bucket_name=props.s3_vector_bucket_name,
            ),
        )

        self._assets_construct = AssetsConstruct(
            self,
            "AssetsApiGateway",
            props=AssetsProps(
                asset_table=props.asset_table,
                api_resource=api,
                cognito_authorizer=self._api_gateway_authorizer,
                x_origin_verify_secret=props.x_origin_verify_secret,
                open_search_endpoint=props.collection_endpoint,
                opensearch_index="media",
                vpc=props.vpc,
                security_group=props.security_group,
                open_search_arn=props.collection_arn,
                user_table=props.user_table,
                s3_vector_bucket_name=props.s3_vector_bucket_name,
            ),
        )

        self._nodes_construct = ApiGatewayNodesConstruct(
            self,
            "NodesApiGateway",
            props=ApiGatewayNodesProps(
                api_resource=api,
                x_origin_verify_secret=props.x_origin_verify_secret,
                cognito_authorizer=self._api_gateway_authorizer,
                pipelines_nodes_table=props.pipelines_nodes_table,
            ),
        )

        # Create a list of dependencies for the deployment
        # These are the resources that the API Gateway deployment needs to wait for
        deployment_dependencies = [
            self._connectors_api_gateway,
            self._search_construct,
            self._assets_construct,
            self._nodes_construct,
        ]

    @property
    def rest_api(self) -> apigateway.RestApi:
        # Return from props instead of internal constructs
        return self._props.rest_api

    @property
    def connector_table(self) -> dynamodb.TableV2:
        return self._connectors_api_gateway.connector_table

    @property
    def x_origin_verify_secret(self) -> secretsmanager.Secret:
        # Return from props instead of internal constructs
        return self._props.x_origin_verify_secret

    @property
    def connector_sync_lambda(self) -> lambda_.Function:
        return self._connectors_api_gateway.connector_sync_lambda

    @property
    def api_resources(self):
        """Return a list of all important API resources for dependency tracking"""
        resources = []

        # Add all resources that were created
        # This is a simplified version - you may need to add more resources
        if hasattr(self, "_asset_lambda_integration"):
            resources.append(self._asset_lambda_integration)
        if hasattr(self, "_pipeline_lambda_integration"):
            resources.append(self._pipeline_lambda_integration)
        if hasattr(self, "_connector_lambda_integration"):
            resources.append(self._connector_lambda_integration)

        # Add any other important API resources here

        return resources

    # Paused dev - still on roadmap
    # def get_functions(self) -> list[lambda_.Function]:
    #     """Return all Lambda functions in this stack that need warming."""
    #     return [
    # self._pipeline_construct.post_pipelines_handler.function,
    # self._pipeline_construct.get_pipelines_handler.function,
    # self._pipeline_construct.get_pipeline_id_handler.function,
    # self._pipeline_construct.put_pipeline_id_handler.function,
    # self._pipeline_construct.del_pipeline_id_handler.function,
    # self._pipeline_construct.pipeline_trigger_lambda.function,
    # ]
