from dataclasses import dataclass

from aws_cdk import Stack
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_s3 as s3
from constructs import Construct

# Import the CDK logger
from cdk_logger import get_logger
from config import config
from medialake_constructs.vpc import CustomVpc, CustomVpcProps

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

# Initialize logger for this module
logger = get_logger("SharedVPCStack")


@dataclass
class SharedVPCStackProps:
    asset_table: dynamodb.TableV2
    media_assets_bucket: s3.IBucket


class SharedVPCStack(Stack):
    def __init__(
        self, scope: Construct, construct_id: str, props: SharedVPCStackProps, **kwargs
    ):
        super().__init__(scope, construct_id, **kwargs)

        logger.info(f"Initializing SharedVPCStack with ID: {construct_id}")

        kwargs.get("env")
        account = Stack.of(self).account
        region = Stack.of(self).region

        logger.debug(f"Stack environment: account={account}, region={region}")

        # Validate VPC configuration
        if not hasattr(config, "vpc"):
            logger.error("VPC configuration is missing in config")
            raise ValueError("VPC configuration is missing in config")

        logger.info("Creating VPC infrastructure")
        try:
            self._vpc = CustomVpc(
                self,
                "MediaLakeVPC",
                props=CustomVpcProps(
                    use_existing_vpc=config.vpc.use_existing_vpc,
                    existing_vpc=config.vpc.existing_vpc,
                    new_vpc=config.vpc.new_vpc,
                ),
            )
            logger.info(f"VPC created successfully with ID: {self._vpc.vpc_id}")
        except Exception as e:
            logger.error(f"Failed to create VPC: {str(e)}")
            raise
