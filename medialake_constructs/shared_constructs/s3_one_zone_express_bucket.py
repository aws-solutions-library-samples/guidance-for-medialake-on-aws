from dataclasses import dataclass, asdict
from typing import Optional, List
from aws_cdk import (
    Stack,
    aws_s3 as s3,
    aws_s3express as s3express,
    aws_iam as iam,
    RemovalPolicy,
    CfnOutput
)
from constructs import Construct


@dataclass
class S3ExpressOneZoneBucketProps:
    bucket_name: str
    access_logs: bool = False
    
    destroy_on_delete: bool = True
    access_logs_bucket: Optional[s3.Bucket] = None


class S3ExpressOneZoneBucket(Construct):
    def __init__(self, scope: Construct, construct_id: str, props: S3ExpressOneZoneBucketProps, **kwargs):
        super().__init__(scope, construct_id, **kwargs)

        if props.access_logs_bucket:
            access_logs_prefix = f"{props.bucket_name}/"

        cfn_directory_bucket = s3express.CfnDirectoryBucket(self, "InternalBucket",
            data_redundancy="SingleAvailabilityZone",
            location_name="use1-az1",

            # the properties below are optional
            bucket_name=f"{props.bucket_name}--use1-az1--x-s3",
            # lifecycle_configuration=s3express.CfnDirectoryBucket.LifecycleConfigurationProperty(
            #     rules=[s3express.CfnDirectoryBucket.RuleProperty(
            #         status="status",

            #         # the properties below are optional
            #         abort_incomplete_multipart_upload=s3express.CfnDirectoryBucket.AbortIncompleteMultipartUploadProperty(
            #             days_after_initiation=30
            #         ),
            #         expiration_in_days=30,
            #         id="id",
            #         object_size_greater_than="objectSizeGreaterThan",
            #         object_size_less_than="objectSizeLessThan",
            #         prefix="prefix"
            #     )]
            # )
        )