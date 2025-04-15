import secrets
import string

from aws_cdk import (
    Stack,
    aws_dynamodb as dynamodb,
    aws_s3 as s3,
    aws_ec2 as ec2,
    aws_lambda as lambda_,
    aws_events as events,
    aws_secretsmanager as secretsmanager,
    aws_apigateway as apigateway,
    aws_iam as iam,
    aws_cognito as cognito,
    aws_stepfunctions as sfn,
    custom_resources as cr,
    aws_wafv2 as wafv2,
    RemovalPolicy,
    Fn
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

from medialake_stacks.pipelines_executions_stack import (
    PipelinesExecutionsStack,
    PipelinesExecutionsStackProps,
)

from medialake_constructs.api_gateway.api_gateway_nodes import (
    ApiGatewayNodesConstruct,
    ApiGatewayNodesProps,
)

from medialake_constructs.api_gateway.api_gateway_deployment_construct import (
    ApiGatewayDeploymentConstruct,
ApiGatewayDeploymentProps,
)

from medialake_constructs.shared_constructs.s3bucket import S3Bucket


@dataclass
class ApiGatewayStackProps:
    """Configuration for API Gateway Stack."""

    # Base infrastructure resources
    asset_table: dynamodb.TableV2
    iac_assets_bucket: s3.Bucket
    media_assets_bucket: S3Bucket
    external_payload_bucket: s3.Bucket
    pipelines_nodes_templates_bucket: s3.Bucket
    asset_table_file_hash_index_arn: str
    asset_table_asset_id_index_arn: str
    asset_table_s3_path_index_arn: str
    ingest_event_bus: events.EventBus
    vpc: ec2.Vpc
    security_group: ec2.SecurityGroup
    collection_endpoint: str
    collection_arn: str
    access_log_bucket: s3.Bucket
    pipeline_table: dynamodb.TableV2
    image_metadata_extractor_lambda: lambda_.Function
    image_proxy_lambda: lambda_.Function
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


class ApiGatewayStack(Stack):
    def __init__(
        self, scope: Construct, id: str, props: ApiGatewayStackProps, **kwargs
    ):
        super().__init__(scope, id, **kwargs)
        

        # Store props for later use in property accessors
        self._props = props



        api_id = Fn.import_value("MediaLakeApiGatewayCore-ApiGatewayId")
        root_resource_id = Fn.import_value("MediaLakeApiGatewayCore-RootResourceId")
        
        api = apigateway.RestApi.from_rest_api_attributes(self, "ApiGatewayImportedApi",
            rest_api_id=api_id,
            root_resource_id=root_resource_id
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
                api_resource=api,
                cognito_authorizer=self._api_gateway_authorizer,
                x_origin_verify_secret=props.x_origin_verify_secret,
                ingest_event_bus=props.ingest_event_bus,
                asset_sync_job_table=props.asset_sync_job_table,
                asset_sync_engine_lambda=props.asset_sync_engine_lambda,
            ),
        )
        
        self._pipelines_executions_stack = PipelinesExecutionsStack(
            self,
            "PipelinesExecutions",
            props=PipelinesExecutionsStackProps(
                x_origin_verify_secret=props.x_origin_verify_secret,
            ),
        )

        self._pipeline_stack = ApiGatewayPipelinesConstruct(
            self,
            "Pipelines",
            api_resource=api,
            cognito_authorizer=self._api_gateway_authorizer,
            ingest_event_bus=props.ingest_event_bus,
            x_origin_verify_secret=props.x_origin_verify_secret,
            iac_assets_bucket=props.iac_assets_bucket,
            media_assets_bucket=props.media_assets_bucket,
            props=ApiGatewayPipelinesProps(
                asset_table=props.asset_table,
                connector_table=self._connectors_api_gateway.connector_table,
                node_table=props.node_table,
                pipeline_table=props.pipeline_table,
                image_proxy_lambda=props.image_proxy_lambda,
                image_metadata_extractor_lambda=props.image_metadata_extractor_lambda,
                iac_assets_bucket=props.iac_assets_bucket,
                external_payload_bucket=props.external_payload_bucket,
                pipelines_nodes_templates_bucket=props.pipelines_nodes_templates_bucket,
                get_pipelines_executions_lambda=self._pipelines_executions_stack.get_pipelines_executions_lambda,
                post_retry_pipelines_executions_lambda=self._pipelines_executions_stack.post_retry_pipelines_executions_lambda,
                open_search_endpoint=props.collection_endpoint,
                vpc=props.vpc,
                security_group=props.security_group
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
            self._pipeline_stack,
            self._search_construct,
            self._assets_construct,
            self._nodes_construct
        ]
        
        # Create a separate deployment for the API
        # This ensures all resources are created before deploying the API
        self._api_deployment = ApiGatewayDeploymentConstruct(
            self,
            "ApiDeployment",
            props=ApiGatewayDeploymentProps(
                rest_api=api,
                waf_acl_arn=props.waf_acl_arn,
                dependencies=deployment_dependencies,
            )
        )

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

    # @property
    # def cognito_authorizer(self) -> apigateway.CognitoUserPoolsAuthorizer:
    #     # Return from props instead of internal constructs
    #     return self._props.cognito_authorizer

    @property
    def pipelines_create_handler(self) -> lambda_.Function:
        return self._pipeline_stack.pipelines_create_handler
    
    @property
    def connector_sync_lambda(self) -> lambda_.Function:
        return self._connectors_api_gateway.connector_sync_lambda
    
    @property
    def user_pool_arn(self) -> str:
        # No longer accessing from cognito_construct
        return self._props.user_pool.user_pool_arn
    
    @property
    def identity_pool(self) -> str:
        # This will need to be provided from props
        return self._props.identity_pool
    
    @property
    def user_pool_client(self) -> str:
        # This will need to be provided from props
        return self._props.user_pool_client
    
    @property
    def user_pool_id(self) -> str:
        # No longer accessing from cognito_construct
        return self._props.user_pool.user_pool_id
        
    @property
    def deployment_stage(self) -> apigateway.Stage:
        return self._api_deployment.stage
        
    def get_functions(self) -> list[lambda_.Function]:
        """Return all Lambda functions in this stack that need warming."""
        return [
            # self._pipeline_stack.post_pipelines_handler.function,
            # self._pipeline_stack.get_pipelines_handler.function,
            # self._pipeline_stack.get_pipeline_id_handler.function,
            # self._pipeline_stack.put_pipeline_id_handler.function,
            # self._pipeline_stack.del_pipeline_id_handler.function,
            # self._pipeline_stack.pipeline_trigger_lambda.function,
        ]
