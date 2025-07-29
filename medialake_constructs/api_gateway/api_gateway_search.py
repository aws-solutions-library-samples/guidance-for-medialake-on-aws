from dataclasses import dataclass
from typing import Optional

from aws_cdk import Stack
from aws_cdk import aws_apigateway as apigateway
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_iam as iam
from aws_cdk import aws_secretsmanager as secretsmanager
from constructs import Construct

from medialake_constructs.api_gateway.api_gateway_utils import add_cors_options_method
from medialake_constructs.shared_constructs.lambda_base import Lambda, LambdaConfig
from medialake_constructs.shared_constructs.lambda_layers import SearchLayer
from medialake_constructs.shared_constructs.s3bucket import S3Bucket


@dataclass
class SearchProps:
    asset_table: dynamodb.TableV2
    media_assets_bucket: S3Bucket
    api_resource: apigateway.IResource
    cognito_authorizer: apigateway.IAuthorizer
    x_origin_verify_secret: secretsmanager.Secret
    open_search_endpoint: str
    open_search_arn: str
    open_search_index: str
    system_settings_table: str
    s3_vector_bucket_name: str
    vpc: Optional[ec2.IVpc] = None
    security_group: Optional[ec2.SecurityGroup] = None


class SearchConstruct(Construct):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        props: SearchProps,
    ) -> None:
        super().__init__(scope, construct_id)

        search_layer = SearchLayer(self, "SearchLayer")

        # Create connectors resource
        search_resource = props.api_resource.root.add_resource("search")
        search_get_lambda = Lambda(
            self,
            "SearchGetLambda",
            config=LambdaConfig(
                name="search_get",
                vpc=props.vpc,
                security_groups=[props.security_group],
                entry="lambdas/api/search/get_search",
                layers=[search_layer.layer],
                memory_size=9000,
                snap_start=True,
                timeout_minutes=10,
                environment_variables={
                    "X_ORIGIN_VERIFY_SECRET_ARN": (
                        props.x_origin_verify_secret.secret_arn
                    ),
                    "OPENSEARCH_ENDPOINT": props.open_search_endpoint,
                    "OPENSEARCH_INDEX": props.open_search_index,
                    "SCOPE": "es",
                    "MEDIA_ASSETS_BUCKET": props.media_assets_bucket.bucket_name,
                    "SYSTEM_SETTINGS_TABLE": props.system_settings_table,
                    "S3_VECTOR_BUCKET_NAME": props.s3_vector_bucket_name,
                    "S3_VECTOR_INDEX_NAME": "media-vectors",
                },
            ),
        )

        search_get_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "ec2:CreateNetworkInterface",
                    "ec2:DescribeNetworkInterfaces",
                    "ec2:DeleteNetworkInterface",
                ],
                resources=["*"],
            )
        )

        # Add OpenSearch read permissions to the Lambda
        search_get_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "es:ESHttpGet",
                    "es:ESHttpPost",
                    "es:ESHttpPut",
                    "es:ESHttpDelete",
                    "es:DescribeElasticsearchDomain",
                    "es:ListDomainNames",
                    "es:ESHttpHead",
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
                    "s3:ListBucket",
                    "kms:Decrypt",
                    "kms:GenerateDataKey",
                ],
                resources=[
                    f"{props.media_assets_bucket.bucket.bucket_arn}/*",
                    f"{props.media_assets_bucket.bucket.bucket_arn}",
                    props.media_assets_bucket.kms_key.key_arn,
                ],
            )
        )

        # Add permissions to access Secrets Manager and the system settings table
        search_get_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "secretsmanager:GetSecretValue",
                    "secretsmanager:DescribeSecret",
                ],
                resources=["*"],
            )
        )

        # Add permissions to access the system settings table
        search_get_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "dynamodb:GetItem",
                    "dynamodb:Query",
                    "dynamodb:Scan",
                ],
                resources=[
                    f"arn:aws:dynamodb:{Stack.of(self).region}:{Stack.of(self).account}:table/{props.system_settings_table}"
                ],
            )
        )

        # Add S3 Vector permissions
        search_get_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "s3vectors:GetVectorBucket",
                    "s3vectors:ListVectorBuckets",
                    "s3vectors:GetIndex",
                    "s3vectors:ListIndexes",
                    "s3vectors:GetVectors",
                    "s3vectors:QueryVectors",
                ],
                resources=[
                    f"arn:aws:s3vectors:{Stack.of(self).region}:{Stack.of(self).account}:bucket/{props.s3_vector_bucket_name}",
                    f"arn:aws:s3vectors:{Stack.of(self).region}:{Stack.of(self).account}:bucket/{props.s3_vector_bucket_name}/*",
                ],
            )
        )

        search_resource.add_method(
            "GET",
            apigateway.LambdaIntegration(search_get_lambda.function),
            authorization_type=apigateway.AuthorizationType.COGNITO,
            authorizer=props.cognito_authorizer,
        )

        # Add CORS support

        # Create fields resource under search
        fields_resource = search_resource.add_resource("fields")

        # Create Lambda for search fields endpoint
        search_fields_lambda = Lambda(
            self,
            "SearchFieldsLambda",
            config=LambdaConfig(
                name="get_search_fields",
                entry="lambdas/api/search/fields/get_fields",
                environment_variables={
                    "X_ORIGIN_VERIFY_SECRET_ARN": (
                        props.x_origin_verify_secret.secret_arn
                    ),
                    "SYSTEM_SETTINGS_TABLE": props.system_settings_table,
                },
            ),
        )

        # Add permissions to access Secrets Manager
        search_fields_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "secretsmanager:GetSecretValue",
                    "secretsmanager:DescribeSecret",
                ],
                resources=["*"],
            )
        )

        # Add permissions to access the system settings table
        search_fields_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "dynamodb:GetItem",
                    "dynamodb:Query",
                    "dynamodb:Scan",
                ],
                resources=[
                    f"arn:aws:dynamodb:{Stack.of(self).region}:{Stack.of(self).account}:table/{props.system_settings_table}"
                ],
            )
        )

        # Add the GET method to the fields resource
        fields_resource.add_method(
            "GET",
            apigateway.LambdaIntegration(search_fields_lambda.function),
            authorization_type=apigateway.AuthorizationType.COGNITO,
            authorizer=props.cognito_authorizer,
        )

        add_cors_options_method(search_resource)
        add_cors_options_method(fields_resource)
