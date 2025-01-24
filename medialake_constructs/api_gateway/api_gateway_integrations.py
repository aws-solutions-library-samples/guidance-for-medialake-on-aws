from dataclasses import dataclass
from aws_cdk import (
    aws_apigateway as apigateway,
    aws_iam as iam,
    aws_dynamodb as dynamodb,
    aws_secretsmanager as secretsmanager,
)
from constructs import Construct
from config import config

from medialake_constructs.shared_constructs.lambda_base import (
    Lambda,
    LambdaConfig,
)
from medialake_constructs.shared_constructs.dynamodb import (
    DynamoDB,
    DynamoDBProps,
)


@dataclass
class ApiGatewayIntegrationsProps:
    """Configuration for integrations API Gateway."""

    api_resource: apigateway.IResource
    x_origin_verify_secret: secretsmanager.Secret
    cognito_authorizer: apigateway.IAuthorizer


class ApiGatewayIntegrationsConstruct(Construct):
    def __init__(
        self,
        scope: Construct,
        id: str,
        props: ApiGatewayIntegrationsProps,
    ) -> None:
        super().__init__(scope, id)

        # Create DynamoDB table for integrations
        self.integrations_table = DynamoDB(
            self,
            "integrationsTable",
            props=DynamoDBProps(
                name=f"{config.resource_prefix}-integrations-{config.environment}",
                partition_key_name="PK",
                partition_key_type=dynamodb.AttributeType.STRING,
                sort_key_name="SK",
                sort_key_type=dynamodb.AttributeType.STRING,
                point_in_time_recovery=True,
            ),
        )

        # Create integrations resource
        integrations_resource = props.api_resource.root.add_resource("integrations")

        # GET /integrations
        self._get_integrations_handler = Lambda(
            self,
            "GetintegrationsHandler",
            config=LambdaConfig(
                name="get_integrations",
                entry="lambdas/api/integrations/get_integrations",
                environment_variables={
                    "X_ORIGIN_VERIFY_SECRET_ARN": props.x_origin_verify_secret.secret_arn,
                    "integrations_TABLE": self.integrations_table.table_name,
                    "METRICS_NAMESPACE": config.global_prefix,
                },
            ),
        )

        self._get_integrations_handler.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=["dynamodb:GetItem", "dynamodb:Scan"],
                resources=[self.integrations_table.table_arn],
            )
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
                name="post_integrations",
                entry="lambdas/api/integrations/post_integrations",
                environment_variables={
                    "X_ORIGIN_VERIFY_SECRET_ARN": props.x_origin_verify_secret.secret_arn,
                    "INTEGRATIONS_TABLE": self.integrations_table.table_name,
                },
            ),
        )

        self._post_integrations_handler.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=["dynamodb:PutItem"],
                resources=[self.integrations_table.table_arn],
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
                name="put_integrations",
                entry="lambdas/api/integrations/put_integrations",
                environment_variables={
                    "X_ORIGIN_VERIFY_SECRET_ARN": props.x_origin_verify_secret.secret_arn,
                    "INTEGRATIONS_TABLE": self.integrations_table.table_name,
                },
            ),
        )

        self._put_integration_handler.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=["dynamodb:GetItem", "dynamodb:UpdateItem"],
                resources=[self.integrations_table.table_arn],
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
            "DeleteintegrationHandler",
            config=LambdaConfig(
                name="delete_integrations",
                entry="lambdas/api/integrations/del_integrations",
                environment_variables={
                    "X_ORIGIN_VERIFY_SECRET_ARN": props.x_origin_verify_secret.secret_arn,
                    "INTEGRATIONS_TABLE": self.integrations_table.table_name,
                },
            ),
        )

        self._delete_integration_handler.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=["dynamodb:DeleteItem"],
                resources=[self.integrations_table.table_arn],
            )
        )

        integration_id_resource.add_method(
            "DELETE",
            apigateway.LambdaIntegration(self._delete_integration_handler.function),
            authorization_type=apigateway.AuthorizationType.COGNITO,
            authorizer=props.cognito_authorizer,
        )

    @property
    def integrations_table_name(self) -> str:
        return self.integrations_table.table_name

    @property
    def integrations_table_arn(self) -> str:
        return self.integrations_table.table_arn

    @property
    def get_integrations_handler(self) -> Lambda:
        return self._get_integrations_handler

    @property
    def post_integrations_handler(self) -> Lambda:
        return self._post_integrations_handler

    @property
    def put_integration_handler(self) -> Lambda:
        return self._put_integration_handler

    @property
    def delete_integration_handler(self) -> Lambda:
        return self._delete_integration_handler
