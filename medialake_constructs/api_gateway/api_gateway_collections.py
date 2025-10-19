"""
Collections API Gateway module for MediaLake.

This module defines the CollectionsApi class which sets up API Gateway endpoints
and a consolidated Lambda function for managing collections using Lambda Powertools routing.

The module handles:
- Collection types and metadata management
- Collection item management with batch operations
- Collection rules for automatic item assignment
- Collection sharing and permissions
- DynamoDB single-table integration
- IAM roles and permissions
- API Gateway integration with proxy integration
- Lambda function configuration
"""

from dataclasses import dataclass

from aws_cdk import Stack
from aws_cdk import aws_apigateway as api_gateway
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_iam as iam
from aws_cdk import aws_secretsmanager as secrets_manager
from constructs import Construct

from medialake_constructs.api_gateway.api_gateway_utils import add_cors_options_method
from medialake_constructs.shared_constructs.dynamodb import DynamoDB, DynamoDBProps
from medialake_constructs.shared_constructs.lambda_base import Lambda, LambdaConfig
from medialake_constructs.shared_constructs.s3bucket import S3Bucket


@dataclass
class CollectionsApiProps:
    x_origin_verify_secret: secrets_manager.Secret
    api_resource: api_gateway.RestApi
    authorizer: api_gateway.IAuthorizer
    open_search_endpoint: str
    open_search_arn: str
    opensearch_index: str
    vpc: ec2.IVpc
    security_group: ec2.SecurityGroup
    media_assets_bucket: S3Bucket


