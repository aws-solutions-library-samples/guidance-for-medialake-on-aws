from aws_cdk import (
    aws_apigateway as apigateway,
    aws_lambda as _lambda,
    aws_logs as logs,
    aws_iam as iam,
    aws_dynamodb as ddb,
    aws_secretsmanager as secretsmanager,
    Duration,
    RemovalPolicy,
    SecretValue,
)
from dataclasses import dataclass
from constructs import Construct
from typing import Optional


class ConnectorsConstruct(Construct):
    def __init__(
        self,
        scope: Construct,
        id: str,
        api_resource: apigateway.IResource,
        cognito_authorizer: apigateway.IAuthorizer,
        lambda_execution_role: iam.Role,
        x_origin_verify_secret: secretsmanager.Secret,
    ) -> None:
        super().__init__(scope, id)

        # Create connectors resource
        connectors_resource = api_resource.root.add_resource("connectors")

        # Create s3list resource and Lambda function
        s3list_resource = connectors_resource.add_resource("s3list")
        s3list_handler = _lambda.Function(
            self,
            "S3ListHandler",
            # ...
            role=lambda_execution_role,
            environment={
                "X_ORIGIN_VERIFY_SECRET_ARN": x_origin_verify_secret.secret_arn,
            },
        )
        s3list_resource.add_method(
            "GET",
            apigateway.LambdaIntegration(s3list_handler),
            authorization_type=apigateway.AuthorizationType.COGNITO,
            authorizer=cognito_authorizer,
        )

        # Create s3connector resource and Lambda function
        s3connector_resource = connectors_resource.add_resource("s3connector")
        s3connector_handler = _lambda.Function(
            self,
            "S3ConnectorHandler",
            # ...
            role=lambda_execution_role,
            environment={
                "X_ORIGIN_VERIFY_SECRET_ARN": x_origin_verify_secret.secret_arn,
            },
        )
        s3connector_resource.add_method(
            "POST",
            apigateway.LambdaIntegration(s3connector_handler),
            authorization_type=apigateway.AuthorizationType.COGNITO,
            authorizer=cognito_authorizer,
        )
