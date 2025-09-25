from dataclasses import dataclass

from aws_cdk import aws_apigateway as apigateway
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_secretsmanager as secretsmanager
from constructs import Construct

from config import config
from medialake_constructs.api_gateway.api_gateway_utils import add_cors_options_method
from medialake_constructs.shared_constructs.lambda_base import Lambda, LambdaConfig


@dataclass
class ApiGatewayNodesProps:
    """Configuration for nodes API Gateway."""

    api_resource: apigateway.IResource
    x_origin_verify_secret: secretsmanager.Secret
    cognito_authorizer: apigateway.IAuthorizer
    pipelines_nodes_table: dynamodb.TableV2


class ApiGatewayNodesConstruct(Construct):
    def __init__(
        self,
        scope: Construct,
        id: str,
        props: ApiGatewayNodesProps,
    ) -> None:
        super().__init__(scope, id)

        # Create nodes resource
        nodes_resource = props.api_resource.root.add_resource("nodes")

        # Create the Lambda handler first
        self._get_nodeId_handler = Lambda(
            self,
            "GetNodeIdHandler",
            config=LambdaConfig(
                name=f"{config.resource_prefix}-get_nodeId-{config.environment}",
                entry="lambdas/api/nodes/rp_nodeId/get_nodeId",
                environment_variables={
                    "X_ORIGIN_VERIFY_SECRET_ARN": props.x_origin_verify_secret.secret_arn,
                    "PIPELINES_NODES_TABLE": props.pipelines_nodes_table.table_name,
                },
            ),
        )

        props.pipelines_nodes_table.grant_read_data(self._get_nodeId_handler.function)

        # GET /nodes/methods/unconfigured
        root_methods_resource = nodes_resource.add_resource("methods")
        unconfigured_resource = root_methods_resource.add_resource("unconfigured")

        unconfigured_resource.add_method(
            "GET",
            apigateway.LambdaIntegration(self._get_nodeId_handler.function),
            authorization_type=apigateway.AuthorizationType.COGNITO,
            authorizer=props.cognito_authorizer,
        )

        # GET /nodes
        self._get_nodes_handler = Lambda(
            self,
            "GetnodesHandler",
            config=LambdaConfig(
                name="get_nodes",
                entry="lambdas/api/nodes/get_nodes",
                environment_variables={
                    "X_ORIGIN_VERIFY_SECRET_ARN": props.x_origin_verify_secret.secret_arn,
                    "PIPELINES_NODES_TABLE": props.pipelines_nodes_table.table_name,
                },
            ),
        )

        props.pipelines_nodes_table.grant_read_data(self._get_nodes_handler.function)

        nodes_resource.add_method(
            "GET",
            apigateway.LambdaIntegration(self._get_nodes_handler.function),
            authorization_type=apigateway.AuthorizationType.COGNITO,
            authorizer=props.cognito_authorizer,
        )

        # integration ID specific endpoints
        node_id_resource = nodes_resource.add_resource("{id}")

        # GET /nodes/{id}

        node_id_resource.add_method(
            "GET",
            apigateway.LambdaIntegration(self._get_nodeId_handler.function),
            authorization_type=apigateway.AuthorizationType.COGNITO,
            authorizer=props.cognito_authorizer,
        )

        # GET /nodes/{id}/methods
        node_methods_resource = node_id_resource.add_resource("methods")
        node_methods_resource.add_method(
            "GET",
            apigateway.LambdaIntegration(self._get_nodeId_handler.function),
            authorization_type=apigateway.AuthorizationType.COGNITO,
            authorizer=props.cognito_authorizer,
        )

        # Add CORS support
        add_cors_options_method(nodes_resource)
        add_cors_options_method(root_methods_resource)
        add_cors_options_method(unconfigured_resource)
        add_cors_options_method(node_id_resource)
        add_cors_options_method(node_methods_resource)
