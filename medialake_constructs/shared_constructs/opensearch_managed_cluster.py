from aws_cdk import (
    Stack,
    aws_iam as iam,
    aws_lambda as lambda_,
    aws_opensearchservice as opensearch,
    aws_ec2 as ec2,
    CustomResource,
    custom_resources as cr,
    aws_logs as logs,
    Duration,
    RemovalPolicy,
    CfnOutput,
)
import hashlib
from config import config
from constructs import Construct
from typing import Optional, List
from dataclasses import dataclass, field
from aws_cdk.aws_lambda_python_alpha import PythonLayerVersion
from pathlib import Path

import time


@dataclass
class OpenSearchClusterProps:
    domain_name: str
    engine_version: str = opensearch.EngineVersion.OPENSEARCH_2_15
    master_node_instance_type: str = (
        config.opensearch_cluster_settings.master_node_instance_type
    )
    master_node_count: int = config.opensearch_cluster_settings.master_node_count
    data_node_instance_type: str = (
        config.opensearch_cluster_settings.data_node_instance_type
    )
    data_node_count: int = config.opensearch_cluster_settings.data_node_count
    volume_size: int = config.opensearch_cluster_settings.data_node_volume_size
    volume_type: str = config.opensearch_cluster_settings.data_node_volume_type
    volume_iops: int = config.opensearch_cluster_settings.data_node_volume_iops
    availability_zone_count: int = (
        config.opensearch_cluster_settings.availability_zone_count
    )
    vpc: Optional[ec2.IVpc] = None
    subnet_ids: Optional[List[str]] = None
    security_group: Optional[ec2.SecurityGroup] = None
    enforce_https: bool = True
    node_to_node_encryption: bool = True
    multi_az_with_standby_enabled: bool = False
    encryption_at_rest: bool = True
    collection_indexes: List[str] = field(default_factory=lambda: ["media"])
    off_peak_window_enabled: bool = True
    off_peak_window_start: opensearch.WindowStartTime = field(
        default_factory=lambda: opensearch.WindowStartTime(hours=20, minutes=0)
    )


# @dataclass
# class OpenSearchClusterProps:
#     domain_name: str
#     engine_version: str = opensearch.EngineVersion.OPENSEARCH_2_15
#     instance_type: str = (
#         "c5.large.search"  # T3 instance type does not support Multi-AZ with standby feature.
#     )
#     instance_count: int = 2  # high availability
#     volume_size: int = 30
#     availability_zone_count: int = 2  #  2 for cross-zone replication
#     vpc: Optional[ec2.IVpc] = None
#     security_group: Optional[ec2.SecurityGroup] = None
#     enforce_https: bool = True
#     node_to_node_encryption: bool = True
#     encryption_at_rest: bool = True
#     master_node_instance_type: str = "c5.large.search"
#     master_node_count: int = 3  # Typically, 3 master nodes for production
#     collection_indexes: List[str] = field(default_factory=lambda: ["media"])
#     off_peak_window_enabled: bool = True
#     off_peak_window_start: opensearch.WindowStartTime = field(
#         default_factory=lambda: opensearch.WindowStartTime(hours=20, minutes=0)
#     )


