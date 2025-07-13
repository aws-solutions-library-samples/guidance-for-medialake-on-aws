from dataclasses import dataclass

from aws_cdk import aws_apigateway as apigateway
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_secretsmanager as secretsmanager
from constructs import Construct

from config import config
from medialake_constructs.api_gateway.api_gateway_utils import add_cors_options_method
from medialake_constructs.shared_constructs.dynamodb import DynamoDB, DynamoDBProps
from medialake_constructs.shared_constructs.lambda_base import Lambda, LambdaConfig


@dataclass
class ApiGatewayIntegrationsProps:
    """Configuration for integrations API Gateway."""

    api_resource: apigateway.IResource
    x_origin_verify_secret: secretsmanager.Secret
    cognito_authorizer: apigateway.IAuthorizer
    pipelines_nodes_table: dynamodb.TableV2


class ApiGatewayIntegrationsConstruct(Construct):
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

        # Create integrations resource
        integrations_resource = props.api_resource.add_resource("integrations")

        # GET /integrations
        self._get_integrations_handler = Lambda(
            self,
            "GetintegrationsHandler",
            config=LambdaConfig(
                name=f"{config.resource_prefix}_get_integrations_{config.environment}",
                entry="lambdas/api/integrations/get_integrations",
                environment_variables={
                    "X_ORIGIN_VERIFY_SECRET_ARN": props.x_origin_verify_secret.secret_arn,
                    "INTEGRATIONS_TABLE": self._integrations_table.table_name,
                    "PIPELINES_NODES_TABLE": props.pipelines_nodes_table.table_name,
                },
            ),
        )
        self._integrations_table.table.grant_read_data(
            self._get_integrations_handler.function
        )

        integrations_resource.add_method(
            "GET",
            apigateway.LambdaIntegration(self._get_integrations_handler.function),
            authorization_type=apigateway.AuthorizationType.COGNITO,
            authorizer=props.cognito_authorizer,
        )

        # POST /integrations
        self._post_integrations_handler = Lambda(
            self,
            "PostintegrationsHandler",
            config=LambdaConfig(
                name=f"{config.resource_prefix}_post_integrations_{config.environment}",
                entry="lambdas/api/integrations/post_integrations",
                environment_variables={
                    "X_ORIGIN_VERIFY_SECRET_ARN": props.x_origin_verify_secret.secret_arn,
                    "INTEGRATIONS_TABLE": self._integrations_table.table_name,
                },
            ),
        )

        self._post_integrations_handler.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=["dynamodb:PutItem"],
                resources=[self._integrations_table.table_arn],
            )
        )

        # Add Secrets Manager permissions
        self._post_integrations_handler.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "secretsmanager:CreateSecret",
                    "secretsmanager:PutSecretValue",
                    "secretsmanager:TagResource",
                ],
                resources=["arn:aws:secretsmanager:*"],
            )
        )

        integrations_resource.add_method(
            "POST",
            apigateway.LambdaIntegration(self._post_integrations_handler.function),
            authorization_type=apigateway.AuthorizationType.COGNITO,
            authorizer=props.cognito_authorizer,
        )

        # integration ID specific endpoints
        integration_id_resource = integrations_resource.add_resource("{id}")

        # PUT /integrations/{id}
        self._put_integration_handler = Lambda(
            self,
            "PutintegrationHandler",
            config=LambdaConfig(
                name=f"{config.resource_prefix}_put_integrationsId_{config.environment}",
                entry="lambdas/api/integrations/rp_integrationsId/put_integrationsId",
                environment_variables={
                    "X_ORIGIN_VERIFY_SECRET_ARN": props.x_origin_verify_secret.secret_arn,
                    "INTEGRATIONS_TABLE": self._integrations_table.table_name,
                },
            ),
        )

        self._integrations_table.table.grant_write_data(
            self._put_integration_handler.function
        )

        # Add specific DynamoDB permissions for query and update operations
        self._put_integration_handler.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=["dynamodb:GetItem", "dynamodb:UpdateItem", "dynamodb:Query"],
                resources=[self._integrations_table.table_arn],
            )
        )

        # Add Secrets Manager permissions for updating API key secrets
        self._put_integration_handler.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "secretsmanager:CreateSecret",
                    "secretsmanager:PutSecretValue",
                    "secretsmanager:UpdateSecret",
                ],
                resources=["arn:aws:secretsmanager:*:*:secret:integration/*"],
            )
        )

        integration_id_resource.add_method(
            "PUT",
            apigateway.LambdaIntegration(self._put_integration_handler.function),
            authorization_type=apigateway.AuthorizationType.COGNITO,
            authorizer=props.cognito_authorizer,
        )

        # DELETE /integrations/{id}
        self._delete_integration_handler = Lambda(
            self,
            "DeleteIntegrationsHandler",
            config=LambdaConfig(
                name=f"{config.resource_prefix}_del_integrationsId_{config.environment}",
                entry="lambdas/api/integrations/rp_integrationsId/del_integrationsId",
                environment_variables={
                    "X_ORIGIN_VERIFY_SECRET_ARN": props.x_origin_verify_secret.secret_arn,
                    "INTEGRATIONS_TABLE": self._integrations_table.table_name,
                },
            ),
        )

        self._integrations_table.table.grant_write_data(
            self._delete_integration_handler.function
        )

        # Add specific DynamoDB permissions for batch operations
        self._delete_integration_handler.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "dynamodb:DeleteItem",
                    "dynamodb:BatchWriteItem",
                    "dynamodb:Query",
                ],
                resources=[self._integrations_table.table_arn],
            )
        )

        # Add Secrets Manager permissions for deleting API key secrets
        self._delete_integration_handler.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=["secretsmanager:DeleteSecret"],
                resources=["arn:aws:secretsmanager:*:*:secret:integration/*"],
            )
        )

        integration_id_resource.add_method(
            "DELETE",
            apigateway.LambdaIntegration(self._delete_integration_handler.function),
            authorization_type=apigateway.AuthorizationType.COGNITO,
            authorizer=props.cognito_authorizer,
        )

        # Add CORS support
        add_cors_options_method(integrations_resource)
        add_cors_options_method(integration_id_resource)

    @property
    def integrations_table(self) -> dynamodb.TableV2:
        return self._integrations_table.table

    @property
    def integrations_table_arn(self) -> str:
        return self._integrations_table.table_arn

    @property
    def get_integrations_handler(self) -> Lambda:
        return self._get_integrations_handler

    @property
    def post_integrations_handler(self) -> lambda_.Function:
        return self._post_integrations_handler.function

    @property
    def put_integration_handler(self) -> Lambda:
        return self._put_integration_handler.function

    @property
    def delete_integration_handler(self) -> Lambda:
        return self._delete_integration_handler.function
