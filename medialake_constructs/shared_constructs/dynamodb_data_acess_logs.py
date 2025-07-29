import json
import logging
from dataclasses import dataclass

from aws_cdk import Aws, RemovalPolicy
from aws_cdk import aws_cloudtrail as cloudtrail
from aws_cdk import aws_iam as iam
from aws_cdk import aws_s3 as s3
from aws_cdk import custom_resources as cr
from constructs import Construct

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Add a handler if none exists
if not logger.handlers:
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    ch.setFormatter(formatter)
    logger.addHandler(ch)


@dataclass
class DynamoDBCloudTrailLogsProps:
    access_logs_bucket: s3.Bucket


class DynamoDBCloudTrailLogs(Construct):
    def __init__(
        self, scope: Construct, id: str, props: DynamoDBCloudTrailLogsProps, **kwargs
    ):
        super().__init__(scope, id, **kwargs)

        trail_name = "DynamoDBDataPlaneTrail"
        bucket_name = f"medialake-access-logs-{Aws.ACCOUNT_ID}-{Aws.REGION}-dev2"

        logger.info(f"Creating CloudTrail bucket with name: {bucket_name}")

        # Create the S3 bucket for CloudTrail logs
        cloudtrail_bucket = s3.Bucket(
            self,
            "CloudTrailBucket",
            bucket_name=bucket_name,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            enforce_ssl=True,
            versioned=True,
        )

        logger.info(f"Created bucket with ARN: {cloudtrail_bucket.bucket_arn}")

        # Create ACL check policy
        acl_policy = iam.PolicyStatement(
            sid="AWSCloudTrailAclCheck20150319",
            effect=iam.Effect.ALLOW,
            principals=[iam.ServicePrincipal("cloudtrail.amazonaws.com")],
            actions=["s3:GetBucketAcl"],
            resources=[cloudtrail_bucket.bucket_arn],
            conditions={
                "StringEquals": {
                    "aws:SourceArn": f"arn:aws:cloudtrail:{Aws.REGION}:{Aws.ACCOUNT_ID}:trail/{trail_name}"
                }
            },
        )

        logger.info(f"ACL Policy JSON: {json.dumps(acl_policy.to_json(), indent=2)}")
        cloudtrail_bucket.add_to_resource_policy(acl_policy)

        # Create write policy with array of resources
        write_policy = iam.PolicyStatement(
            sid="AWSCloudTrailWrite20150319",
            effect=iam.Effect.ALLOW,
            principals=[iam.ServicePrincipal("cloudtrail.amazonaws.com")],
            actions=["s3:PutObject"],
            resources=[f"{cloudtrail_bucket.bucket_arn}/AWSLogs/{Aws.ACCOUNT_ID}/*"],
            conditions={
                "StringEquals": {
                    "aws:SourceArn": f"arn:aws:cloudtrail:{Aws.REGION}:{Aws.ACCOUNT_ID}:trail/{trail_name}",
                    "s3:x-amz-acl": "bucket-owner-full-control",
                }
            },
        )

        logger.info(
            f"Write Policy JSON: {json.dumps(write_policy.to_json(), indent=2)}"
        )
        cloudtrail_bucket.add_to_resource_policy(write_policy)

        # Add custom resource to verify bucket policy
        verify_policy = cr.AwsCustomResource(
            self,
            "VerifyBucketPolicy",
            on_create=cr.AwsSdkCall(
                service="S3",
                action="getBucketPolicy",
                parameters={"Bucket": bucket_name},
                physical_resource_id=cr.PhysicalResourceId.of(f"{bucket_name}-policy"),
            ),
            policy=cr.AwsCustomResourcePolicy.from_sdk_calls(
                resources=[cloudtrail_bucket.bucket_arn]
            ),
        )

        logger.info("Creating CloudTrail")
        # Create CloudTrail
        cfn_trail = cloudtrail.CfnTrail(
            self,
            "DynamoDBDataPlaneTrail",
            is_logging=True,
            s3_bucket_name=cloudtrail_bucket.bucket_name,
            include_global_service_events=True,
            is_multi_region_trail=True,
            enable_log_file_validation=True,
            event_selectors=[
                cloudtrail.CfnTrail.EventSelectorProperty(
                    data_resources=[
                        cloudtrail.CfnTrail.DataResourceProperty(
                            type="AWS::DynamoDB::Table", values=["arn:aws:dynamodb"]
                        )
                    ],
                    include_management_events=True,
                    read_write_type="All",
                )
            ],
        )

        logger.info(f"Created CloudTrail with name: {cfn_trail.logical_id}")

        # Add dependency to ensure bucket policy is created before trail
        cfn_trail.node.add_dependency(verify_policy)

        # Make the bucket accessible to the rest of the stack
        self.cloudtrail_bucket = cloudtrail_bucket
