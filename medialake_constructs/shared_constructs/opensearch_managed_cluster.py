from aws_cdk import (
    aws_opensearchservice as opensearch,
    aws_ec2 as ec2,
    Stack,
    RemovalPolicy,
    CfnOutput,
)
from constructs import Construct
from typing import Optional, List, Dict
from dataclasses import dataclass


@dataclass
class OpenSearchClusterProps:
    domain_name: str
    engine_version: str = "OpenSearch_2.11"
    instance_type: str = "t2.medium.search"
    instance_count: int = 1
    volume_size: int = 20
    availability_zone_count: int = 1
    vpc: Optional[ec2.IVpc] = None
    enforce_https: bool = True
    node_to_node_encryption: bool = True
    encryption_at_rest: bool = True
    master_node_instance_type: str = "t2.medium.search"
    master_node_count: int = 1


class OpenSearchCluster(Construct):
    def __init__(
        self,
        scope: Construct,
        id: str,
        *,
        props: OpenSearchClusterProps,
    ) -> None:
        super().__init__(scope, id)

        # Create the OpenSearch Domain
        self.domain = opensearch.Domain(
            self,
            "OpenSearchDomain",
            domain_name=props.domain_name,
            version=opensearch.EngineVersion.OPENSEARCH_2_15,
            # Capacity configuration
            capacity={
                "data_nodes": props.instance_count,
                "data_node_instance_type": props.instance_type,
                # "master_nodes": props.master_node_count,
                # "master_node_instance_type": props.master_node_instance_type,
                "multi_az_with_standby_enabled": False,
            },
            # EBS configuration
            ebs={
                "volume_size": props.volume_size,
                "volume_type": ec2.EbsDeviceVolumeType.GP2,
            },
            # Zone awareness configuration
            # zone_awareness={"availability_zone_count": props.availability_zone_count},
            # Security configuration
            enforce_https=props.enforce_https,
            # node_to_node_encryption=props.node_to_node_encryption,
            # encryption_at_rest={"enabled": props.encryption_at_rest},
            # Logging configuration
            logging={
                "slow_search_log_enabled": True,
                "app_log_enabled": True,
                "slow_index_log_enabled": True,
            },
            # VPC configuration
            # vpc=props.vpc,
            # vpc_subnets=(
            #     [
            #         ec2.SubnetSelection(
            #             subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
            #             availability_zones=props.vpc.availability_zones[
            #                 : props.availability_zone_count
            #             ],
            #         )
            #     ]
            #     if props.vpc
            #     else None
            # ),
            # Advanced options
            advanced_options={
                "rest.action.multi.allow_explicit_index": "true",
                "indices.fielddata.cache.size": "25",
                "indices.query.bool.max_clause_count": "2048",
            },
            removal_policy=RemovalPolicy.DESTROY,
        )
