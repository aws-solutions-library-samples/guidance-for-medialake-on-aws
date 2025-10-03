# medialake_constructs/shared_constructs/cloudfront_logging.py

from dataclasses import dataclass

from aws_cdk import aws_cloudfront as cloudfront
from aws_cdk import aws_iam as iam
from aws_cdk import aws_s3 as s3
from constructs import Construct


@dataclass
class CloudFrontLoggingProps:
    """Properties for CloudFront logging configuration."""

    distribution: cloudfront.Distribution
    logging_bucket: s3.IBucket
    prefix_override: str = None


class CloudFrontLogging(Construct):
    """
    Construct to configure CloudFront logging to an S3 bucket.

    Configures a CloudFront distribution to send logs to the specified S3 bucket
    with a prefix based on the distribution name.
    """

    def __init__(
        self,
        scope: Construct,
        id: str,
        props: CloudFrontLoggingProps,
    ) -> None:
        super().__init__(scope, id)

        # Get distribution ID for use in log prefix if no override provided
        distribution_id = props.distribution.distribution_id
        log_prefix = props.prefix_override or f"cloudfront-logs/{distribution_id}/"

        # Update the distribution's logging configuration
        cfn_distribution = props.distribution.node.default_child
        cfn_distribution.logging = {
            "bucket": props.logging_bucket.bucket_regional_domain_name,
            "includeCookies": False,
            "prefix": log_prefix,
        }

        # Grant CloudFront permission to write logs to the bucket
        props.logging_bucket.add_to_resource_policy(
            iam.PolicyStatement(
                sid="AllowCloudFrontLogging",
                actions=["s3:PutObject"],
                principals=[iam.ServicePrincipal("cloudfront.amazonaws.com")],
                resources=[f"{props.logging_bucket.bucket_arn}/{log_prefix}*"],
                conditions={
                    "StringEquals": {
                        "AWS:SourceArn": f"arn:aws:cloudfront::{scope.account}:distribution/{distribution_id}"
                    }
                },
            )
        )
