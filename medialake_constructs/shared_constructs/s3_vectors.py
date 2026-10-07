from dataclasses import dataclass, field
from typing import List, Optional

from aws_cdk import CfnOutput, RemovalPolicy, Stack
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_iam as iam
from aws_cdk import aws_s3vectors as s3vectors
from constructs import Construct

# Metadata keys stored on every vector that search NEVER filters on — declared
# non-filterable so the index's filterable schema is small and deterministic.
#
# Why this matters: S3 Vectors treats all metadata keys as filterable-by-default
# unless declared otherwise at index creation. Leaving all 14 keys filterable let
# a schema-establishment race silently drop `embedding_option` filterability for
# vectors written into a fresh index under concurrent bulk load. Declaring the
# return-only keys as non-filterable removes that inference step. The keys search
# DOES filter on (inventory_id, embedding_option, embedding_scope, content_type)
# are intentionally absent here and stay filterable.
#
# NOTE: this takes effect only on a NEWLY created index — non-filterable keys are
# immutable after creation. Existing indexes must be recreated + re-ingested.
NON_FILTERABLE_METADATA_KEYS = [
    "timestamp",
    "start_offset_sec",
    "end_offset_sec",
    "start_timecode",
    "end_timecode",
    "embedding_dimension",
    "space_type",
    "model_provider",
    "model_name",
    "model_version",
]


@dataclass
class S3VectorClusterProps:
    bucket_name: str
    vector_dimension: int = 512
    collection_indexes: List[str] = field(default_factory=lambda: ["media"])
    vpc: Optional[ec2.IVpc] = None
    security_group: Optional[ec2.SecurityGroup] = None


