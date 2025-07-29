import hashlib
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from aws_cdk import CfnOutput, CustomResource, RemovalPolicy, Stack
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_iam as iam
from aws_cdk import aws_logs as logs
from aws_cdk import aws_opensearchservice as opensearch
from aws_cdk import custom_resources as cr
from constructs import Construct

from config import config
from medialake_constructs.shared_constructs.lambda_base import Lambda, LambdaConfig


# Add the optional domain_endpoint property to allow importing an existing domain.
@dataclass
class OpenSearchClusterProps:
    domain_name: str

    engine_version: str = "OpenSearch_2.15"
    use_dedicated_master_nodes: bool = (
        config.resolved_opensearch_cluster_settings.use_dedicated_master_nodes
    )
    master_node_instance_type: str = (
        config.resolved_opensearch_cluster_settings.master_node_instance_type
    )
    master_node_count: int = (
        config.resolved_opensearch_cluster_settings.master_node_count
    )
    data_node_instance_type: str = (
        config.resolved_opensearch_cluster_settings.data_node_instance_type
    )
    data_node_count: int = config.resolved_opensearch_cluster_settings.data_node_count
    volume_size: int = config.resolved_opensearch_cluster_settings.data_node_volume_size
    volume_type: str = config.resolved_opensearch_cluster_settings.data_node_volume_type
    volume_iops: int = config.resolved_opensearch_cluster_settings.data_node_volume_iops
    availability_zone_count: int = (
        config.resolved_opensearch_cluster_settings.availability_zone_count
    )
    vpc: Optional[ec2.IVpc] = None
    subnet_ids: Optional[List[str]] = None
    security_group: Optional[ec2.SecurityGroup] = None
    enforce_https: bool = True
    node_to_node_encryption: bool = True
    multi_az_with_standby_enabled: bool = False
    encryption_at_rest: bool = True
    collection_indexes: List[str] = field(default_factory=lambda: ["media"])
    off_peak_window_enabled: bool = field(
        default=config.resolved_opensearch_cluster_settings.off_peak_window_enabled
    )
    off_peak_window_start: opensearch.WindowStartTime = field(
        default_factory=lambda: opensearch.WindowStartTime(
            hours=int(
                config.resolved_opensearch_cluster_settings.off_peak_window_start.split(
                    ":"
                )[0]
            ),
            minutes=int(
                config.resolved_opensearch_cluster_settings.off_peak_window_start.split(
                    ":"
                )[1]
            ),
        )
    )
    automated_snapshot_start_hour: int = field(
        default=config.resolved_opensearch_cluster_settings.automated_snapshot_start_hour
    )


def grant_opensearch_access(log_group: logs.LogGroup) -> None:
    log_group.add_to_resource_policy(
        iam.PolicyStatement(
            actions=["logs:PutLogEvents", "logs:CreateLogStream"],
            principals=[iam.ServicePrincipal("es.amazonaws.com")],
            resources=[log_group.log_group_arn],
        )
    )


