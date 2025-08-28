import hashlib
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from aws_cdk import CfnOutput, CustomResource, Stack
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_iam as iam
from aws_cdk import aws_logs as logs
from aws_cdk import custom_resources as cr
from constructs import Construct

from medialake_constructs.shared_constructs.lambda_base import Lambda, LambdaConfig


@dataclass
class S3VectorClusterProps:
    bucket_name: str
    vector_dimension: int = 1024
    collection_indexes: List[str] = field(default_factory=lambda: ["media"])
    vpc: Optional[ec2.IVpc] = None
    security_group: Optional[ec2.SecurityGroup] = None


class S3VectorCluster(Construct):
    def __init__(self, scope: Construct, id: str, props: S3VectorClusterProps) -> None:
        super().__init__(scope, id)

        stack = Stack.of(self)
        self.region = stack.region
        self.account_id = stack.account
        self._bucket_name = props.bucket_name
        self._vector_dimension = props.vector_dimension

        if not props.vpc:
            raise ValueError("A VPC must be provided for the S3 Vector cluster.")

        # Create Lambda function for S3 Vector bucket and index creation
        create_s3_vector_lambda = Lambda(
            self,
            "MediaLakeS3VectorCreationFunction",
            config=LambdaConfig(
                entry="lambdas/back_end/create_s3_vector_index",
                lambda_handler="handler",
                vpc=props.vpc,
                security_groups=(
                    [props.security_group] if props.security_group else None
                ),
                timeout_minutes=5,
                environment_variables={
                    "VECTOR_BUCKET_NAME": self._bucket_name,
                    "INDEX_NAMES": ",".join(props.collection_indexes),
                    "REGION": self.region,
                    "VECTOR_DIMENSION": str(self._vector_dimension),
                },
            ),
        )

        # Add IAM permissions for S3 Vector operations
        create_s3_vector_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "s3vectors:CreateVectorBucket",
                    "s3vectors:GetVectorBucket",
                    "s3vectors:ListVectorBuckets",
                    "s3vectors:DeleteVectorBucket",
                    "s3vectors:CreateIndex",
                    "s3vectors:GetIndex",
                    "s3vectors:ListIndexes",
                    "s3vectors:DeleteIndex",
                    "s3vectors:PutVectors",
                    "s3vectors:GetVectors",
                    "s3vectors:DeleteVectors",
                    "s3vectors:QueryVectors",
                ],
                resources=[
                    f"arn:aws:s3vectors:{self.region}:{self.account_id}:bucket/{self._bucket_name}",
                    f"arn:aws:s3vectors:{self.region}:{self.account_id}:bucket/{self._bucket_name}/*",
                ],
            )
        )

        # Add VPC permissions if using VPC
        if props.vpc:
            create_s3_vector_lambda.function.add_to_role_policy(
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "ec2:CreateNetworkInterface",
                        "ec2:DescribeNetworkInterfaces",
                        "ec2:DeleteNetworkInterface",
                    ],
                    resources=["*"],
                )
            )

        # Create a custom resource provider that triggers the Lambda for S3 Vector setup
        provider = cr.Provider(
            self,
            "S3VectorCreateResourceProvider",
            on_event_handler=create_s3_vector_lambda.function,
            log_retention=logs.RetentionDays.ONE_WEEK,
        )

        # Generate hash of Lambda code for change detection
        lambda_code = Path(
            "lambdas/back_end/create_s3_vector_index/index.py"
        ).read_text(encoding="utf-8")
        code_hash = hashlib.sha256(lambda_code.encode()).hexdigest()

        # Create custom resource to trigger S3 Vector setup
        create_s3_vector_resource = CustomResource(
            self,
            "S3VectorCreateResource",
            service_token=provider.service_token,
            properties={
                "code_hash": code_hash,
                "timestamp": str(int(time.time())),
                "bucket_name": self._bucket_name,
                "vector_dimension": self._vector_dimension,
                "indexes": ",".join(props.collection_indexes),
            },
            resource_type="Custom::S3VectorCreateIndex",
        )

        # Store properties for access by other constructs (already set above)
        self._indexes = props.collection_indexes

        # Output the S3 Vector bucket information
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
