from dataclasses import dataclass
from aws_cdk import (
    aws_apigateway as apigateway,
    aws_secretsmanager as secretsmanager,
    aws_dynamodb as dynamodb,
    Duration,
    aws_iam as iam,
)
from aws_cdk import Fn, Stack
from constructs import Construct
from medialake_constructs.shared_constructs.lambda_base import (
    Lambda,
    LambdaConfig,
)
from config import config
from medialake_constructs.shared_constructs.lambda_layers import SearchLayer


@dataclass
class AssetsProps:
    asset_table: dynamodb.TableV2
    api_resource: apigateway.IResource
    cognito_authorizer: apigateway.IAuthorizer
    x_origin_verify_secret: secretsmanager.Secret
    open_search_endpoint: str
    open_search_arn: str
    open_search_index: str


class AssetsConstruct(Construct):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        props: AssetsProps,
    ) -> None:
        super().__init__(scope, construct_id)

        search_layer = SearchLayer(self, "SearchLayer")

        # Create connectors resource
        search_resource = props.api_resource.root.add_resource("assets")
        search_get_lambda = Lambda(
            self,
            "SearchGetLambda",
            config=LambdaConfig(
                name="search_get_lambda",
                entry="lambdas/api/search/get_search",
                layers=[search_layer.layer],
                environment_variables={
                    "X_ORIGIN_VERIFY_SECRET_ARN": (
                        props.x_origin_verify_secret.secret_arn
                    ),
                    "OPENSEARCH_ENDPOINT": props.open_search_endpoint,
                    "OPENSEARCH_INDEX": props.open_search_index,
                },
            ),
        )

        # Add OpenSearch read permissions to the Lambda
        search_get_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "aoss:ReadDocument",
                    "aoss:SearchDocument",
                    "aoss:BatchGetDocument",
                    "aoss:APIAccessAll",
                    "aoss:DescribeIndex",
                    "aoss:ListIndices",
                ],
                resources=[props.open_search_arn, f"{props.open_search_arn}/*"],
            )
        )

        # Add S3 and KMS permissions for generating presigned URLs
        search_get_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "s3:GetObject",
                    "s3:PutObject",
                    "s3:GetObjectVersion",
                    "s3:GetBucketLocation",
                    "kms:Decrypt",
                    "kms:GenerateDataKey",
                ],
                resources=[
                    "arn:aws:s3:::medialake-asset-bucket-*/*",
                    "arn:aws:s3:::medialake-asset-bucket-*",
                    "arn:aws:kms:*:*:key/*",
                ],
            )
        )

        search_resource.add_method(
            "GET",
            apigateway.LambdaIntegration(search_get_lambda.function),
            authorization_type=apigateway.AuthorizationType.COGNITO,
            authorizer=props.cognito_authorizer,
        )
