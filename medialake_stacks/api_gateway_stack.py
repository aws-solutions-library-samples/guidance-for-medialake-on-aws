from dataclasses import dataclass

import aws_cdk as cdk
from aws_cdk import Duration, Fn
from aws_cdk import aws_apigateway as apigateway
from aws_cdk import aws_cognito as cognito
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_events as events
from aws_cdk import aws_events_targets as targets
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_secretsmanager as secretsmanager
from constructs import Construct

from constants import Lambda as LambdaConstants
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
from medialake_constructs.shared_constructs.lambda_base import Lambda, LambdaConfig
from medialake_constructs.shared_constructs.s3bucket import S3Bucket


@dataclass
class ApiGatewayStackProps:
    """Configuration for API Gateway Stack."""

    asset_table: dynamodb.TableV2
    auth_table_name: str
    avp_policy_store_arn: str
    avp_policy_store_id: str
    cognito_user_pool_id: str
    api_keys_table_name: str
    api_keys_table_arn: str
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
    rest_api_id: str
    x_origin_verify_secret_arn: str
    user_pool: cognito.UserPool
    identity_pool: str
    user_pool_client: str
    waf_acl_arn: str
    cloudfront_domain: str  # CloudFront distribution domain for CORS configuration
    # user_table: dynamodb.TableV2
    s3_vector_bucket_name: str
    ui_origin_host: str | None = None  # Custom domain for UI, if configured


