# media-lake-v2/medialake_constructs/shared_constructs/s3_logging.py

from aws_cdk import Stack
from aws_cdk import aws_iam as iam
from aws_cdk import aws_s3 as s3
from constructs import Construct


def add_s3_access_logging_policy(
    scope: Construct,
    access_logs_bucket: s3.IBucket,
    source_bucket: s3.IBucket,
) -> None:
    """
    Configures an S3 bucket to receive CloudFront access logs.

    Args:
        scope: The construct scope
        access_logs_bucket: The bucket that will store access logs
        source_bucket: The bucket that will generate the logs

    Returns:
        None
    """
    stack = Stack.of(scope)

    # Enable ACLs for CloudFront logging
    if isinstance(access_logs_bucket, s3.Bucket):
        access_logs_bucket.node.default_child.add_property_override(
            "OwnershipControls",
            {"Rules": [{"ObjectOwnership": "BucketOwnerPreferred"}]},
        )

    # Add the CloudFront logging service principal permissions
    access_logs_bucket.add_to_resource_policy(
        iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=["s3:PutObject"],
            resources=[
                access_logs_bucket.bucket_arn,
                f"{access_logs_bucket.bucket_arn}/*",
            ],
            principals=[iam.ServicePrincipal("logging.s3.amazonaws.com")],
            conditions={
                "StringEquals": {"aws:SourceAccount": stack.account},
                "ArnLike": {"aws:SourceArn": source_bucket.bucket_arn},
            },
        )
    )

    # Grant CloudFront access to write logs
    access_logs_bucket.add_to_resource_policy(
        iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=["s3:PutObject"],
            resources=[f"{access_logs_bucket.bucket_arn}/*"],
            principals=[iam.ServicePrincipal("cloudfront.amazonaws.com")],
            conditions={
                "StringEquals": {"aws:SourceAccount": stack.account},
            },
        )
    )


def enable_s3_server_access_logging(
    scope: Construct,
    access_logs_bucket: s3.IBucket,
    source_bucket: s3.IBucket,
) -> None:
    """
    Enables server access logging for an S3 bucket, directing logs to a specified logging bucket
    with a prefix matching the source bucket name.

    Args:
        scope: The construct scope
        access_logs_bucket: The destination bucket that will store access logs
        source_bucket: The source bucket to enable logging for

    Returns:
        None
    """
    stack = Stack.of(scope)

    # Enable ACLs for S3 server access logging
    if isinstance(access_logs_bucket, s3.Bucket):
        access_logs_bucket.node.default_child.add_property_override(
            "OwnershipControls",
            {"Rules": [{"ObjectOwnership": "BucketOwnerPreferred"}]},
        )

    # Add the S3 logging service principal permissions to the destination bucket
    access_logs_bucket.add_to_resource_policy(
        iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=["s3:PutObject"],
            resources=[
                f"{access_logs_bucket.bucket_arn}/*",
            ],
            principals=[iam.ServicePrincipal("logging.s3.amazonaws.com")],
            conditions={
                "StringEquals": {"aws:SourceAccount": stack.account},
                "ArnLike": {"aws:SourceArn": source_bucket.bucket_arn},
            },
        )
    )

    # Enable server access logging on the source bucket
    if isinstance(source_bucket, s3.Bucket):
        source_bucket.node.default_child.add_property_override(
            "LoggingConfiguration",
            {
                "DestinationBucketName": access_logs_bucket.bucket_name,
                "LogFilePrefix": f"{source_bucket.bucket_name}/",
            },
        )
