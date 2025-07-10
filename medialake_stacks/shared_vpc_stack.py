from dataclasses import dataclass

from constructs import Construct
from aws_cdk import (
    Stack,
    aws_ec2 as ec2,
    aws_dynamodb as dynamodb,
    aws_s3 as s3,
)
from config import config
from medialake_constructs.shared_constructs.s3_logging import (
    add_s3_access_logging_policy,
)

from medialake_constructs.shared_constructs.s3bucket import S3Bucket, S3BucketProps

from medialake_constructs.vpc import CustomVpc, CustomVpcProps

from medialake_constructs.shared_constructs.dynamodb import DynamoDB, DynamoDBProps

# Import the CDK logger
from cdk_logger import get_logger

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

# Initialize logger for this module
logger = get_logger("SharedVPCStack")


@dataclass
class SharedVPCStackProps:
    asset_table: dynamodb.TableV2
    media_assets_bucket: s3.IBucket


class SharedVPCStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, props: SharedVPCStackProps, **kwargs):
        super().__init__(scope, construct_id, **kwargs)

        logger.info(f"Initializing SharedVPCStack with ID: {construct_id}")
        
        env = kwargs.get("env")
        account = Stack.of(self).account
        region = Stack.of(self).region
        
        logger.debug(f"Stack environment: account={account}, region={region}")

        # Validate VPC configuration
        if not hasattr(config, 'vpc'):
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