class ApiGatewayStack(cdk.NestedStack):
    def __init__(
        self, scope: Construct, id: str, props: ApiGatewayStackProps, **kwargs
    ):
        super().__init__(scope, id, **kwargs)

        # Store props for later use in property accessors
        self._props = props

        api_id = Fn.import_value("MediaLakeApiGatewayCore-ApiGatewayId")
        root_resource_id = Fn.import_value("MediaLakeApiGatewayCore-RootResourceId")

        # Create the RestApi object once and store it
        self._rest_api = apigateway.RestApi.from_rest_api_attributes(
            self,
            "ApiGatewayImportedApi",
            rest_api_id=api_id,
            root_resource_id=root_resource_id,
        )

        common_env_vars = {
            "AUTH_TABLE_NAME": props.auth_table_name,
            "AVP_POLICY_STORE_ID": props.avp_policy_store_id,
            "COGNITO_USER_POOL_ID": props.cognito_user_pool_id,
            "API_KEYS_TABLE_NAME": props.api_keys_table_name,
            "DEBUG_MODE": "true",
            "NAMESPACE": "MediaLake",
            "TOKEN_TYPE": "identityToken",
        }

        self._authorizer_lambda = Lambda(
            self,
            "SharedCustomAuthorizerLambda",
            config=LambdaConfig(
                name="shared_custom_authorizer",
                entry="lambdas/auth/custom_authorizer",
                memory_size=256,
                timeout_minutes=1,
                snap_start=False,
                environment_variables=common_env_vars,
            ),
        )

        self._authorizer_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "verifiedpermissions:IsAuthorizedWithToken",
                    "verifiedpermissions:IsAuthorized",
                ],
                resources=[props.avp_policy_store_arn],
            )
        )

        self._authorizer_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "dynamodb:GetItem",
                    "dynamodb:Query",
                ],
                resources=[props.api_keys_table_arn],
            )
        )

        self._authorizer_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "secretsmanager:GetSecretValue",
                ],
                resources=[
                    f"arn:aws:secretsmanager:{cdk.Aws.REGION}:{cdk.Aws.ACCOUNT_ID}:secret:medialake/api-keys/*"
                ],
            )
        )

        self._authorizer_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "kms:Decrypt",
                ],
                resources=["*"],  # For AWS managed keys
                conditions={
                    "StringEquals": {
                        "kms:ViaService": f"secretsmanager.{cdk.Aws.REGION}.amazonaws.com"
                    }
                },
            )
        )

        events.Rule(
            self,
            "SharedAuthorizerWarmerRule",
            schedule=events.Schedule.rate(
                Duration.minutes(LambdaConstants.WARMER_INTERVAL_MINUTES)
            ),
            targets=[
                targets.LambdaFunction(
                    self._authorizer_lambda.function,
                    event=events.RuleTargetInput.from_object({"lambda_warmer": True}),
                ),
            ],
            description="Keeps shared custom authorizer Lambda warm via scheduled EventBridge rule.",
        )

        self._authorizer = apigateway.RequestAuthorizer(
            self,
            "SharedRequestAuthorizer",
            handler=self._authorizer_lambda.function,
            identity_sources=[apigateway.IdentitySource.context("requestId")],
            results_cache_ttl=cdk.Duration.seconds(0),
        )

        # Add permission for API Gateway to invoke the authorizer Lambda
        # The source_arn format should be: arn:aws:execute-api:region:account:api-id/authorizers/authorizer-id
        self._authorizer_lambda.function.add_permission(
            "ApiGatewayInvokePermission",
            principal=iam.ServicePrincipal("apigateway.amazonaws.com"),
            action="lambda:InvokeFunction",
            source_arn=f"arn:aws:execute-api:{cdk.Aws.REGION}:{cdk.Aws.ACCOUNT_ID}:{api_id}/authorizers/{self._authorizer.authorizer_id}",
        )

        # Create the Secret object once and store it
        self._x_origin_verify_secret = secretsmanager.Secret.from_secret_name_v2(
            self, "XOriginVerifySecret", props.x_origin_verify_secret_arn
        )

        # Use the stored Secret object in all constructs
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
                api_resource=self._rest_api,
                authorizer=self._authorizer,
                x_origin_verify_secret=self._x_origin_verify_secret,
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
                cloudfront_domain=props.cloudfront_domain,
                ui_origin_host=props.ui_origin_host,
            ),
        )

        # Update the SearchConstruct to include the system settings table
        self._search_construct = SearchConstruct(
            self,
            "SearchApiGateway",
            props=SearchProps(
                asset_table=props.asset_table,
                media_assets_bucket=props.media_assets_bucket,
                api_resource=self._rest_api,
                authorizer=self._authorizer,
                x_origin_verify_secret=self._x_origin_verify_secret,
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
                connector_table=self._connectors_api_gateway.connector_table,
                api_resource=self._rest_api,
                authorizer=self._authorizer,
                x_origin_verify_secret=self._x_origin_verify_secret,
                open_search_endpoint=props.collection_endpoint,
                opensearch_index="media",
                vpc=props.vpc,
                security_group=props.security_group,
                open_search_arn=props.collection_arn,
                system_settings_table=props.system_settings_table,
                media_assets_bucket=props.media_assets_bucket.bucket,
                s3_vector_bucket_name=props.s3_vector_bucket_name,
            ),
        )

        self._nodes_construct = ApiGatewayNodesConstruct(
            self,
            "NodesApiGateway",
            props=ApiGatewayNodesProps(
                api_resource=self._rest_api,
                x_origin_verify_secret=self._x_origin_verify_secret,
                authorizer=self._authorizer,
                pipelines_nodes_table=props.pipelines_nodes_table,
            ),
        )

        # Create health endpoint
        self._create_health_endpoint(
            self._rest_api, self._x_origin_verify_secret, self._authorizer
        )

    def _create_health_endpoint(
        self,
        api: apigateway.RestApi,
        x_origin_verify_secret: secretsmanager.Secret,
        authorizer: apigateway.RequestAuthorizer,
    ) -> None:
        """
        Create the health check endpoint for the API.

        Args:
            api: The API Gateway REST API instance
            x_origin_verify_secret: Secret for origin verification
        """
        # Create health resource
        health_resource = api.root.add_resource("health")

        # Create health Lambda function
        health_lambda = Lambda(
            self,
            "HealthLambda",
            config=LambdaConfig(
                name="health_get",
                entry="lambdas/api/health/get_health",
                memory_size=128,
                timeout_minutes=1,
                environment_variables={
                    "X_ORIGIN_VERIFY_SECRET_ARN": x_origin_verify_secret.secret_arn,
                },
            ),
        )

        # Grant permission to read the secret
        x_origin_verify_secret.grant_read(health_lambda.function)

        # Create GET method for health endpoint
        health_resource.add_method(
            "GET",
            apigateway.LambdaIntegration(health_lambda.function),
            authorizer=authorizer,
        )

        # Store reference to health lambda for external access if needed
        self._health_lambda = health_lambda

    @property
    def rest_api(self) -> apigateway.RestApi:
        # Return from props instead of internal constructs
        return self._rest_api

    @property
    def connector_table(self) -> dynamodb.TableV2:
        return self._connectors_api_gateway.connector_table

    @property
    def x_origin_verify_secret(self) -> secretsmanager.Secret:
        # Return from props instead of internal constructs
        return self._x_origin_verify_secret

    @property
    def connector_sync_lambda(self) -> lambda_.Function:
        return self._connectors_api_gateway.connector_sync_lambda

    @property
    def health_lambda(self) -> lambda_.Function:
        return self._health_lambda.function

    @property
    def authorizer(self) -> apigateway.RequestAuthorizer:
        return self._authorizer

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