class OpenSearchCluster(Construct):
    def __init__(
        self,
        scope: Construct,
        id: str,
        props: OpenSearchClusterProps,
    ) -> None:
        super().__init__(scope, id)

        # Determine the current stack
        stack = Stack.of(self)

        # Get the region and account ID
        self.region = stack.region
        self.account_id = stack.account

        # Ensure VPC is provided
        if not props.vpc:
            raise ValueError("A VPC must be provided for the OpenSearch domain.")

        # Define Access Policy
        access_policy = iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            principals=[
                iam.ServicePrincipal("es.amazonaws.com"),
            ],
            actions=[
                "es:ESHttpPut",
                "es:ESHttpPost",
                "es:ESHttpGet",
                "es:ESHttpDelete",
                "es:ESHttpHead",
            ],
            resources=[
                f"arn:aws:es:{stack.region}:{stack.account}:domain/{props.domain_name}",
                f"arn:aws:es:{stack.region}:{stack.account}:domain/{props.domain_name}/*",  # Include if specific resources are not feasible
            ],
        )

        # Create a Security Group with restricted access
        os_security_group = ec2.SecurityGroup(
            self,
            "OpenSearchSG",
            vpc=props.vpc,
            description="Allow limited access to OpenSearch",
            allow_all_outbound=True,
        )

        os_security_group.add_ingress_rule(
            peer=props.security_group,
            connection=ec2.Port.tcp(443),
            description="Allow HTTPS access from trusted security group",
        )

        # Create IAM Role for OpenSearch to publish audit logs to CloudWatch
        audit_log_role = iam.Role(
            self,
            "OpenSearchAuditLogRole",
            assumed_by=iam.ServicePrincipal("es.amazonaws.com"),
        )

        audit_log_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents",
                ],
                resources=[
                    f"arn:aws:logs:{stack.region}:{stack.account}:log-group:/aws/opensearch/{props.domain_name}:*"
                ],
            )
        )

        # Define Audit Log Group
        audit_log_group = logs.LogGroup(
            self,
            "AuditLogGroup",
            retention=logs.RetentionDays.ONE_WEEK,
            removal_policy=RemovalPolicy.DESTROY,
        )

        # VPC configuration
        vpc_subnets = None
        if props.vpc and props.subnet_ids:
            # Get the availability zones for the VPC
            vpc_azs = props.vpc.availability_zones

            # Create subnet references with availability zones
            vpc_subnets = [
                ec2.Subnet.from_subnet_attributes(
                    self,
                    f"Subnet{i}",
                    subnet_id=subnet_id,
                    availability_zone=vpc_azs[i % len(vpc_azs)],
                )
                for i, subnet_id in enumerate(props.subnet_ids)
            ]

        # Define OpenSearch Domain
        self.domain = opensearch.Domain(
            self,
            "OpenSearchDomain",
            domain_name=props.domain_name,
            version=props.engine_version,
            # Capacity configuration
            capacity=opensearch.CapacityConfig(
                multi_az_with_standby_enabled=props.multi_az_with_standby_enabled,
                data_nodes=props.data_node_count,
                data_node_instance_type=props.data_node_instance_type,
                master_nodes=props.master_node_count,
                master_node_instance_type=props.master_node_instance_type,
            ),
            # EBS configuration
            ebs=opensearch.EbsOptions(
                volume_size=props.volume_size,
                volume_type=ec2.EbsDeviceVolumeType[props.volume_type.upper()],
                iops=props.volume_iops,
                # throughput=125, # for GP3
                # iops=3000,
            ),
            # Zone awareness configuration for cross-zone replication
            zone_awareness=opensearch.ZoneAwarenessConfig(
                enabled=True, availability_zone_count=props.availability_zone_count
            ),
            # Security configuration
            enforce_https=props.enforce_https,
            node_to_node_encryption=props.node_to_node_encryption,
            encryption_at_rest=opensearch.EncryptionAtRestOptions(
                enabled=props.encryption_at_rest,
            ),
            # Logging configuration
            logging=opensearch.LoggingOptions(
                slow_search_log_enabled=True,
                app_log_enabled=True,
                slow_index_log_enabled=True,
                app_log_group=logs.LogGroup(
                    self,
                    "AppLogGroup",
                    retention=logs.RetentionDays.ONE_WEEK,
                    removal_policy=RemovalPolicy.DESTROY,
                ),
                slow_search_log_group=logs.LogGroup(
                    self,
                    "SlowSearchLogGroup",
                    retention=logs.RetentionDays.ONE_WEEK,
                    removal_policy=RemovalPolicy.DESTROY,
                ),
                slow_index_log_group=logs.LogGroup(
                    self,
                    "SlowIndexLogGroup",
                    retention=logs.RetentionDays.ONE_WEEK,
                    removal_policy=RemovalPolicy.DESTROY,
                ),
            ),
            # VPC configuration
            # vpc=props.vpc,
            # vpc_subnets=[
            #     ec2.SubnetSelection(
            #         subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
            #         availability_zones=[
            #             props.vpc.select_subnets(
            #                 subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
            #             )
            #             .subnets[0]
            #             .availability_zone,
            #             props.vpc.select_subnets(
            #                 subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
            #             )
            #             .subnets[1]
            #             .availability_zone,
            #         ],
            #     )
            # ],
            # security_groups=[os_security_group],
            vpc=props.vpc,
            vpc_subnets=(
                [ec2.SubnetSelection(subnets=vpc_subnets)] if vpc_subnets else None
            ),
            security_groups=[os_security_group] if props.vpc else None,
            # Access Policy added here
            access_policies=[access_policy],
            # Maintenance window (off-peak)
            off_peak_window_enabled=props.off_peak_window_enabled,
            off_peak_window_start=props.off_peak_window_start,
            # Advanced options
            advanced_options={
                "rest.action.multi.allow_explicit_index": "true",
                "indices.fielddata.cache.size": "25",
                "indices.query.bool.max_clause_count": "2048",
            },
            removal_policy=RemovalPolicy.DESTROY,
            # Automatic upgrades
            enable_auto_software_update=True,
        )

        # Create a service-linked role if it doesn't exist
        slr = iam.CfnServiceLinkedRole(
            self, "ServiceLinkedRole", aws_service_name="es.amazonaws.com"
        )

        # Ensure the service-linked role is created before the domain
        self.domain.node.add_dependency(slr)

        # Create Lambda function for index creation
        create_indexlambda_ = lambda_.Function(
            self,
            "IndexCreationFunction",
            runtime=lambda_.Runtime.PYTHON_3_13,
            handler="index.handler",
            vpc=props.vpc,
            security_groups=[props.security_group],
            code=lambda_.Code.from_asset("lambdas/back_end/create_oss_index/"),
            timeout=Duration.seconds(60),
            environment={
                "COLLECTION_ENDPOINT": f"https://{self.domain.domain_endpoint}",
                "INDEX_NAMES": ",".join(props.collection_indexes),
                "REGION": self.region,
                "SCOPE": "es",
            },
        )

        # Define a Lambda Layer for dependencies
        layer = PythonLayerVersion(
            self,
            "RequestsLayer",
            entry="lambdas/back_end/create_oss_index",
            compatible_runtimes=[lambda_.Runtime.PYTHON_3_13],
            compatible_architectures=[
                lambda_.Architecture.ARM_64,
                lambda_.Architecture.X86_64,
            ],
        )

        create_indexlambda_.add_layers(layer)

        # Define IAM permission policy for the Lambda function
        create_indexlambda_.role.add_to_principal_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "es:ESHttpPut",
                    "es:ESHttpPost",
                    "es:ESHttpGet",
                    "es:ESHttpDelete",
                    "es:ESHttpHead",
                ],
                resources=[f"{self.domain.domain_arn}/*"],
            )
        )

        # Allow the Lambda function to access the OpenSearch domain
        self.domain.grant_read_write(create_indexlambda_)

        # Create a custom resource that uses the Lambda
        provider = cr.Provider(
            self,
            "IndexCreateResourceProvider",
            on_event_handler=create_indexlambda_,
            log_retention=logs.RetentionDays.ONE_WEEK,
        )

        # Optionally, include a code hash for triggering updates
        lambda_code = Path("lambdas/back_end/create_oss_index/index.py").read_text(
            encoding="utf-8"
        )
        code_hash = hashlib.sha256(lambda_code.encode()).hexdigest()

        create_index_resource = CustomResource(
            self,
            "IndexCreateResource",
            service_token=provider.service_token,
            properties={
                "code_hash": code_hash,
                "timestamp": str(int(time.time())),
            },
            resource_type="Custom::OpenSearchCreateIndex",
        )

        create_index_resource.node.add_dependency(self.domain)

        # Output the Domain Endpoint
        CfnOutput(
            self,
            "OpenSearchDomainEndpoint",
            value=self.domain.domain_endpoint,
            description="Endpoint of the OpenSearch Domain",
        )

    @property
    def domain_endpoint(self) -> str:
        return f"https://{self.domain.domain_endpoint}"

    @property
    def domain_arn(self) -> str:
        return self.domain.domain_arn

    @property
    def opensearch_instance(self) -> opensearch.Domain:
        return self.domain
