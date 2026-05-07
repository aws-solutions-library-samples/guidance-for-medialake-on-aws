from aws_cdk import Stack
from aws_cdk import aws_ec2 as ec2  # custom_resources as cr,
from constructs import Construct

from config import config
from medialake_constructs.shared_constructs.opensearch_managed_cluster import (
    OpenSearchCluster,
    OpenSearchClusterProps,
)

"""
Base infrastructure stack that sets up core AWS resources for the MediaLake application.

This stack creates and configures:
- VPC and networking components
- OpenSearch cluster
- S3 buckets for media assets, IAC assets, and DynamoDB exports
- EventBridge event bus
- DynamoDB tables for asset management
- Ingestion pipeline for syncing DynamoDB to OpenSearch
"""


class SharedSearchStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs):
        super().__init__(scope, construct_id, **kwargs)

        kwargs.get("env")
        Stack.of(self).account
        region = Stack.of(self).region

        self._opensearch_cluster = OpenSearchCluster(
            self,
            "MediaLakeOpenSearch",
            props=OpenSearchClusterProps(
                domain_name=f"{config.resource_prefix}-os-{region}-{config.environment}",
                vpc=self._vpc.vpc,
                subnet_ids=selected_subnet_ids,
                collection_indexes=[opensearch_index_name],
                security_group=self._security_group,
            ),
        )
