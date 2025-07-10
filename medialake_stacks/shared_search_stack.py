from constructs import Construct
from aws_cdk import (
    Stack,
    Fn,
    Environment,
    aws_ec2 as ec2,
    aws_kms as kms,
    # custom_resources as cr,
    Duration,
    RemovalPolicy,
    CfnOutput,
)
from config import config
from medialake_constructs.shared_constructs.s3_logging import (
    add_s3_access_logging_policy,
)

from medialake_constructs.shared_constructs.s3bucket import S3Bucket, S3BucketProps

from medialake_constructs.shared_constructs.eventbridge import EventBus, EventBusConfig
from medialake_constructs.vpc import CustomVpc, CustomVpcProps
from medialake_constructs.shared_constructs.opensearch_managed_cluster import (
    OpenSearchCluster,
    OpenSearchClusterProps,
)
from medialake_constructs.shared_constructs.opensearch_ingestion_pipeline import (
    OpenSearchIngestionPipeline,
    OpenSearchIngestionPipelineProps,
)
from medialake_constructs.shared_constructs.dynamodb import DynamoDB, DynamoDBProps

from cdk_nag import AwsSolutionsChecks, NagSuppressions

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

        env = kwargs.get("env")
        account = Stack.of(self).account
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