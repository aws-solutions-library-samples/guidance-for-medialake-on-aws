import json
import os
import random
from typing import Optional

from aws_cdk import (
    Stack,
    Duration,
    RemovalPolicy,
    aws_iam as iam,
    aws_s3 as s3,
    aws_ec2 as ec2,
    aws_opensearchserverless as oss,
    aws_logs as logs,
    aws_lambda as _lambda,
    custom_resources as cr,
    CfnOutput,
)
from constructs import Construct


class Props(Stack):
    def __init__(
        self,
        scope: Construct,
        id: str,
        current_user_arn: str,
        collection_name: Optional[str] = None,
        table_name: Optional[str] = None,
        bucket_name: Optional[str] = None,
        pipeline_name: Optional[str] = None,
        log_group_name: Optional[str] = None,
        vpc_name: Optional[str] = None,
        vpc_endpoint_name: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(scope, id, **kwargs)

        # Default properties
        default_props = {
            "collection_name": "dynamodb-etl-collection",
            "table_name": "opensearch-etl-table",
            "bucket_name": f"dynamodb-oss-etl-bucket-{random.randint(100, 999)}",
            "pipeline_name": "dynamodb-etl-pipeline",
            "log_group_name": "/aws/vendedlogs/OpenSearchIngestion/dynamodb-osis-pipeline/audit-logs",
            "vpc_name": "dynamodb-opensearch-etl-vpc",
            "vpc_endpoint_name": "dynamodb-etl-collection-endpoint",
        }

        # Assign properties with defaults
        self.collection_name = collection_name or default_props["collection_name"]
        self.table_name = table_name or default_props["table_name"]
        self.bucket_name = bucket_name or default_props["bucket_name"]
        self.pipeline_name = pipeline_name or default_props["pipeline_name"]
        self.log_group_name = log_group_name or default_props["log_group_name"]
        self.current_user_arn = current_user_arn
        self.vpc_name = vpc_name or default_props["vpc_name"]
        self.vpc_endpoint_name = vpc_endpoint_name or default_props["vpc_endpoint_name"]

        # Create VPC for OpenSearchServerless
        vpc = ec2.Vpc(
            self,
            "OpenSearchServerlessVpc",
            vpc_name=self.vpc_name,
            ip_addresses=ec2.IpAddresses.cidr("10.0.0.0/16"),
            max_azs=3,
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    cidr_mask=24,
                    name="private-oss-pipeline-",
                    subnet_type=ec2.SubnetType.PRIVATE_ISOLATED,
                )
            ],
        )

        # Create security group
        security_group = ec2.SecurityGroup(
            self,
            "OpenSearchServerlessSecurityGroup",
            vpc=vpc,
        )

        # Allow HTTPS ingress from the VPC CIDR
        security_group.add_ingress_rule(
            peer=ec2.Peer.ipv4(vpc.vpc_cidr_block),
            connection=ec2.Port.tcp(443),
            description="Allow HTTPS ingress from VPC CIDR",
        )

        # Allow HTTP ingress from the VPC CIDR
        security_group.add_ingress_rule(
            peer=ec2.Peer.ipv4(vpc.vpc_cidr_block),
            connection=ec2.Port.tcp(80),
            description="Allow HTTP ingress from VPC CIDR",
        )

        # Create OpenSearch Serverless collection
        collection = oss.CfnCollection(
            self,
            "OpenSearchServerlessCollection",
            name=self.collection_name,
            description="Collection created by CDK to explore DynamoDB to OpenSearch Pipeline ETL Integration.",
            type="SEARCH",
        )

        # S3 bucket for DynamoDB initial export
        bucket = s3.Bucket(
            self,
            "OpenSearchIngestionBucket",
            bucket_name=self.bucket_name,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            auto_delete_objects=True,
            removal_policy=RemovalPolicy.DESTROY,
        )

        # Create CloudWatch logs for Ingestion Pipeline
        ingestion_log_group = logs.LogGroup(
            self,
            "IngestionPipelineLogGroup",
            log_group_name=self.log_group_name,
            removal_policy=RemovalPolicy.DESTROY,
            retention=logs.RetentionDays.ONE_DAY,
        )

        # Create OpenSearch Ingestion Pipeline Role
        pipeline_role = iam.Role(
            self,
            "IngestionRole",
            assumed_by=iam.ServicePrincipal("osis-pipelines.amazonaws.com"),
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
                    f"arn:aws:osis:{self.region}:{self.account}:pipeline/{self.pipeline_name}"
                ],
            )
        )

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
                resources=[pipeline_role.role_arn],
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
                resources=[bucket.bucket_arn, f"{bucket.bucket_arn}/*"],
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

        # OpenSearch encryption policy
        encryption_policy = oss.CfnSecurityPolicy(
            self,
            "EncryptionPolicy",
            name="ddb-etl-encryption-policy",
            type="encryption",
            description=f"Encryption policy for {self.collection_name} collection.",
            policy=json.dumps(
                {
                    "Rules": [
                        {
                            "ResourceType": "collection",
                            "Resource": [f"collection/{self.collection_name}*"],
                        }
                    ],
                    "AWSOwnedKey": True,
                }
            ),
        )

        # OpenSearch network policy
        network_policy = oss.CfnSecurityPolicy(
            self,
            "NetworkPolicy",
            name="ddb-etl-network-policy",
            type="network",
            description=f"Network policy for {self.collection_name} collection.",
            policy=json.dumps(
                [
                    {
                        "Rules": [
                            {
                                "ResourceType": "collection",
                                "Resource": [f"collection/{self.collection_name}"],
                            },
                            {
                                "ResourceType": "dashboard",
                                "Resource": [f"collection/{self.collection_name}"],
                            },
                        ],
                        "AllowFromPublic": True,
                    }
                ]
            ),
        )

        # OpenSearch data access policy
        data_access_policy = oss.CfnAccessPolicy(
            self,
            "DataAccessPolicy",
            name="ddb-etl-access-policy",
            type="data",
            description=f"Data access policy for {self.collection_name} collection.",
            policy=json.dumps(
                [
                    {
                        "Rules": [
                            {
                                "ResourceType": "collection",
                                "Resource": [f"collection/{self.collection_name}*"],
                                "Permission": [
                                    "aoss:CreateCollectionItems",
                                    "aoss:DescribeCollectionItems",
                                    "aoss:DeleteCollectionItems",
                                    "aoss:UpdateCollectionItems",
                                ],
                            },
                            {
                                "ResourceType": "index",
                                "Resource": [f"index/{self.collection_name}*/*"],
                                "Permission": [
                                    "aoss:CreateIndex",
                                    "aoss:DeleteIndex",
                                    "aoss:UpdateIndex",
                                    "aoss:DescribeIndex",
                                    "aoss:ReadDocument",
                                    "aoss:WriteDocument",
                                ],
                            },
                        ],
                        "Principal": [
                            pipeline_role.role_arn,
                            self.current_user_arn,
                            f"arn:aws:iam::{self.account}:user/Admin",
                        ],
                    }
                ]
            ),
        )

        # Custom resource to populate DynamoDB with dummy data
        on_event = _lambda.Function(
            self,
            "DynamoDBPipelineCustomFunction",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="custom_resource.on_event",
            code=_lambda.Code.from_asset(os.path.join(os.path.dirname(__file__), "../assets")),
            architecture=_lambda.Architecture.X86_64,
            timeout=Duration.seconds(600),
            environment={
                "TABLE_NAME": self.table_name,
                "PIPELINE_NAME": self.pipeline_name,
                "PIPELINE_ROLE_NAME": pipeline_role.role_name,
                "REGION": self.region,
                "ACCOUNT_ID": self.account,
                "NETWORK_POLICY_NAME": network_policy.name,
                "BUCKET_NAME": self.bucket_name,
                "BUCKET_ARN": bucket.bucket_arn,
                "COLLECTION_ARN": collection.attr_arn,
                "COLLECTION_NAME": self.collection_name,
                "COLLECTION_ENDPOINT": collection.attr_collection_endpoint,
                "LOG_GROUP_NAME": self.log_group_name,
                "VPC_ID": vpc.vpc_id,
                "VPC_ENDPOINT_NAME": self.vpc_endpoint_name,
                "SECURITY_GROUP_IDS": security_group.security_group_id,
                "SUBNET_IDS_ISOLATED": json.dumps(
                    [
                        subnet.subnet_id
                        for subnet in vpc.isolated_subnets
                        if subnet.availability_zone.endswith("a")
                    ]
                    + [
                        subnet.subnet_id
                        for subnet in vpc.isolated_subnets
                        if subnet.availability_zone.endswith("b")
                    ]
                ),
            },
            role=dynamo_db_pipeline_custom_resource_role,
        )

        dynamo_db_pipeline_custom_resource_provider = cr.Provider(
            self,
            "DynamoDBPipelineCustomResourceProvider",
            on_event_handler=on_event,
            log_retention=logs.RetentionDays.ONE_DAY,
        )

        custom_resource = cr.CustomResource(
            self,
            "DynamoDBPipelineCustomResource",
            service_token=dynamo_db_pipeline_custom_resource_provider.service_token,
        )

        # Ensure dependencies
        collection.node.add_dependency(encryption_policy)
        collection.node.add_dependency(network_policy)
        collection.node.add_dependency(data_access_policy)

        # Outputs
        CfnOutput(
            self,
            "BucketName",
            value=self.bucket_name,
        )

        CfnOutput(
            self,
            "TableName",
            value=self.table_name,
        )

        CfnOutput(
            self,
            "OpenSearchServerlessCollectionEndpoint",
            value=collection.attr_collection_endpoint,
        )

        CfnOutput(
            self,
            "OpenSearchIngestionPipelineName",
            value=self.pipeline_name,
        )

        CfnOutput(
            self,
            "OpenSearchIngestionLogGroup",
            value=self.log_group_name,
        )

        CfnOutput(
            self,
            "OpenSearchServerlessVPCId",
            value=vpc.vpc_id,
        )