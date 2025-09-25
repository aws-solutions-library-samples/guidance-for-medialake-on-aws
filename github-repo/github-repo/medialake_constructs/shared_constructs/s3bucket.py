from dataclasses import asdict, dataclass
from typing import List, Optional

from aws_cdk import RemovalPolicy
from aws_cdk import aws_kms as kms
from aws_cdk import aws_s3 as s3
from constructs import Construct

from config import config


@dataclass
class S3BucketProps:
    access_logs: bool = False
    destroy_on_delete: bool = True
    bucket_name: Optional[str] = None
    access_logs_bucket: Optional[s3.Bucket] = None
    cors: Optional[List[s3.CorsRule]] = None
    website_index_document: Optional[str] = None
    website_error_document: Optional[str] = None
    intelligent_tiering_configurations: Optional[
        List[s3.IntelligentTieringConfiguration]
    ] = None
    lifecycle_rules: Optional[List[s3.LifecycleRule]] = None
    existing_kms_key_arn: Optional[str] = None
    existing_bucket_arn: Optional[str] = None


class S3Bucket(Construct):
    def __init__(
        self,
        scope: Construct,
        id: str,
        props: S3BucketProps,
        **kwargs,
    ):
        super().__init__(scope, id, **kwargs)

        # Handle KMS key for bucket encryption
        if props.existing_kms_key_arn:
            self.kms_key = kms.Key.from_key_arn(
                self, "ImportedBucketEncryptionKey", key_arn=props.existing_kms_key_arn
            )
        else:
            self.kms_key = kms.Key(
                self,
                "BucketEncryptionKey",
                removal_policy=(
                    RemovalPolicy.DESTROY
                    if props.destroy_on_delete and config.environment != "prod"
                    else RemovalPolicy.RETAIN
                ),
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
                if props.destroy_on_delete and config.environment != "prod"
                else RemovalPolicy.RETAIN
            ),
            "auto_delete_objects": props.destroy_on_delete
            and config.environment != "prod",
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
        # if props.access_logs_bucket:
        #     bucket_props["server_access_logs_prefix"] = f"{props.bucket_name}/"

        # If we have an existing bucket, import it instead of creating a new one
        if props.existing_bucket_arn:
            self._bucket = s3.Bucket.from_bucket_attributes(
                self,
                "ImportedBucket",
                bucket_name=props.bucket_name,
                bucket_arn=props.existing_bucket_arn,
                encryption_key=self.kms_key if props.existing_kms_key_arn else None,
            )
        else:
            # Create new S3 bucket with combined properties
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

    @property
    def bucket_name(self) -> str:
        """
        Returns the underlying S3 bucket as an IBucket interface.
        """
        return self._bucket.bucket_name

    @property
    def key_arn(self) -> str:
        """
        Returns the ARN of the KMS key used for bucket encryption.
        """
        return self.kms_key.key_arn
