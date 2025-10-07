from dataclasses import dataclass

import aws_cdk as cdk
from aws_cdk import aws_apigateway as apigateway
from aws_cdk import aws_cognito as cognito
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_secretsmanager as secretsmanager
from constructs import Construct

from medialake_constructs.api_gateway.api_gateway_collections import (
    CollectionsApi,
    CollectionsApiProps,
)
from medialake_constructs.shared_constructs.s3bucket import S3Bucket


@dataclass
class CollectionsStackProps:
    """Configuration for Collections API Stack."""

    cognito_user_pool: cognito.UserPool
    authorizer: apigateway.IAuthorizer
    api_resource: apigateway.RestApi
    x_origin_verify_secret: secretsmanager.Secret
    collection_endpoint: str
    collection_arn: str
    opensearch_index: str
    vpc: ec2.IVpc
    security_group: ec2.SecurityGroup
    media_assets_bucket: S3Bucket


class CollectionsStack(cdk.NestedStack):
    """
    Stack for Collections API and management.

    This stack creates the Collections API endpoints and all related resources including:
    - Collection types management
    - Collections CRUD operations with hierarchical relationships
    - Collection items management with batch operations
    - Collection rules for automatic item assignment
    - Collection sharing and permissions management
    - Single-table DynamoDB design for optimal performance

    The stack follows MediaLake patterns and integrates with the existing
    authorization and API Gateway infrastructure.
    """

    def __init__(
        self, scope: Construct, id: str, props: CollectionsStackProps, **kwargs
    ):
        super().__init__(scope, id, **kwargs)

        # Create Collections API construct
        self._collections_api = CollectionsApi(
            self,
            "CollectionsApiGateway",
            props=CollectionsApiProps(
                api_resource=props.api_resource,
                authorizer=props.authorizer,
                x_origin_verify_secret=props.x_origin_verify_secret,
                open_search_endpoint=props.collection_endpoint,
                open_search_arn=props.collection_arn,
                opensearch_index=props.opensearch_index,
                vpc=props.vpc,
                security_group=props.security_group,
                media_assets_bucket=props.media_assets_bucket,
            ),
        )

    @property
    def collections_api(self):
        """
        Return the Collections API construct.

        Returns:
            CollectionsApi: The Collections API Gateway construct containing
                all endpoint definitions and Lambda functions
        """
        return self._collections_api

    @property
    def collections_table(self):
        """
        Return the Collections DynamoDB table.

        Returns:
            aws_dynamodb.Table: The single Collections table containing
                all collection-related data with optimized GSI structure
        """
        return self._collections_api.collections_table.table
