import json
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from aws_cdk import CustomResource, RemovalPolicy, Stack
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_iam as iam
from aws_cdk import aws_logs as logs
from aws_cdk import aws_opensearchservice as opensearch
from aws_cdk import aws_s3 as s3
from aws_cdk import custom_resources as cr
from constructs import Construct

from config import config
from medialake_constructs.shared_constructs.lambda_base import Lambda, LambdaConfig


@dataclass
class OpenSearchIngestionPipelineProps:

    asset_table: dynamodb.TableV2
    opensearch_cluster: opensearch
    index_name: str
    ddb_export_bucket: s3.Bucket
    access_logs_bucket: Optional[s3.Bucket] = None
    vpc: Optional[ec2.Vpc] = None
    security_group: Optional[ec2.SecurityGroup] = None


class OpenSearchIngestionPipeline(Construct):

    def __init__(
        self,
        scope: Construct,
        id: str,
        props: OpenSearchIngestionPipelineProps,
    ) -> None:
        super().__init__(scope, id)

        # Determine the current stack
        stack = Stack.of(self)

        # Get the region and account ID
        self.region = stack.region
        self.account_id = stack.account

        # self.create_service_linked_roles()
        # self.update_log_delivery_policy()

        # Define the physical name
        log_group_name = f"/aws/vendedlogs/MediaLakeOpenSearchIngestion-{config.environment}-{self.region}-{self.account_id}"

        ingestion_log_group = logs.LogGroup(
            self,
            "IngestionPipelineLogGroup",
            log_group_name=log_group_name,
            removal_policy=RemovalPolicy.DESTROY,
            retention=logs.RetentionDays.ONE_DAY,
        )

        # Manually compute the ARN
        log_group_arn = f"arn:aws:logs:{self.region}:{Stack.of(self).account}:log-group:{log_group_name}"

        ingestion_log_group.add_to_resource_policy(
            iam.PolicyStatement(
                sid="AllowLogDelivery",
                effect=iam.Effect.ALLOW,
                principals=[iam.ServicePrincipal("delivery.logs.amazonaws.com")],
                actions=["logs:CreateLogStream", "logs:PutLogEvents"],
                resources=[f"{log_group_arn}:*"],
            )
        )

        # OS ingest pipeline
        ingestion_pipeline_lambda = Lambda(
            self,
            "AssetTableIngestionPipeline",
            config=LambdaConfig(
                name=f"{config.resource_prefix}-os-pipeline-creator-{config.environment}",
                timeout_minutes=15,
                # vpc=props.vpc.vpc,
                # security_groups=[props.security_group],
                entry="lambdas/back_end/asset_table_ingestion_pipline",
                environment_variables={
                    "TABLE_ARN": props.asset_table.table_arn,
                    "BUCKET_NAME": props.ddb_export_bucket.bucket.bucket_name,
                    "COLLECTION_ENDPOINT": props.opensearch_cluster.domain_endpoint,
                    "INDEX_NAME": props.index_name,
                    "REGION": self.region,
                    "LOG_GROUP_NAME": ingestion_log_group.log_group_name,
                    "PIPELINE_NAME": f"{config.resource_prefix}-etl-pipeline",
                    "SUBNET_IDS_PIPELINE": json.dumps(
                        props.vpc.vpc.select_subnets(
                            subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
                        ).subnet_ids
                    ),
                    "SECURITY_GROUP_IDS": json.dumps(
                        [props.security_group.security_group_id]
                    ),
                },
            ),
        )

        ddb_pipeline_cr_role = ingestion_pipeline_lambda.lambda_role

        pipeline_role = iam.Role(
            self,
            "IngestionRole",
            assumed_by=iam.ServicePrincipal("osis-pipelines.amazonaws.com"),
        )
        # es permissions
        pipeline_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["es:ESHttp*"],
                resources=[f"{props.opensearch_cluster.domain_arn}/*"],
            )
        )

        pipeline_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["es:DescribeDomain"],
                resources=[f"arn:aws:es:*:{self.account_id}:domain/*"],
            )
        )

        pipeline_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "dynamodb:DescribeTable",
                    "dynamodb:DescribeContinuousBackups",
                    "dynamodb:ExportTableToPointInTime",
                    "dynamodb:DescribeStream",
                ],
                resources=[
                    props.asset_table.table_arn,
                ],
            )
        )

        pipeline_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "kms:Encrypt",
                    "kms:Decrypt",
                    "kms:ReEncrypt*",
                    "kms:GenerateDataKey*",
                    "kms:DescribeKey",
                ],
                resources=["*"],
            )
        )

        pipeline_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "dynamodb:GetRecords",
                    "dynamodb:GetShardIterator",
                    "dynamodb:DescribeStream",
                ],
                resources=[f"{props.asset_table.table_arn}/stream/*"],
            )
        )

        pipeline_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["dynamodb:DescribeExport"],
                resources=[f"{props.asset_table.table_arn}/export/*"],
            )
        )

        pipeline_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "s3:GetObject",
                    "s3:PutObject",
                    "s3:DeleteObject",
                    "s3:DeleteObjectVersion",
                    "s3:ListBucket",
                    "s3:DeleteBucket",
                ],
                resources=[
                    props.ddb_export_bucket.bucket_arn,
                    f"{props.ddb_export_bucket.bucket_arn}/*",
                ],
            )
        )

        ingestion_pipeline_lambda.function.add_environment(
            "PIPELINE_ROLE_ARN", pipeline_role.role_arn
        )

        # osis permission
        ddb_pipeline_cr_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "osis:CreatePipeline",
                    "osis:ValidatePipeline",
                ],
                resources=[
                    f"arn:aws:osis:{self.region}:{self.account_id}:pipeline/{config.resource_prefix}-etl-pipeline"
                ],
            )
        )

        ddb_pipeline_cr_role.add_to_policy(
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

        ddb_pipeline_cr_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "logs:CreateLogStream",
                    "logs:PutLogEvents",
                ],
                resources=[
                    f"arn:aws:logs:{self.region}:{self.account_id}:log-group:{ingestion_log_group.log_group_name}:*"
                ],
            )
        )

        ddb_pipeline_cr_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents",
                    "logs:DescribeLogGroups",
                ],
                resources=[
                    f"arn:aws:logs:{self.region}:{self.account_id}:log-group:/aws/vendedlogs/MediaLakeOpenSearchIngestion-*"
                ],
            )
        )

        ddb_pipeline_cr_role.add_to_policy(
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
                resources=[
                    "*"
                ],  # These actions typically require '*' as they operate across all log groups
            )
        )

        ddb_pipeline_cr_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["iam:ListPolicies"],
                resources=["*"],
                # These actions typically require '*' as they operate across all log groups
            )
        )

        ddb_pipeline_cr_role.add_to_policy(
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
                resources=[f"arn:aws:iam::{self.account_id}:policy/*"],
            )
        )

        ingestion_pipeline_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "s3:GetBucketLocation",
                    "s3:ListBucket",
                ],
                resources=[props.ddb_export_bucket.bucket.bucket_arn],
            )
        )

        ingestion_pipeline_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "s3:GetObject",
                    "s3:PutObject",
                    "s3:DeleteObject",
                ],
                resources=[f"{props.ddb_export_bucket.bucket.bucket_arn}/*"],
            )
        )
        ingestion_pipeline_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "ec2:CreateNetworkInterface",
                    "ec2:DescribeNetworkInterfaces",
                    "ec2:DeleteNetworkInterface",
                ],
                resources=["*"],
                # These actions typically require '*' as they operate across all log groups
            )
        )

        ddb_pipeline_cr_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "ec2:CreateVpcEndpoint",
                    "ec2:DeleteVpcEndpoints",
                    "ec2:ListVpcEndpoints",
                    "ec2:DescribeVpcEndpoints",
                    "ec2:DescribeVpcs",
                    "ec2:DescribeSubnets",
                    "ec2:DescribeSecurityGroups",
                    "ec2:CreateTags",
                    "ec2:DeleteTags",
                ],
                resources=[f"arn:aws:ec2:{self.region}:{self.account_id}:*"],
            )
        )

        ddb_pipeline_cr_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "route53:AssociateVPCWithHostedZone",
                    "route53:DisassociateVPCFromHostedZone",
                ],
                resources=[f"arn:aws:route53:::hostedzone/*"],
            )
        )

        ddb_pipeline_cr_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["osis:Ingest"],
                resources=[
                    f"arn:aws:osis:{self.region}:{self.account_id}:pipeline/{config.resource_prefix}-etl-pipeline"
                ],
            )
        )

        ingestion_pipeline_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "opensearch:CreateDomain",
                    "opensearch:DeleteDomain",
                    "opensearch:DescribeDomain",
                ],
                resources=[
                    f"arn:aws:opensearch:{self.region}:{self.account_id}:domain/*"
                ],
            )
        )

        ingestion_pipeline_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "osis:GetPipeline",
                    "osis:CreatePipeline",
                    "osis:DeletePipeline",
                ],
                resources=[
                    f"arn:aws:osis:{self.region}:{self.account_id}:pipeline/{config.resource_prefix}-etl-pipeline"
                ],
            )
        )

        # Define Custom Resource for Ingestion Pipeline
        ingestion_provider = cr.Provider(
            self,
            "IngestionProvider",
            on_event_handler=ingestion_pipeline_lambda.function,
        )

        ingestion_custom_resource = CustomResource(
            self,
            "CreateIngestionPipeline",
            service_token=ingestion_provider.service_token,
            removal_policy=RemovalPolicy.DESTROY,
            properties={
                "PipelineName": f"{config.resource_prefix}-asset-pipeline",
                "TableArn": props.asset_table.table_arn,
                "BucketName": props.ddb_export_bucket.bucket.bucket_arn,
                "CollectionEndpoint": props.opensearch_cluster.domain_endpoint,
                "PipelineRoleArn": pipeline_role.role_arn,
                "Region": self.region,
                "LogGroupName": ingestion_log_group.log_group_name,
                "SubnetIdsPipeline": json.dumps(
                    props.vpc.vpc.select_subnets(
                        subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
                    ).subnet_ids
                ),
                "SecurityGroupIds": json.dumps(
                    [props.security_group.security_group_id]
                ),
                "Timestamp": datetime.now().isoformat(),
            },
        )
        # Ensure the ingestion pipeline is created after the DynamoDB table is populated
        ingestion_custom_resource.node.add_dependency(props.asset_table)
        ingestion_custom_resource.node.add_dependency(pipeline_role)

    # def update_log_delivery_policy(self):
    #     new_resource_arn = f"arn:aws:logs:{self.region}:{self.account_id}:log-group:/aws/vendedlogs/MediaLakeOpenSearchIngestion-{config.environment}-{self.region}-{self.account_id}:log-stream:*"

    #     # Construct the policy document using Fn.join and other intrinsic functions
    #     policy_document = {
    #         "Fn::Transform": {
    #             "Name": "String",
    #             "Parameters": {
    #                 "InputString": Fn.join(
    #                     "",
    #                     [
    #                         '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"delivery.logs.amazonaws.com"},"Action":["logs:CreateLogStream","logs:PutLogEvents"],"Resource":',
    #                         Fn.join(
    #                             ",",
    #                             [
    #                                 Fn.join(
    #                                     "",
    #                                     [
    #                                         "[",
    #                                         Fn.join(
    #                                             ",",
    #                                             cr.JsonPath.parse_json("$.Policy")[
    #                                                 "Statement"
    #                                             ][0]["Resource"],
    #                                         ),
    #                                         ",",
    #                                         f'"{new_resource_arn}"',
    #                                         "]",
    #                                     ],
    #                                 )
    #                             ],
    #                         ),
    #                         ',"Condition":{"StringEquals":{"aws:SourceAccount":"',
    #                         self.account_id,
    #                         '"},"ArnLike":{"aws:SourceArn":"arn:aws:logs:',
    #                         self.region,
    #                         ":",
    #                         self.account_id,
    #                         ':*"}}}]}',
    #                     ],
    #                 ),
    #                 "Operation": "REPLACE",
    #             },
    #         }
    #     }

    #     cr.AwsCustomResource(
    #         self,
    #         "UpdateLogDeliveryPolicy",
    #         on_create=cr.AwsSdkCall(
    #             service="CloudWatchLogs",
    #             action="getResourcePolicy",
    #             parameters={"policyName": "AWSLogDeliveryWrite20150319"},
    #             physical_resource_id=cr.PhysicalResourceId.of("GetLogDeliveryPolicy"),
    #         ),
    #         on_update=cr.AwsSdkCall(
    #             service="CloudWatchLogs",
    #             action="putResourcePolicy",
    #             parameters={
    #                 "policyName": "AWSLogDeliveryWrite20150319",
    #                 "policyDocument": policy_document,
    #             },
    #             physical_resource_id=cr.PhysicalResourceId.of(
    #                 "UpdateLogDeliveryPolicy"
    #             ),
    #         ),
    #         policy=cr.AwsCustomResourcePolicy.from_sdk_calls(
    #             resources=cr.AwsCustomResourcePolicy.ANY_RESOURCE
    #         ),
    #     )

    def create_service_linked_roles(self):
        for service in [
            # "es.amazonaws.com",
            "opensearchservice.amazonaws.com",
            "osis.amazonaws.com",
        ]:
            cr.AwsCustomResource(
                self,
                f'ServiceLinkedRole{service.split(".")[0].capitalize()}',
                on_create=cr.AwsSdkCall(
                    service="IAM",
                    action="createServiceLinkedRole",
                    parameters={"AWSServiceName": service},
                    physical_resource_id=cr.PhysicalResourceId.of(
                        f"ServiceLinkedRole{service}"
                    ),
                ),
                policy=cr.AwsCustomResourcePolicy.from_sdk_calls(
                    resources=cr.AwsCustomResourcePolicy.ANY_RESOURCE
                ),
            )

    @property
    def ddb_export_bucket(self) -> s3.IBucket:
        """
        Returns the access log bucket.

        Returns:
            s3.IBucket: S3 bucket object
        """
        return self.ddb_export_bucket.bucket
