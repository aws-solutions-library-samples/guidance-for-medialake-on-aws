from aws_cdk import (
    aws_s3 as s3,
    aws_iam as iam,
    aws_kms as kms,
    RemovalPolicy,
    Stack,
)
from constructs import Construct
from typing import Optional, List
from dataclasses import dataclass


@dataclass
class S3BucketProps:
    bucket_name: str
    access_logs: bool = False
    access_logs_bucket: Optional[s3.Bucket] = None
    lifecycle_rules: Optional[List[s3.LifecycleRule]] = None
    destroy_on_delete: bool = True
    cors: Optional[List[s3.CorsRule]] = None


class S3Bucket(Construct):
    def __init__(
        self,
        scope: Construct,
        id: str,
        props: S3BucketProps,
        **kwargs,
    ):
        super().__init__(scope, id, **kwargs)
        stack = Stack.of(self)

        # Create KMS key for bucket encryption with RETAIN policy
        self.kms_key = kms.Key(
            self,
            "BucketEncryptionKey",
            removal_policy=RemovalPolicy.DESTROY,
            enable_key_rotation=True,
        )

        # Create S3 bucket with security best practices
        self._bucket = s3.Bucket(
            self,
            "S3Bucket",
            bucket_name=props.bucket_name,
            encryption=s3.BucketEncryption.KMS,
            encryption_key=self.kms_key,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            versioned=True,
            lifecycle_rules=props.lifecycle_rules,
            cors=props.cors,
            removal_policy=(
                RemovalPolicy.DESTROY
                if props.destroy_on_delete
                else RemovalPolicy.RETAIN
            ),
            auto_delete_objects=True if props.destroy_on_delete else False,
            server_access_logs_bucket=props.access_logs_bucket,
            server_access_logs_prefix=(
                f"{props.bucket_name}/" if props.access_logs_bucket else None
            ),
        )

        # Add logging bucket permissions if access_logs_bucket is provided
        if props.access_logs_bucket:
            props.access_logs_bucket.add_to_resource_policy(
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=["s3:PutObject"],
                    resources=[
                        props.access_logs_bucket.bucket_arn,
                        f"{props.access_logs_bucket.bucket_arn}/*",
                    ],
                    principals=[iam.ServicePrincipal("logging.s3.amazonaws.com")],
                    conditions={
                        "StringEquals": {"aws:SourceAccount": stack.account},
                        "ArnLike": {"aws:SourceArn": self._bucket.bucket_arn},
                    },
                )
            )

    @property
    def bucket(self) -> s3.IBucket:
        """
        Returns the underlying S3 bucket as an IBucket interface.
        """
        return self._bucket

    @property
    def bucket_arn(self) -> str:
        """
        Returns the underlying S3 bucket as an IBucket interface.
        """
        return self._bucket.bucket_arn
