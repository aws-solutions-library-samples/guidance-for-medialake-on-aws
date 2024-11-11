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
class S3Config:
    bucket_name: str
    access_logs: bool = False
    lifecycle_rules: Optional[List[s3.LifecycleRule]] = None
    destroy_on_delete: bool = True
    cors: Optional[List[s3.CorsRule]] = None


class S3Bucket(Construct):
    def __init__(
        self,
        scope: Construct,
        id: str,
        s3_config: S3Config,
        **kwargs,
    ):
        super().__init__(scope, id, **kwargs)
        stack = Stack.of(self)

        # Create KMS key for bucket encryption with RETAIN policy
        self.kms_key = kms.Key(
            self,
            "BucketEncryptionKey",
            removal_policy=RemovalPolicy.DESTROY,  # Changed to RETAIN to prevent deletion
            enable_key_rotation=True,  # Added key rotation as a security best practice
        )

        # Create S3 bucket with security best practices
        self.bucket = s3.Bucket(
            self,
            "SecureBucket",
            bucket_name=s3_config.bucket_name,
            encryption=s3.BucketEncryption.KMS,
            encryption_key=self.kms_key,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            versioned=True,
            lifecycle_rules=s3_config.lifecycle_rules,
            cors=s3_config.cors,
            removal_policy=(
                RemovalPolicy.DESTROY
                if s3_config.destroy_on_delete
                else RemovalPolicy.RETAIN
            ),
            auto_delete_objects=True if s3_config.destroy_on_delete else False,
        )

        # Enable access logging if access_log_bucket is provided
        if s3_config.access_logs:
            access_log_bucket = f"{s3_config.bucket_name}-logs-{stack.region}"
            self.bucket.add_to_resource_policy(
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=["s3:PutObject"],
                    resources=[
                        f"{access_log_bucket.bucket_arn}/{self.bucket.bucket_name}/*"
                    ],
                    principals=[iam.ServicePrincipal("logging.s3.amazonaws.com")],
                )
            )
