from aws_cdk import (
    aws_ec2 as ec2,
    aws_logs as logs,
    RemovalPolicy,
)
from constructs import Construct
from typing import Optional, Dict, List
from dataclasses import dataclass
from aws_lambda_powertools import Logger

# Import your CDK configuration to check the environment
from config import config

logger = Logger()


@dataclass
class CustomVpcProps:
    use_existing_vpc: bool
    existing_vpc: Optional[Dict[str, any]] = None
    new_vpc: Optional[Dict[str, any]] = None


class CustomVpc(Construct):
    def __init__(self, scope: Construct, id: str, *, props: CustomVpcProps) -> None:
        super().__init__(scope, id)
        self.props = props

        if self.props.use_existing_vpc:
            if not self.props.existing_vpc:
                raise ValueError("Existing VPC configuration is missing")

            vpc_id = self.props.existing_vpc.vpc_id
            subnet_ids = self.props.existing_vpc.subnet_ids
            vpc_cidr = self.props.existing_vpc.vpc_cidr

            # Determine the number of AZs based on the number of public subnets
            num_azs = len(subnet_ids.get("public", []))
            logger.info(f"Using existing VPC: {vpc_id}")
            logger.info(f"Public subnets: {subnet_ids.get('public', [])[:num_azs]}")
            logger.info(f"Private subnets: {subnet_ids.get('private', [])[:num_azs]}")
            logger.info(f"CIDR: {vpc_cidr}")

            self.vpc = ec2.Vpc.from_vpc_attributes(
                self,
                "ExistingVPC",
                vpc_id=vpc_id,
                availability_zones=scope.availability_zones[:num_azs],
                private_subnet_ids=subnet_ids.get("private", [])[:num_azs],
                public_subnet_ids=subnet_ids.get("public", []),
                vpc_cidr_block=vpc_cidr,
            )
        else:
            if not self.props.new_vpc:
                raise ValueError("New VPC configuration is missing")

            new_vpc_config = self.props.new_vpc
            subnet_configuration = [
                ec2.SubnetConfiguration(
                    name="Public",
                    subnet_type=ec2.SubnetType.PUBLIC,
                    cidr_mask=24,
                ),
                ec2.SubnetConfiguration(
                    name="Private",
                    subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
                    cidr_mask=24,
                ),
            ]

            self.vpc = ec2.Vpc(
                self,
                "CustomVPC",
                vpc_name=new_vpc_config.vpc_name,
                max_azs=new_vpc_config.max_azs,
                nat_gateways=1,
                ip_addresses=ec2.IpAddresses.cidr(new_vpc_config.cidr),
                enable_dns_hostnames=new_vpc_config.enable_dns_hostnames,
                enable_dns_support=new_vpc_config.enable_dns_support,
                subnet_configuration=subnet_configuration,
                gateway_endpoints={
                    "S3": {"service": ec2.GatewayVpcEndpointAwsService.S3},
                    "DynamoDB": {"service": ec2.GatewayVpcEndpointAwsService.DYNAMODB},
                },
            )

            # If the environment is prod, apply a retention policy to the VPC.
            if config.environment == "prod":
                self.vpc.apply_removal_policy(RemovalPolicy.RETAIN)
                for subnet in self.vpc.public_subnets + self.vpc.private_subnets:
                    subnet.apply_removal_policy(RemovalPolicy.RETAIN)

        self.vpc_id = self.vpc.vpc_id

        # Create a CloudWatch Log Group for Flow Logs
        flow_log_group = logs.LogGroup(
            self,
            "VpcFlowLogGroup",
            log_group_name=f"{self.vpc.vpc_id}-flow-logs",
            retention=logs.RetentionDays.ONE_MONTH,
            removal_policy=RemovalPolicy.DESTROY,
        )

        # Enable VPC Flow Logs
        ec2.FlowLog(
            self,
            "VpcFlowLog",
            resource_type=ec2.FlowLogResourceType.from_vpc(self.vpc),
            traffic_type=ec2.FlowLogTrafficType.ALL,
            destination=ec2.FlowLogDestination.to_cloud_watch_logs(flow_log_group),
        )

    def get_subnet_ids(self, subnet_type: ec2.SubnetType) -> List[Dict[str, str]]:
        """Get subnet IDs and their availability zones for a specific subnet type"""
        try:
            if self.props.use_existing_vpc:
                subnet_ids = self.props.existing_vpc["subnet_ids"]
                if subnet_type == ec2.SubnetType.PRIVATE_WITH_EGRESS:
                    return [
                        {"subnet_id": subnet_id, "az": "unknown"}
                        for subnet_id in subnet_ids["private"]
                    ]
                elif subnet_type == ec2.SubnetType.PUBLIC:
                    return [
                        {"subnet_id": subnet_id, "az": "unknown"}
                        for subnet_id in subnet_ids["public"]
                    ]
            else:
                if isinstance(self.vpc, ec2.Vpc):
                    subnets = self.vpc.select_subnets(subnet_type=subnet_type).subnets
                    return [
                        {"subnet_id": subnet.subnet_id, "az": subnet.availability_zone}
                        for subnet in subnets
                    ]
                elif isinstance(self.vpc, ec2.IVpc):
                    if subnet_type == ec2.SubnetType.PRIVATE_WITH_EGRESS:
                        return [
                            {
                                "subnet_id": subnet.subnet_id,
                                "az": subnet.availability_zone,
                            }
                            for subnet in self.vpc.private_subnets
                        ]
                    elif subnet_type == ec2.SubnetType.PUBLIC:
                        return [
                            {
                                "subnet_id": subnet.subnet_id,
                                "az": subnet.availability_zone,
                            }
                            for subnet in self.vpc.public_subnets
                        ]
            return []
        except Exception as e:
            print(f"Error getting subnet IDs: {e}")
            return []
