from aws_cdk import (
    aws_apigateway as apigateway,
    aws_iam as iam,
    aws_secretsmanager as secretsmanager,
    aws_dynamodb as dynamodb,
    aws_s3_deployment as s3deploy,
    Duration,
    aws_s3 as s3,
    aws_events as events,
)
from medialake_constructs.shared_constructs.s3bucket import S3Bucket, S3Config
from aws_cdk import Fn, Stack
from constructs import Construct
from medialake_constructs.shared_constructs.lambda_base import (
    Lambda,
    LambdaConfig,
)
from medialake_constructs.shared_constructs.dynamodb import (
    DynamoDB,
    DynamoDBConfig,
)
import os
import shutil
from medialake_constructs.shared_constructs.lam_deployment import LambdaDeployment
from config import config


class ApiSearchConstruct(Construct):
    def __init__(
        self,
        scope: Construct,
        id: str,
        api_resource: apigateway.IResource,
        cognito_authorizer: apigateway.IAuthorizer,
        x_origin_verify_secret: secretsmanager.Secret,
    ) -> None:
        super().__init__(scope, id)



        # Create connectors resource
        search_resource = api_resource.root.add_resource("search")
        search_get_lambda_config = LambdaConfig(
            name="connectors_get_lambda",
            entry="lambdas/api/search/get_search",
            environment_variables={
                "X_ORIGIN_VERIFY_SECRET_ARN": (x_origin_verify_secret.secret_arn),
            },
        )
        search_get_lambda = Lambda(
            self,
            "ConnectorsGetLambda",
            config=search_get_lambda_config,
        )

        search_resource.add_method(
            "GET",
            apigateway.LambdaIntegration(search_get_lambda.function),
            authorization_type=apigateway.AuthorizationType.COGNITO,
            authorizer=cognito_authorizer,
        )