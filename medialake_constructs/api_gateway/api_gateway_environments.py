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
class ApiGatewayEnvironmentsProps:
    """Configuration for Environments API Gateway."""

    api_resource: apigateway.IResource
    x_origin_verify_secret: secretsmanager.Secret


class ApiGatewayEnvironmentsConstruct(Construct):
    def __init__(
        self,
        scope: Construct,
        id: str,
        cognito_authorizer: apigateway.IAuthorizer,
        props: ApiGatewayEnvironmentsProps,
    ) -> None:
        super().__init__(scope, id)

        # Create DynamoDB table for environments
        self.environments_table = DynamoDB(
            self,
            "EnvironmentsTable",
            props=DynamoDBProps(
                name=f"{config.global_prefix}-environments",
                partition_key_name="PK",
                partition_key_type=dynamodb.AttributeType.STRING,
                sort_key_name="SK",
                sort_key_type=dynamodb.AttributeType.STRING,
                stream=dynamodb.StreamViewType.NEW_AND_OLD_IMAGES,
                point_in_time_recovery=True,
            ),
        )

        # Create environments resource
        environments_resource = props.api_resource.root.add_resource("environments")

        # GET /environments
        self._get_environments_handler = Lambda(
            self,
            "GetEnvironmentsHandler",
            config=LambdaConfig(
                name="get_environments",
                entry="lambdas/api/environments/get_environments",
                environment_variables={
                    "X_ORIGIN_VERIFY_SECRET_ARN": props.x_origin_verify_secret.secret_arn,
                    "ENVIRONMENTS_TABLE": self.environments_table.table_name,
                    "METRICS_NAMESPACE": config.global_prefix,
                },
            ),
        )

        self._get_environments_handler.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=["dynamodb:GetItem", "dynamodb:Scan"],
                resources=[self.environments_table.table_arn],
            )
        )

        environments_resource.add_method(
            "GET",
            apigateway.LambdaIntegration(self._get_environments_handler.function),
            authorization_type=apigateway.AuthorizationType.COGNITO,
            authorizer=cognito_authorizer,
        )

        # POST /environments
        self._post_environments_handler = Lambda(
            self,
            "PostEnvironmentsHandler",
            config=LambdaConfig(
                name="post_environments",
                entry="lambdas/api/environments/post_environments",
                environment_variables={
                    "X_ORIGIN_VERIFY_SECRET_ARN": props.x_origin_verify_secret.secret_arn,
                    "ENVIRONMENTS_TABLE": self.environments_table.table_name,
                    "METRICS_NAMESPACE": config.global_prefix,
                },
            ),
        )

        self._post_environments_handler.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=["dynamodb:PutItem"],
                resources=[self.environments_table.table_arn],
            )
        )

        environments_resource.add_method(
            "POST",
            apigateway.LambdaIntegration(self._post_environments_handler.function),
            authorization_type=apigateway.AuthorizationType.COGNITO,
            authorizer=cognito_authorizer,
        )

        # Environment ID specific endpoints
        environment_id_resource = environments_resource.add_resource("{id}")

        # PUT /environments/{id}
        self._put_environment_handler = Lambda(
            self,
            "PutEnvironmentHandler",
            config=LambdaConfig(
                name="put_environments",
                entry="lambdas/api/environments/put_environments",
                environment_variables={
                    "X_ORIGIN_VERIFY_SECRET_ARN": props.x_origin_verify_secret.secret_arn,
                    "ENVIRONMENTS_TABLE": self.environments_table.table_name,
                    "METRICS_NAMESPACE": config.global_prefix,
                },
            ),
        )

        self._put_environment_handler.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=["dynamodb:GetItem", "dynamodb:UpdateItem"],
                resources=[self.environments_table.table_arn],
            )
        )

        environment_id_resource.add_method(
            "PUT",
            apigateway.LambdaIntegration(self._put_environment_handler.function),
            authorization_type=apigateway.AuthorizationType.COGNITO,
            authorizer=cognito_authorizer,
        )

        # DELETE /environments/{id}
        self._delete_environment_handler = Lambda(
            self,
            "DeleteEnvironmentHandler",
            config=LambdaConfig(
                name="delete_environments",
                entry="lambdas/api/environments/delete_environments",
                environment_variables={
                    "X_ORIGIN_VERIFY_SECRET_ARN": props.x_origin_verify_secret.secret_arn,
                    "ENVIRONMENTS_TABLE": self.environments_table.table_name,
                    "METRICS_NAMESPACE": config.global_prefix,
                },
            ),
        )

        self._delete_environment_handler.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=["dynamodb:DeleteItem"],
                resources=[self.environments_table.table_arn],
            )
        )

        environment_id_resource.add_method(
            "DELETE",
            apigateway.LambdaIntegration(self._delete_environment_handler.function),
            authorization_type=apigateway.AuthorizationType.COGNITO,
            authorizer=cognito_authorizer,
        )

    @property
    def environments_table_name(self) -> str:
        return self.environments_table.table_name

    @property
    def environments_table_arn(self) -> str:
        return self.environments_table.table_arn

    @property
    def get_environments_handler(self) -> Lambda:
        return self._get_environments_handler

    @property
    def post_environments_handler(self) -> Lambda:
        return self._post_environments_handler

    @property
    def put_environment_handler(self) -> Lambda:
        return self._put_environment_handler

    @property
    def delete_environment_handler(self) -> Lambda:
        return self._delete_environment_handler