class OpenSearchCluster(Construct):
    def __init__(
        self, scope: Construct, id: str, props: OpenSearchClusterProps
    ) -> None:
        super().__init__(scope, id)

        stack = Stack.of(self)
        self.region = stack.region
        self.account_id = stack.account

        if not props.vpc:
            raise ValueError("A VPC must be provided for the OpenSearch domain.")

        access_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"AWS": f"arn:aws:iam::{self.account_id}:root"},
                    "Action": "es:*",
                    "Resource": f"arn:aws:es:{stack.region}:{stack.account}:domain/{props.domain_name}/*",
                }
            ],
        }

        # Create or import OpenSearch security group
        if config.vpc.security_groups.use_existing_groups:
            os_security_group = ec2.SecurityGroup.from_security_group_id(
                self,
                "OpenSearchSG",
                security_group_id=config.vpc.security_groups.existing_groups.opensearch_sg,
            )
        else:
            os_security_group = ec2.SecurityGroup(
                self,
                "OpenSearchSG",
                vpc=props.vpc,
                security_group_name=config.vpc.security_groups.new_groups[
                    "opensearch_sg"
                ].name,
                description=config.vpc.security_groups.new_groups[
                    "opensearch_sg"
                ].description,
                allow_all_outbound=True,
            )

            if config.environment == "prod":
                os_security_group.apply_removal_policy(RemovalPolicy.RETAIN)

        os_security_group.add_ingress_rule(
            peer=props.security_group,
            connection=ec2.Port.tcp(443),
            description="Allow HTTPS access from trusted security group",
        )

        # Create IAM Role for OpenSearch audit logging
        try:
            audit_log_role = iam.Role.from_role_arn(
                self,
                "OpenSearchAuditLogRole",
                f"arn:aws:iam::{stack.account}:role/OpenSearchAuditLogRole",
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
        except Exception:
            # Role already exists
            pass

        # Create CloudWatch Log Groups and grant OpenSearch access
        app_log_group = logs.LogGroup(
            self,
            "AppLogGroup",
            retention=logs.RetentionDays.ONE_WEEK,
            removal_policy=RemovalPolicy.DESTROY,
        )
        slow_search_log_group = logs.LogGroup(
            self,
            "SlowSearchLogGroup",
            retention=logs.RetentionDays.ONE_WEEK,
            removal_policy=RemovalPolicy.DESTROY,
        )
        slow_index_log_group = logs.LogGroup(
            self,
            "SlowIndexLogGroup",
            retention=logs.RetentionDays.ONE_WEEK,
            removal_policy=RemovalPolicy.DESTROY,
        )
        for lg in (app_log_group, slow_search_log_group, slow_index_log_group):
            grant_opensearch_access(lg)

        # Configure VPC subnets if subnet IDs are provided
        vpc_subnets = None
        if props.vpc and props.subnet_ids:
            vpc_azs = props.vpc.availability_zones
            vpc_subnets = [
                ec2.Subnet.from_subnet_attributes(
                    self,
                    f"Subnet{i}",
                    subnet_id=subnet_id,
                    availability_zone=vpc_azs[i % len(vpc_azs)],
                )
                for i, subnet_id in enumerate(props.subnet_ids)
            ]

        # Import an existing domain if domain_endpoint is provided

        if config.resolved_opensearch_cluster_settings.domain_endpoint:
            # Import the existing domain using the L2 construct
            self.domain = opensearch.Domain.from_domain_endpoint(
                self,
                "ImportedDomain",
                config.resolved_opensearch_cluster_settings.domain_endpoint,
            )
            collection_endpoint = (
                config.resolved_opensearch_cluster_settings.domain_endpoint
            )
        else:
            ebs_options = opensearch.CfnDomain.EBSOptionsProperty(ebs_enabled=False)
            if not props.data_node_instance_type.lower().startswith("r7gd"):
                ebs_options = opensearch.CfnDomain.EBSOptionsProperty(
                    ebs_enabled=True,
                    volume_size=props.volume_size,
                    volume_type=props.volume_type,
                    iops=props.volume_iops,
                )

            self.domain = opensearch.CfnDomain(
                self,
                "OpenSearchDomain",
                domain_name=props.domain_name,
                engine_version=props.engine_version,
                cluster_config=opensearch.CfnDomain.ClusterConfigProperty(
                    instance_type=props.data_node_instance_type,
                    instance_count=props.data_node_count,
                    dedicated_master_enabled=props.use_dedicated_master_nodes,
                    dedicated_master_type=(
                        props.master_node_instance_type
                        if props.use_dedicated_master_nodes
                        else None
                    ),
                    dedicated_master_count=(
                        props.master_node_count
                        if props.use_dedicated_master_nodes
                        else None
                    ),
                    zone_awareness_enabled=True,
                    zone_awareness_config=opensearch.CfnDomain.ZoneAwarenessConfigProperty(
                        # Ensure availability_zone_count doesn't exceed the number of data nodes
                        availability_zone_count=min(
                            props.availability_zone_count, props.data_node_count
                        )
                    ),
                    multi_az_with_standby_enabled=props.multi_az_with_standby_enabled,
                ),
                ebs_options=ebs_options,
                vpc_options=opensearch.CfnDomain.VPCOptionsProperty(
                    subnet_ids=(
                        [subnet.subnet_id for subnet in vpc_subnets]
                        if vpc_subnets
                        else None
                    ),
                    security_group_ids=[os_security_group.security_group_id],
                ),
                encryption_at_rest_options=opensearch.CfnDomain.EncryptionAtRestOptionsProperty(
                    enabled=props.encryption_at_rest
                ),
                node_to_node_encryption_options=opensearch.CfnDomain.NodeToNodeEncryptionOptionsProperty(
                    enabled=props.node_to_node_encryption
                ),
                domain_endpoint_options=opensearch.CfnDomain.DomainEndpointOptionsProperty(
                    enforce_https=props.enforce_https
                ),
                log_publishing_options={
                    "ES_APPLICATION_LOGS": {
                        "cloudWatchLogsLogGroupArn": app_log_group.log_group_arn,
                        "enabled": True,
                    },
                    "SEARCH_SLOW_LOGS": {
                        "cloudWatchLogsLogGroupArn": slow_search_log_group.log_group_arn,
                        "enabled": True,
                    },
                    "INDEX_SLOW_LOGS": {
                        "cloudWatchLogsLogGroupArn": slow_index_log_group.log_group_arn,
                        "enabled": True,
                    },
                },
                snapshot_options=opensearch.CfnDomain.SnapshotOptionsProperty(
                    automated_snapshot_start_hour=props.automated_snapshot_start_hour
                ),
                off_peak_window_options=opensearch.CfnDomain.OffPeakWindowOptionsProperty(
                    enabled=props.off_peak_window_enabled,
                    off_peak_window=opensearch.CfnDomain.OffPeakWindowProperty(
                        window_start_time=opensearch.CfnDomain.WindowStartTimeProperty(
                            hours=props.off_peak_window_start.hours,
                            minutes=props.off_peak_window_start.minutes,
                        )
                    ),
                ),
                access_policies=access_policy,
            )
            # Retain domain on stack destroy if in prod
            if config.environment == "prod":
                self.domain.apply_removal_policy(RemovalPolicy.RETAIN)

            # For new domains, the endpoint is not available until deployment.
            collection_endpoint = f"https://{self.domain.attr_domain_endpoint}"

        # Add IAM permissions for the Lambda function to interact with OpenSearch
        # Use the appropriate ARN attribute based on whether the domain is imported.
        domain_arn = (
            self.domain.attr_arn
            if hasattr(self.domain, "attr_arn")
            else self.domain.domain_arn
        )

        should_create_index = (
            not config.resolved_opensearch_cluster_settings.domain_endpoint
        )

        if should_create_index:
            # Create Lambda function for index creation
            create_index_lambda = Lambda(
                self,
                "MediaLakeIndexCreationFunction",
                config=LambdaConfig(
                    entry="lambdas/back_end/create_os_index",
                    lambda_handler="handler",
                    vpc=props.vpc,
                    security_groups=[props.security_group],
                    timeout_minutes=1,
                    environment_variables={
                        "COLLECTION_ENDPOINT": collection_endpoint,
                        "INDEX_NAMES": ",".join(props.collection_indexes),
                        "REGION": self.region,
                        "SCOPE": "es",
                    },
                ),
            )

            create_index_lambda.function.add_to_role_policy(
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "es:ESHttpPut",
                        "es:ESHttpPost",
                        "es:ESHttpGet",
                        "es:ESHttpDelete",
                        "es:ESHttpHead",
                    ],
                    resources=[f"{domain_arn}/*"],
                )
            )
            create_index_lambda.function.add_to_role_policy(
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

            # Create a custom resource provider that triggers the Lambda for index creation
            provider = cr.Provider(
                self,
                "IndexCreateResourceProvider",
                on_event_handler=create_index_lambda.function,
                log_retention=logs.RetentionDays.ONE_WEEK,
            )

            lambda_code = Path("lambdas/back_end/create_os_index/index.py").read_text(
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
        # Only add dependency if we created a new domain.
        if not config.resolved_opensearch_cluster_settings.domain_endpoint:
            create_index_resource.node.add_dependency(self.domain)

        # Output the OpenSearch Domain endpoint (if imported, use the provided endpoint)
        domain_endpoint_output = (
            config.resolved_opensearch_cluster_settings.domain_endpoint
            if config.resolved_opensearch_cluster_settings.domain_endpoint
            else f"https://{self.domain.attr_domain_endpoint}"
        )
        CfnOutput(
            self,
            "OpenSearchDomainEndpoint",
            value=domain_endpoint_output,
            description="Endpoint of the OpenSearch Domain",
        )

    @property
    def domain_endpoint(self) -> str:
        # Return the proper endpoint regardless of whether the domain is imported.
        if hasattr(self.domain, "attr_domain_endpoint"):
            return f"https://{self.domain.attr_domain_endpoint}"
        else:
            return self.domain.domain_endpoint

    @property
    def domain_arn(self) -> str:
        if hasattr(self.domain, "attr_arn"):
            return self.domain.attr_arn
        else:
            # Remove 'vpc-' prefix if it exists
            domain_name = self.domain.domain_name
            if domain_name.startswith("vpc-"):
                domain_name = domain_name[4:]
            return f"arn:aws:es:{self.region}:{self.account_id}:domain/{domain_name}"

    @property
    def opensearch_instance(self) -> opensearch.CfnDomain:
        return self.domain
