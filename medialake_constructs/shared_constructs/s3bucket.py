from aws_cdk import (
    aws_s3 as s3,
    aws_iam as iam,
    aws_kms as kms,
    RemovalPolicy,
    Stack,
)
from constructs import Construct
from typing import Optional, List
from dataclasses import dataclass, asdict


@dataclass
class S3BucketProps:
    bucket_name: str
    access_logs: bool = False
    destroy_on_delete: bool = True
    access_logs_bucket: Optional[s3.Bucket] = None
    cors: Optional[List[s3.CorsRule]] = None
    website_index_document: Optional[str] = None
    website_error_document: Optional[str] = None
    intelligent_tiering_configurations: Optional[
        List[s3.IntelligentTieringConfiguration]
    ] = None
    lifecycle_rules: Optional[List[s3.LifecycleRule]] = None


class S3Bucket(Construct):
    def __init__(
        self,
        scope: Construct,
        id: str,
        props: S3BucketProps,
        **kwargs,
    ):
        super().__init__(scope, id, **kwargs)

        # Create KMS key for bucket encryption
        self.kms_key = kms.Key(
            self,
            "BucketEncryptionKey",
            removal_policy=RemovalPolicy.DESTROY,
            enable_key_rotation=True,
        )

        bucket_props = {
            "encryption": s3.BucketEncryption.KMS,
            "encryption_key": self.kms_key,
            "block_public_access": s3.BlockPublicAccess.BLOCK_ALL,
            "versioned": True,
            "enforce_ssl": True,
            "removal_policy": (
                RemovalPolicy.DESTROY
                if props.destroy_on_delete
                else RemovalPolicy.RETAIN
            ),
            "auto_delete_objects": props.destroy_on_delete,
        }
        # Add optional properties from props if they exist
        props_dict = asdict(props)
        optional_props = {
            "bucket_name": "bucket_name",
            "lifecycle_rules": "lifecycle_rules",
            "cors": "cors",
            "server_access_logs_bucket": "access_logs_bucket",
        }

        for prop_name, bucket_prop_name in optional_props.items():
            if props_dict.get(prop_name) is not None:
                bucket_props[bucket_prop_name] = props_dict[prop_name]

        # Add server access logs prefix if access_logs_bucket is provided
        if props.access_logs_bucket:
            bucket_props["server_access_logs_prefix"] = f"{props.bucket_name}/"

        # Create S3 bucket with combined properties
        self._bucket = s3.Bucket(self, "S3Bucket", **bucket_props)

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