class CollectionsApi(Construct):
    """
    Collections API Gateway deployment with single Lambda and routing
    """

    def __init__(
        self,
        scope: Construct,
        constructor_id: str,
        props: CollectionsApiProps,
    ) -> None:
        super().__init__(scope, constructor_id)

        from config import config

        # Get the current account ID
        Stack.of(self).account

        # Create single Collections table with GSIs following the schema design
        gsi_list = [
            # GSI1: UserCollectionsGSI - Find all collections a user has access to
            dynamodb.GlobalSecondaryIndexPropsV2(
                index_name="UserCollectionsGSI",
                partition_key=dynamodb.Attribute(
                    name="GSI1_PK", type=dynamodb.AttributeType.STRING
                ),
                sort_key=dynamodb.Attribute(
                    name="GSI1_SK", type=dynamodb.AttributeType.STRING
                ),
                projection_type=dynamodb.ProjectionType.ALL,
            ),
            # GSI2: ItemCollectionsGSI - Find all collections containing a specific item
            dynamodb.GlobalSecondaryIndexPropsV2(
                index_name="ItemCollectionsGSI",
                partition_key=dynamodb.Attribute(
                    name="GSI2_PK", type=dynamodb.AttributeType.STRING
                ),
                sort_key=dynamodb.Attribute(
                    name="GSI2_SK", type=dynamodb.AttributeType.STRING
                ),
                projection_type=dynamodb.ProjectionType.ALL,
            ),
            # GSI3: CollectionTypeGSI - Find collections by type
            dynamodb.GlobalSecondaryIndexPropsV2(
                index_name="CollectionTypeGSI",
                partition_key=dynamodb.Attribute(
                    name="GSI3_PK", type=dynamodb.AttributeType.STRING
                ),
                sort_key=dynamodb.Attribute(
                    name="GSI3_SK", type=dynamodb.AttributeType.STRING
                ),
                projection_type=dynamodb.ProjectionType.ALL,
            ),
            # GSI4: ParentChildGSI - Find all parent collections of a child collection
            dynamodb.GlobalSecondaryIndexPropsV2(
                index_name="ParentChildGSI",
                partition_key=dynamodb.Attribute(
                    name="GSI4_PK", type=dynamodb.AttributeType.STRING
                ),
                sort_key=dynamodb.Attribute(
                    name="GSI4_SK", type=dynamodb.AttributeType.STRING
                ),
                projection_type=dynamodb.ProjectionType.ALL,
            ),
            # GSI5: RecentlyModifiedGSI - Find recently modified collections system-wide
            dynamodb.GlobalSecondaryIndexPropsV2(
                index_name="RecentlyModifiedGSI",
                partition_key=dynamodb.Attribute(
                    name="GSI5_PK", type=dynamodb.AttributeType.STRING
                ),
                sort_key=dynamodb.Attribute(
                    name="GSI5_SK", type=dynamodb.AttributeType.STRING
                ),
                projection_type=dynamodb.ProjectionType.ALL,
            ),
        ]

        self._collections_table = DynamoDB(
            self,
            "CollectionsTable",
            props=DynamoDBProps(
                name=f"{config.resource_prefix}_collections_{config.environment}",
                partition_key_name="PK",
                partition_key_type=dynamodb.AttributeType.STRING,
                sort_key_name="SK",
                sort_key_type=dynamodb.AttributeType.STRING,
                global_secondary_indexes=gsi_list,
                ttl_attribute="expiresAt",
            ),
        )

        # Get environment for SSM parameter path
        from config import config

        # Create single consolidated Collections Lambda with routing
        # High-traffic API with VPC access needs higher memory + provisioned concurrency
        collections_lambda = Lambda(
            self,
            "CollectionsLambda",
            config=LambdaConfig(
                name="collections_api",
                entry="lambdas/api/collections_api",
                vpc=props.vpc,
                security_groups=[props.security_group],
                environment_variables={
                    "X_ORIGIN_VERIFY_SECRET_ARN": props.x_origin_verify_secret.secret_arn,
                    "COLLECTIONS_TABLE_NAME": self._collections_table.table_name,
                    "COLLECTIONS_TABLE_ARN": self._collections_table.table_arn,
                    "OPENSEARCH_ENDPOINT": props.open_search_endpoint,
                    "OPENSEARCH_INDEX": props.opensearch_index,
                    "SCOPE": "es",
                    "ENVIRONMENT": config.environment,
                },
            ),
        )

        # Grant DynamoDB permissions
        self._collections_table.table.grant_read_write_data(collections_lambda.function)

        # Grant VPC network interface permissions for Lambda in VPC
        collections_lambda.function.add_to_role_policy(
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
        collections_lambda.function.add_to_role_policy(
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

        # Add S3 and KMS permissions for generating CloudFront URLs
        collections_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "s3:GetObject",
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

        # Add SSM GetParameter permissions for CloudFront domain retrieval
        collections_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["ssm:GetParameter"],
                resources=[
                    f"arn:aws:ssm:{Stack.of(self).region}:{Stack.of(self).account}:parameter/medialake/*"
                ],
            )
        )

        # Create Lambda integration
        collections_integration = api_gateway.LambdaIntegration(
            collections_lambda.function,
            proxy=True,
            allow_test_invoke=True,
        )

        # /collection-types resource
        collection_types_resource = props.api_resource.root.add_resource(
            "collection-types"
        )

        collection_types_method = collection_types_resource.add_method(
            "ANY",
            collections_integration,
        )
        cfn_method = collection_types_method.node.default_child
        cfn_method.authorization_type = "CUSTOM"
        cfn_method.authorizer_id = props.authorizer.authorizer_id

        # /collections resource
        collections_resource = props.api_resource.root.add_resource("collections")

        # Add ANY method to /collections for list and create operations
        collections_method = collections_resource.add_method(
            "ANY",
            collections_integration,
        )
        cfn_method = collections_method.node.default_child
        cfn_method.authorization_type = "CUSTOM"
        cfn_method.authorizer_id = props.authorizer.authorizer_id

        # /collections/shared-with-me (static route must come before variable route)
        shared_with_me_resource = collections_resource.add_resource("shared-with-me")
        shared_with_me_method = shared_with_me_resource.add_method(
            "ANY",
            collections_integration,
        )
        cfn_method = shared_with_me_method.node.default_child
        cfn_method.authorization_type = "CUSTOM"
        cfn_method.authorizer_id = props.authorizer.authorizer_id

        # /collections/{collectionId} - Variable path for specific collections
        collection_id_resource = collections_resource.add_resource("{collectionId}")

        # Add ANY method to /collections/{collectionId}
        collection_id_method = collection_id_resource.add_method(
            "ANY",
            collections_integration,
        )
        cfn_method = collection_id_method.node.default_child
        cfn_method.authorization_type = "CUSTOM"
        cfn_method.authorizer_id = props.authorizer.authorizer_id

        # /collections/{collectionId}/{proxy+} - Catch all sub-resources
        collection_proxy_resource = collection_id_resource.add_resource("{proxy+}")

        collection_proxy_method = collection_proxy_resource.add_method(
            "ANY",
            collections_integration,
        )
        cfn_method = collection_proxy_method.node.default_child
        cfn_method.authorization_type = "CUSTOM"
        cfn_method.authorizer_id = props.authorizer.authorizer_id

        # Add CORS support to all resources
        add_cors_options_method(collection_types_resource)
        add_cors_options_method(collections_resource)
        add_cors_options_method(shared_with_me_resource)
        add_cors_options_method(collection_id_resource)
        add_cors_options_method(collection_proxy_resource)

    @property
    def collections_table(self) -> DynamoDB:
        """
        Get the Collections DynamoDB table construct.

        Returns:
            DynamoDB: The Collections table construct
        """
        return self._collections_table
