from aws_cdk import (
    aws_opensearchservice as opensearch,
    aws_ec2 as ec2,
    Stack,
    RemovalPolicy,
    CfnOutput,
)
from constructs import Construct
from typing import Optional, List, Dict


class OpenSearchCluster(Construct):
    def __init__(
        self,
        scope: Construct,
        id: str,
        *,
        domain_name: str,
        engine_version: str = "OpenSearch_1.3",
        instance_type: str = "r6g.large.search",
        instance_count: int = 3,
        volume_size: int = 20,
        availability_zone_count: int = 3,
        vpc: Optional[ec2.IVpc] = None,
        enforce_https: bool = True,
        node_to_node_encryption: bool = True,
        encryption_at_rest: bool = True
    ) -> None:
        super().__init__(scope, id)

        # Create the OpenSearch Domain
        self.domain = opensearch.Domain(
            self,
            "OpenSearchDomain",
            domain_name=domain_name,
            version=opensearch.EngineVersion.of(engine_version),
            # Capacity configuration
            capacity={
                "data_nodes": instance_count,
                "data_node_instance_type": instance_type,
            },
            # EBS configuration
            ebs={
                "volume_size": volume_size,
                "volume_type": ec2.EbsDeviceVolumeType.GP3,
            },
            # Zone awareness configuration
            zone_awareness={"availability_zone_count": availability_zone_count},
            # Security configuration
            enforce_https=enforce_https,
            node_to_node_encryption=node_to_node_encryption,
            encryption_at_rest={"enabled": encryption_at_rest},
            # Logging configuration
            logging={
                "slow_search_log_enabled": True,
                "app_log_enabled": True,
                "slow_index_log_enabled": True,
            },
            # VPC configuration
            vpc=vpc,
            vpc_subnets=(
                vpc.select_subnets(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS)
                if vpc
                else None
            ),
            # Advanced options
            advanced_options={
                "rest.action.multi.allow_explicit_index": "true",
                "indices.fielddata.cache.size": "25",
                "indices.query.bool.max_clause_count": "2048",
            },
            removal_policy=RemovalPolicy.DESTROY,
        )
