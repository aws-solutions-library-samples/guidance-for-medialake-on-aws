"""
Assets API Stack for MediaLake.

Hosts the (large) Assets API surface in its OWN top-level CloudFormation
template, peeled out of the monolithic ApiGatewayStack to keep every template
well under the 500-resource CloudFormation limit.

It imports the shared REST API by ID (so its API Gateway resources/methods are
emitted into this template) and reuses the shared request authorizer created in
the API Gateway stack. It creates no stateful resources of its own — all
DynamoDB tables/buckets are passed in by reference, so nothing is reprovisioned
when this stack is created/migrated.
"""

from dataclasses import dataclass
from typing import Optional

import aws_cdk as cdk
from aws_cdk import aws_apigateway as apigateway
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_events as events
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_secretsmanager as secretsmanager
from constructs import Construct

from medialake_constructs.api_gateway.api_gateway_assets import (
    AssetsConstruct,
    AssetsProps,
)


@dataclass
class AssetsApiStackProps:
    """Configuration for the Assets API Stack."""

    # Data tier (owned elsewhere; passed by reference, never moved)
    asset_table: dynamodb.ITable
    connector_table: dynamodb.ITable
    upload_directives_table: dynamodb.ITable
    asset_events_bus: events.IEventBus
    media_assets_bucket: s3.IBucket
    # Shared API tier
    authorizer: apigateway.IAuthorizer
    rest_api_id: str
    root_resource_id: str
    x_origin_verify_secret_arn: str
    # Search / vectors
    open_search_endpoint: str
    open_search_arn: str
    system_settings_table: str
    s3_vector_bucket_name: str
    # Networking
    vpc: ec2.IVpc
    security_group: ec2.ISecurityGroup
    # Optional
    personal_assets_bucket: Optional[s3.IBucket] = None
    video_download_enabled: bool = True


class AssetsApiStack(cdk.Stack):
    """Top-level stack hosting the Assets API surface."""

    def __init__(self, scope: Construct, id: str, props: AssetsApiStackProps, **kwargs):
        super().__init__(scope, id, **kwargs)

        # Import the shared REST API by ID so the assets resources/methods land
        # in THIS template, and build the X-Origin secret reference locally.
        api = apigateway.RestApi.from_rest_api_attributes(
            self,
            "AssetsImportedApi",
            rest_api_id=props.rest_api_id,
            root_resource_id=props.root_resource_id,
        )
        x_origin_verify_secret = secretsmanager.Secret.from_secret_name_v2(
            self,
            "AssetsXOriginSecret",
            props.x_origin_verify_secret_arn,
        )

        self._assets_construct = AssetsConstruct(
            self,
            "AssetsApiGateway",
            props=AssetsProps(
                asset_table=props.asset_table,
                connector_table=props.connector_table,
                api_resource=api,
                authorizer=props.authorizer,
                x_origin_verify_secret=x_origin_verify_secret,
                open_search_endpoint=props.open_search_endpoint,
                opensearch_index="media",
                open_search_arn=props.open_search_arn,
                system_settings_table=props.system_settings_table,
                asset_events_bus=props.asset_events_bus,
                s3_vector_bucket_name=props.s3_vector_bucket_name,
                upload_directives_table=props.upload_directives_table,
                vpc=props.vpc,
                security_group=props.security_group,
                media_assets_bucket=props.media_assets_bucket,
                personal_assets_bucket=props.personal_assets_bucket,
                video_download_enabled=props.video_download_enabled,
            ),
        )

    @property
    def assets_construct(self) -> AssetsConstruct:
        return self._assets_construct