class S3VectorCluster(Construct):
    """
    S3 Vector cluster using native CloudFormation resources.

    This construct creates an S3 Vector bucket and indexes using
    AWS::S3Vectors::VectorBucket and AWS::S3Vectors::Index resources.

    S3 Vectors GA Capabilities:
    - Up to 2 billion vectors per index
    - Up to 100 search results per query
    - ~100ms query latency
    - Native CloudFormation support

    Args:
        scope: CDK construct scope
        id: Construct identifier
        props: S3VectorClusterProps configuration

    Note:
        VPC and security_group parameters in props are deprecated
        and ignored. S3 Vectors provisioning doesn't require VPC.
        Runtime operations still need VPC access.
    """

    def __init__(self, scope: Construct, id: str, props: S3VectorClusterProps) -> None:
        super().__init__(scope, id)

        # Import config for environment-aware removal policy
        from config import config

        stack = Stack.of(self)
        self.region = stack.region
        self.account_id = stack.account
        self._bucket_name = props.bucket_name
        self._vector_dimension = props.vector_dimension
        self._indexes = props.collection_indexes

        # Create S3 Vector Bucket using native CDK construct
        # DECISION: Using native CfnVectorBucket instead of custom Lambda provisioning
        # per design.md Section 1 - simplifies infrastructure and improves reliability
        self._vector_bucket = s3vectors.CfnVectorBucket(
            self,
            "VectorBucket",
            vector_bucket_name=self._bucket_name,
            encryption_configuration=s3vectors.CfnVectorBucket.EncryptionConfigurationProperty(
                sse_type="AES256"  # Default to S3-managed encryption per FR-5
            ),
        )

        # Apply removal policy based on environment per FR-6
        # RETAIN for production to prevent data loss, DESTROY for dev/staging
        # NOTE: Even with DESTROY policy, the bucket must be empty before deletion
        # The provisioned_resource_cleanup Lambda handles emptying the bucket/indexes
        removal_policy = (
            RemovalPolicy.RETAIN
            if config.environment == "prod"
            else RemovalPolicy.DESTROY
        )
        self._vector_bucket.apply_removal_policy(removal_policy)

        # Create vector indexes for each collection per FR-2 and US-4
        # DECISION: Loop through collection_indexes to support multiple indexes
        # per design.md Section 1 - enables different embedding types in separate indexes
        self._index_resources = []
        for index_name in props.collection_indexes:
            index = s3vectors.CfnIndex(
                self,
                f"Index-{index_name}",
                vector_bucket_name=self._bucket_name,
                index_name=index_name,
                dimension=self._vector_dimension,
                data_type="float32",  # Standard data type for embeddings
                distance_metric="cosine",  # Cosine similarity for semantic search
                # Declare return-only keys non-filterable so the filterable schema
                # is small and deterministic (prevents the filterability race).
                metadata_configuration=s3vectors.CfnIndex.MetadataConfigurationProperty(
                    non_filterable_metadata_keys=NON_FILTERABLE_METADATA_KEYS,
                ),
                encryption_configuration=s3vectors.CfnIndex.EncryptionConfigurationProperty(
                    sse_type="AES256"  # Match bucket encryption per FR-5
                ),
            )

            # Ensure index depends on bucket per FR-6 (proper creation/deletion order)
            # CloudFormation will create bucket first, then indexes
            # Deletion happens in reverse: indexes first, then bucket
            index.add_dependency(self._vector_bucket)

            # Apply same removal policy as bucket
            index.apply_removal_policy(removal_policy)

            # Store reference for potential future use
            self._index_resources.append(index)

        # Store properties for access by other constructs
        CfnOutput(
            self,
            "S3VectorBucketName",
            value=self._bucket_name,
            description="Name of the S3 Vector bucket",
        )

        CfnOutput(
            self,
            "S3VectorDimension",
            value=str(self._vector_dimension),
            description="Vector dimension for S3 Vector indexes",
        )

        CfnOutput(
            self,
            "S3VectorIndexes",
            value=",".join(props.collection_indexes),
            description="List of S3 Vector indexes created",
        )

    @property
    def bucket_name(self) -> str:
        """Return the S3 Vector bucket name."""
        return self._bucket_name

    @property
    def vector_dimension(self) -> int:
        """Return the vector dimension."""
        return self._vector_dimension

    @property
    def indexes(self) -> List[str]:
        """Return the list of indexes."""
        return self._indexes

    @property
    def bucket_arn(self) -> str:
        """Return the S3 Vector bucket ARN."""
        return f"arn:aws:s3vectors:{self.region}:{self.account_id}:bucket/{self._bucket_name}"

    def grant_s3_vector_access(self, grantee: iam.IGrantable) -> iam.Grant:
        """Grant S3 Vector access to the specified grantee."""
        return iam.Grant.add_to_principal(
            grantee=grantee,
            actions=[
                "s3vectors:GetVectorBucket",
                "s3vectors:ListVectorBuckets",
                "s3vectors:GetIndex",
                "s3vectors:ListIndexes",
                "s3vectors:PutVectors",
                "s3vectors:GetVectors",
                "s3vectors:DeleteVectors",
                "s3vectors:QueryVectors",
            ],
            resources=[
                self.bucket_arn,
                f"{self.bucket_arn}/*",
            ],
        )

    def grant_s3_vector_read_access(self, grantee: iam.IGrantable) -> iam.Grant:
        """Grant read-only S3 Vector access to the specified grantee."""
        return iam.Grant.add_to_principal(
            grantee=grantee,
            actions=[
                "s3vectors:GetVectorBucket",
                "s3vectors:ListVectorBuckets",
                "s3vectors:GetIndex",
                "s3vectors:ListIndexes",
                "s3vectors:GetVectors",
                "s3vectors:QueryVectors",
            ],
            resources=[
                self.bucket_arn,
                f"{self.bucket_arn}/*",
            ],
        )

    def grant_s3_vector_write_access(self, grantee: iam.IGrantable) -> iam.Grant:
        """Grant write S3 Vector access to the specified grantee."""
        return iam.Grant.add_to_principal(
            grantee=grantee,
            actions=[
                "s3vectors:GetVectorBucket",
                "s3vectors:GetIndex",
                "s3vectors:PutVectors",
                "s3vectors:DeleteVectors",
            ],
            resources=[
                self.bucket_arn,
                f"{self.bucket_arn}/*",
            ],
        )
