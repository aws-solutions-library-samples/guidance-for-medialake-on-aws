"""
Integrations API Gateway module for MediaLake.

This module defines the ApiGatewayIntegrationsConstruct class which sets up API Gateway endpoints
and a consolidated Lambda function for managing integrations using Lambda Powertools routing.

The module handles:
- Integration CRUD operations
- Secrets Manager integration for API keys
- DynamoDB single-table integration
- IAM roles and permissions
- API Gateway integration with proxy integration
- Lambda function configuration
"""

from dataclasses import dataclass

from aws_cdk import aws_apigateway as apigateway
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_iam as iam
from aws_cdk import aws_secretsmanager as secretsmanager
from constructs import Construct

from config import config
from medialake_constructs.api_gateway.api_gateway_utils import add_cors_options_method
from medialake_constructs.shared_constructs.dynamodb import DynamoDB, DynamoDBProps
from medialake_constructs.shared_constructs.lambda_base import Lambda, LambdaConfig


@dataclass
class ApiGatewayIntegrationsProps:
    """Configuration for integrations API Gateway."""

    api_resource: apigateway.RestApi
    x_origin_verify_secret: secretsmanager.Secret
    authorizer: apigateway.IAuthorizer
    pipelines_nodes_table: dynamodb.TableV2
    environments_table: dynamodb.TableV2


class ApiGatewayIntegrationsConstruct(Construct):
    """
    Integrations API Gateway deployment with single Lambda and routing.
    """

    def __init__(
        self,
        scope: Construct,
        id: str,
        props: ApiGatewayIntegrationsProps,
    ) -> None:
        super().__init__(scope, id)

        # Create DynamoDB table for integrations
        self._integrations_table = DynamoDB(
            self,
            "integrationsTable",
            props=DynamoDBProps(
                name=f"{config.resource_prefix}-integrations-{config.environment}",
                partition_key_name="PK",
                partition_key_type=dynamodb.AttributeType.STRING,
                sort_key_name="SK",
                sort_key_type=dynamodb.AttributeType.STRING,
                point_in_time_recovery=True,
                global_secondary_indexes=[
                    dynamodb.GlobalSecondaryIndexPropsV2(
                        index_name="NodeEnvironmentIndex",
                        partition_key=dynamodb.Attribute(
                            name="Node", type=dynamodb.AttributeType.STRING
                        ),
                        sort_key=dynamodb.Attribute(
                            name="Environment", type=dynamodb.AttributeType.STRING
                        ),
                        projection_type=dynamodb.ProjectionType.ALL,
                    ),
                    dynamodb.GlobalSecondaryIndexPropsV2(
                        index_name="TypeStatusIndex",
                        partition_key=dynamodb.Attribute(
                            name="Type", type=dynamodb.AttributeType.STRING
                        ),
                        sort_key=dynamodb.Attribute(
                            name="Status", type=dynamodb.AttributeType.STRING
                        ),
                        projection_type=dynamodb.ProjectionType.ALL,
                    ),
                ],
            ),
        )

        # Create single consolidated Integrations Lambda with routing
        integrations_lambda = Lambda(
            self,
            "IntegrationsLambda",
            config=LambdaConfig(
                name="integrations_api",
                entry="lambdas/api/integrations_api",
                environment_variables={
                    "X_ORIGIN_VERIFY_SECRET_ARN": props.x_origin_verify_secret.secret_arn,
                    "INTEGRATIONS_TABLE": self._integrations_table.table_name,
                    "PIPELINES_NODES_TABLE": props.pipelines_nodes_table.table_name,
                    "ENVIRONMENTS_TABLE": props.environments_table.table_name,
                    "ENVIRONMENT": config.environment,
                },
            ),
        )

        # Grant DynamoDB permissions
        self._integrations_table.table.grant_read_write_data(
            integrations_lambda.function
        )
        props.pipelines_nodes_table.grant_read_data(integrations_lambda.function)
        props.environments_table.grant_read_data(integrations_lambda.function)

        # Add comprehensive DynamoDB permissions
        integrations_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "dynamodb:GetItem",
                    "dynamodb:PutItem",
                    "dynamodb:UpdateItem",
                    "dynamodb:DeleteItem",
                    "dynamodb:Query",
                    "dynamodb:Scan",
                    "dynamodb:BatchWriteItem",
                ],
                resources=[
                    self._integrations_table.table_arn,
                    f"{self._integrations_table.table_arn}/index/*",
                ],
            )
        )

        # Add Secrets Manager permissions for API key management
        integrations_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "secretsmanager:CreateSecret",
                    "secretsmanager:PutSecretValue",
                    "secretsmanager:UpdateSecret",
                    "secretsmanager:DeleteSecret",
                    "secretsmanager:TagResource",
                ],
                resources=["arn:aws:secretsmanager:*:*:secret:integration/*"],
            )
        )

        # Create Lambda integration
        integrations_integration = apigateway.LambdaIntegration(
            integrations_lambda.function,
            proxy=True,
            allow_test_invoke=True,
        )

        # /integrations resource
        integrations_resource = props.api_resource.root.add_resource("integrations")

        # Add ANY method to /integrations for list and create operations
        integrations_method = integrations_resource.add_method(
            "ANY",
            integrations_integration,
        )
        cfn_method = integrations_method.node.default_child
        cfn_method.authorization_type = "CUSTOM"
        cfn_method.authorizer_id = props.authorizer.authorizer_id

        # /integrations/{id} - Variable path for specific integrations
        integration_id_resource = integrations_resource.add_resource("{id}")

        # Add ANY method to /integrations/{integration_id}
        integration_id_method = integration_id_resource.add_method(
            "ANY",
            integrations_integration,
        )
        cfn_method = integration_id_method.node.default_child
        cfn_method.authorization_type = "CUSTOM"
        cfn_method.authorizer_id = props.authorizer.authorizer_id

        # Add CORS support
        add_cors_options_method(integrations_resource)
        add_cors_options_method(integration_id_resource)

        # Store the Lambda for external access
        self._integrations_lambda = integrations_lambda

    @property
    def integrations_table(self) -> dynamodb.TableV2:
        """
        Get the Integrations DynamoDB table.

        Returns:
            dynamodb.TableV2: The Integrations table
        """
        return self._integrations_table.table

    @property
    def integrations_table_arn(self) -> str:
        """
        Get the Integrations DynamoDB table ARN.

        Returns:
            str: The table ARN
        """
        return self._integrations_table.table_arn

    @property
    def integrations_lambda(self) -> Lambda:
        """
        Get the consolidated Integrations Lambda function.

        Returns:
            Lambda: The Integrations Lambda construct
        """
        return self._integrations_lambda
