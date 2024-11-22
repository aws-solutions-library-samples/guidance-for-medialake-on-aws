from aws_cdk import (
    Stack,
    aws_iam as iam,
    aws_kms as kms,
    aws_s3 as s3,
    aws_dynamodb as dynamodb,
    RemovalPolicy
)

from constructs import Construct

from dataclasses import dataclass
from typing import Dict, Optional, List


@dataclass
class DynamoDBProps:
    """Configuration for DynamoDB creation."""

    name: str
    partition_key_name: str
    partition_key_type: str
    pipeline_name: Optional[str] = None
    pipeline_role: Optional[iam.Role] = None
    ddb_export_bucket: Optional[s3.Bucket] = None
    sort_key_name: Optional[str] = None
    sort_key_type: Optional[dynamodb.AttributeType] = None
    stream: Optional[dynamodb.StreamViewType] = None
    point_in_time_recovery: Optional[bool] = False


class DynamoDB(Construct):
    def __init__(self, scope: Construct, id: str, props: DynamoDBProps, **kwargs):
        super().__init__(scope, id, **kwargs)

        stack = Stack.of(self)
        
        self.region = stack.region
        self.account_id = stack.account
        
        # Create a custom KMS key for encryption
        self._kms_key = kms.Key(
            self, "DynamoDBKMSKey", removal_policy=RemovalPolicy.DESTROY
        )

        # Create the DynamoDB table with the provided configuration
        self._table = dynamodb.TableV2(
            self,
            "DynamoDBTable",
            table_name=props.name,
            partition_key=dynamodb.Attribute(
                name=props.partition_key_name, type=props.partition_key_type
            ),
            # encryption_key=self._kms_key,
            # point_in_time_recovery=config.get("point_in_time_recovery", False),
            removal_policy=RemovalPolicy.DESTROY,
            dynamo_stream=props.stream,
        )
        
        # Create an IAM role for custom resource
        dynamo_db_pipeline_custom_resource_role = iam.Role(
            self,
            "DynamoDbPipelineCustomResourceRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
        )

        # Add policies to the custom resource role
        dynamo_db_pipeline_custom_resource_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "dynamodb:BatchWriteItem",
                    "dynamodb:CreateTable",
                    "dynamodb:DeleteTable",
                    "dynamodb:UpdateContinuousBackups",
                ],
                conditions={
                    "StringEquals": {"dynamodb:TableName": self.table_name}
                },
                resources=["*"],
            )
        )

        dynamo_db_pipeline_custom_resource_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "osis:CreatePipeline",
                    "osis:DeletePipeline",
                    "osis:StopPipeline",
                ],
                resources=[
                    f"arn:aws:osis:{stack.region}:{stack.account}:pipeline/{props.pipeline_name}dynamodb-etl-pipeline"
                ],
            )
        )
       
        if props.pipeline_role:
    
            dynamo_db_pipeline_custom_resource_role.add_to_policy(
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "iam:PassRole",
                        "iam:CreateRole",
                        "iam:AttachRolePolicy",
                        "iam:DetachRolePolicy",
                        "iam:GetRole",
                        "iam:DeleteRole",
                    ],
                    resources=[props.pipeline_role.role_arn],
                )
            )

        dynamo_db_pipeline_custom_resource_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["iam:ListPolicies"],
                resources=["*"],
            )
        )

        dynamo_db_pipeline_custom_resource_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "iam:CreatePolicy",
                    "iam:DeletePolicy",
                ],
                conditions={
                    "StringEquals": {
                        "iam:PolicyName": [
                            "IngestionPipelinePolicy",
                            "DynamoDBIngestionPolicy",
                        ]
                    }
                },
                resources=["*"],
            )
        )

        dynamo_db_pipeline_custom_resource_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "logs:CreateLogDelivery",
                    "logs:PutResourcePolicy",
                    "logs:UpdateLogDelivery",
                    "logs:DeleteLogDelivery",
                    "logs:DescribeResourcePolicies",
                    "logs:GetLogDelivery",
                    "logs:ListLogDeliveries",
                ],
                resources=["*"],
            )
        )
        if props.ddb_export_bucket:
            dynamo_db_pipeline_custom_resource_role.add_to_policy(
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "s3:ListObjects",
                        "s3:DeleteObject",
                        "s3:DeleteObjectVersion",
                        "s3:ListBucket",
                        "s3:DeleteBucket",
                    ],
                    resources=[props.ddb_export_bucket.bucket.bucket_arn, f"{props.ddb_export_bucket.bucket.bucket_arn}/*"],
                )
            )

        dynamo_db_pipeline_custom_resource_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "aoss:CreateVpcEndpoint",
                    "aoss:DeleteVpcEndpoint",
                    "aoss:ListVpcEndpoints",
                    "aoss:GetSecurityPolicy",
                    "aoss:UpdateSecurityPolicy",
                    "ec2:CreateVpcEndpoint",
                    "ec2:DeleteVpcEndpoints",
                    "ec2:ListVpcEndpoints",
                    "ec2:DescribeVpcEndpoints",
                    "ec2:DescribeVpcs",
                    "ec2:DescribeSubnets",
                    "ec2:DescribeSecurityGroups",
                    "ec2:CreateTags",
                    "ec2:DeleteTags",
                    "route53:AssociateVPCWithHostedZone",
                    "route53:DisassociateVPCFromHostedZone",
                ],
                resources=["*"],
            )
        )

    @property
    def table(self) -> dynamodb.TableV2:
        return self._table

    @property
    def table_name(self) -> str:
        return self._table.table_name

    @property
    def table_arn(self) -> str:
        return self._table.table_arn

    # @property
    # def kms_key(self) -> kms.Key:
    #     return self._kms_key
