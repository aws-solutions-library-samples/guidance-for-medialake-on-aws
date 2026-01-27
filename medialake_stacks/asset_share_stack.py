"""
Asset Share Stack

This stack creates infrastructure for sharing assets as direct CloudFront URLs.

Features:
- Simple DynamoDB table to track shared assets
- No viewer page - just direct pre-signed URLs
- Share endpoint: POST /api/assets/{id}/share
- Unshare endpoint: DELETE /api/assets/{id}/share
- Automatic expiration tracking with TTL
"""

from dataclasses import dataclass

import aws_cdk as cdk
from aws_cdk import RemovalPolicy, aws_dynamodb as dynamodb
from constructs import Construct

from config import config
from medialake_constructs.shared_constructs.dynamodb import (
    DynamoDB as DynamoDBConstruct,
)
from medialake_constructs.shared_constructs.dynamodb import DynamoDBProps


@dataclass
class AssetShareStackProps:
    """Configuration for Asset Share Stack."""

    pass


class AssetShareStack(cdk.NestedStack):
    """
    Stack for Asset Sharing functionality.

    Creates a DynamoDB table to track shared assets with direct CloudFront URLs.

    Table Schema:
        Partition Key: AssetID (string)
        Attributes:
            - ShareToken: UUID token for tracking
            - ShareURL: Pre-signed CloudFront URL
            - RepresentationType: "proxy" or "original"
            - CreatedBy: User ID who shared
            - CreatedAt: Timestamp
            - ExpiresAt: TTL attribute for auto-cleanup
            - Status: "shared" or "unshared"
    """

    def __init__(
        self, scope: Construct, id: str, props: AssetShareStackProps, **kwargs
    ):
        super().__init__(scope, id, **kwargs)

        # Create Asset Shares Table
        # Simple table with ShareToken as partition key for tracking shared assets
        asset_shares_table_props = DynamoDBProps(
            name=f"{config.resource_prefix}-asset-shares-table-{config.environment}",
            partition_key_name="ShareToken",
            partition_key_type=dynamodb.AttributeType.STRING,
            point_in_time_recovery=True,
            removal_policy=RemovalPolicy.DESTROY,
            ttl_attribute="ExpiresAt",  # Auto-delete expired shares
            global_secondary_indexes=[
                dynamodb.GlobalSecondaryIndexPropsV2(
                    index_name="AssetID-CreatedAt-index",
                    partition_key=dynamodb.Attribute(
                        name="AssetID",
                        type=dynamodb.AttributeType.STRING
                    ),
                    sort_key=dynamodb.Attribute(
                        name="CreatedAt",
                        type=dynamodb.AttributeType.NUMBER
                    ),
                    projection_type=dynamodb.ProjectionType.ALL
                ),
                dynamodb.GlobalSecondaryIndexPropsV2(
                    index_name="CreatedBy-CreatedAt-index",
                    partition_key=dynamodb.Attribute(
                        name="CreatedBy",
                        type=dynamodb.AttributeType.STRING
                    ),
                    sort_key=dynamodb.Attribute(
                        name="CreatedAt",
                        type=dynamodb.AttributeType.NUMBER
                    ),
                    projection_type=dynamodb.ProjectionType.ALL
                )
            ]
        )

        self._asset_shares_table = DynamoDBConstruct(
            self, "AssetSharesTable", props=asset_shares_table_props
        ).table

    @property
    def asset_shares_table(self) -> dynamodb.TableV2:
        """
        Return the Asset Shares DynamoDB table.

        Returns:
            dynamodb.TableV2: The Asset Shares table
        """
        return self._asset_shares_table

    @property
    def asset_shares_table_name(self) -> str:
        """
        Return the name of the Asset Shares table.

        Returns:
            str: Name of the DynamoDB table
        """
        return self._asset_shares_table.table_name

    @property
    def asset_shares_table_arn(self) -> str:
        """
        Return the ARN of the Asset Shares table.

        Returns:
            str: ARN of the DynamoDB table
        """
        return self._asset_shares_table.table_arn
