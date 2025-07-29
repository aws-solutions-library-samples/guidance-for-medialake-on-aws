from dataclasses import dataclass

from aws_cdk import Stack
from aws_cdk import aws_cloudfront as cloudfront
from aws_cdk import aws_s3 as s3
from constructs import Construct

from medialake_constructs.cloudfront_logging import (
    CloudFrontLogging,
    CloudFrontLoggingProps,
)
from medialake_constructs.shared_constructs.s3_logging import (
    add_s3_access_logging_policy,
    enable_s3_server_access_logging,
)


@dataclass
class PostDeployConfigStackProps:
    access_log_bucket: s3.IBucket
    medialake_ui_s3_bucket: s3.IBucket
    cloudfront_distribution: cloudfront.Distribution


class PostDeployConfigStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        props: PostDeployConfigStackProps,
        **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        enable_s3_server_access_logging(
            scope=self,
            access_logs_bucket=props.access_log_bucket,
            source_bucket=props.medialake_ui_s3_bucket,
        )

        add_s3_access_logging_policy(
            self,
            access_logs_bucket=props.access_log_bucket,
            source_bucket=props.medialake_ui_s3_bucket,
        )

        CloudFrontLogging(
            self,
            "CloudFrontLogging",
            props=CloudFrontLoggingProps(
                distribution=props.cloudfront_distribution,
                logging_bucket=props.access_log_bucket,
            ),
        )
