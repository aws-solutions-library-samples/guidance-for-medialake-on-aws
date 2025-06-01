import secrets
import string
import aws_cdk as cdk

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
    Fn
)
from constructs import Construct
from dataclasses import dataclass

from medialake_constructs.api_gateway.api_gateway_integrations import (
    ApiGatewayIntegrationsConstruct,
    ApiGatewayIntegrationsProps,
)

from medialake_constructs.api_gateway.api_gateway_environments import (
    ApiGatewayEnvironmentsConstruct,
    ApiGatewayEnvironmentsProps,
)

from medialake_constructs.shared_constructs.default_environment import DefaultEnvironment, DefaultEnvironmentProps
from medialake_constructs.shared_constructs.lambda_base import LambdaConfig


@dataclass
class IntegrationsEnvironmentStackProps:
    """Configuration for Integrations Environment Stack."""
    
    # API Gateway resources
    api_resource: apigateway.RestApi
    x_origin_verify_secret: secretsmanager.Secret
    cognito_user_pool: cognito.UserPool
    pipelines_nodes_table: dynamodb.TableV2
    post_pipelines_lambda: lambda_.Function


class IntegrationsEnvironmentStack(cdk.NestedStack):
    def __init__(
        self, scope: Construct, id: str, props: IntegrationsEnvironmentStackProps, **kwargs
    ):
        super().__init__(scope, id, **kwargs)
        
        # Store props for later use in property accessors
        self._props = props


        # Import the API Gateway Core components
        api_id = Fn.import_value("MediaLakeApiGatewayCore-ApiGatewayId")
        root_resource_id = Fn.import_value("MediaLakeApiGatewayCore-RootResourceId")
        
        api = apigateway.RestApi.from_rest_api_attributes(self, "IntegrationsApiGateway",
            rest_api_id=api_id,
            root_resource_id=root_resource_id
        )
        
        self._api_authorizer = apigateway.CognitoUserPoolsAuthorizer(
            self, 
            "IntegrationsApiAuthorizer",
            identity_source="method.request.header.Authorization",
            cognito_user_pools=[props.cognito_user_pool],
        )


        # Create Integrations API Gateway construct
        self._integrations_stack = ApiGatewayIntegrationsConstruct(
            self,
            "Integrations",
            props=ApiGatewayIntegrationsProps(
                api_resource=api.root,
                x_origin_verify_secret=props.x_origin_verify_secret,
                cognito_authorizer=self._api_authorizer,
                pipelines_nodes_table=props.pipelines_nodes_table,
            ),
        )
        
        # Create Environments API Gateway construct
        self._environments_api = ApiGatewayEnvironmentsConstruct(
            self,
            "EnvironmentsApiGateway",
            props=ApiGatewayEnvironmentsProps(
                api_resource=api.root,
                cognito_authorizer=self._api_authorizer,
                x_origin_verify_secret=props.x_origin_verify_secret,
                integrations_table=self._integrations_stack.integrations_table,
                post_integrations_handler=self._integrations_stack.post_integrations_handler,
            ),
        )
        
        # Create default environment custom resource
        _ = DefaultEnvironment(
            self,
            "DefaultEnvironment",
            props=DefaultEnvironmentProps(
                environments_table=self._environments_api.environments_table.table,
            ),
        )

        self._props.post_pipelines_lambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=["dynamodb:GetItem", "dynamodb:Query"],
                resources=[self._integrations_stack.integrations_table.table_arn],
            )
        )
        
        self._props.post_pipelines_lambda.add_environment(
            "INTEGRATIONS_TABLE",
            self._integrations_stack.integrations_table.table_arn,
        )
        
    @property
    def integrations_table(self) -> dynamodb.TableV2:
        return self._integrations_stack.integrations_table
    
    @property
    def post_integrations_handler(self) -> lambda_.Function:
        return self._integrations_stack.post_integrations_handler
    
    @property
    def environments_table(self) -> dynamodb.TableV2:
        return self._environments_api.environments_table
    
    @property
    def integrations_construct(self) -> ApiGatewayIntegrationsConstruct:
        return self._integrations_stack
    
    @property
    def environments_construct(self) -> ApiGatewayEnvironmentsConstruct:
        return self._environments_api 