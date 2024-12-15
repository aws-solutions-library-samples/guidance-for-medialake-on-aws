from aws_cdk import (
    aws_opensearchservice as opensearch,
    aws_ec2 as ec2,
    aws_logs as logs,
    Stack,
    RemovalPolicy,
    CfnOutput,
)
from constructs import Construct
from typing import Optional, List, Dict
from dataclasses import dataclass


@dataclass
class CustomVpcProps:
    vpc_name: str
    max_azs: int = 3
    nat_gateways: int = 1
    cidr: str = "10.0.0.0/16"
    enable_dns_hostnames: bool = True
    enable_dns_support: bool = True


class CustomVpc(Construct):
    def __init__(self, scope: Construct, id: str, *, props: CustomVpcProps) -> None:
        super().__init__(scope, id)

        # Default subnet configuration
        subnet_configuration = [
            ec2.SubnetConfiguration(
                name="Public", subnet_type=ec2.SubnetType.PUBLIC, cidr_mask=24
            ),
            ec2.SubnetConfiguration(
                name="Private",
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
                cidr_mask=24,
            ),
            ec2.SubnetConfiguration(
                name="Isolated",
                subnet_type=ec2.SubnetType.PRIVATE_ISOLATED,
                cidr_mask=24,
            ),
        ]

        # Create the VPC
        self.vpc = ec2.Vpc(
            self,
            "CustomVPC",
            vpc_name=props.vpc_name,
            max_azs=props.max_azs,
            nat_gateways=props.nat_gateways,
            ip_addresses=ec2.IpAddresses.cidr(props.cidr),
            enable_dns_hostnames=props.enable_dns_hostnames,
            enable_dns_support=props.enable_dns_support,
            subnet_configuration=subnet_configuration,
            gateway_endpoints={
                "S3": {"service": ec2.GatewayVpcEndpointAwsService.S3},
                "DynamoDB": {"service": ec2.GatewayVpcEndpointAwsService.DYNAMODB},
            },
        )

        # Add interface endpoints
        # self._add_interface_endpoints()

        self.vpc_id = self.vpc.vpc_id

        # def _add_interface_endpoints(self) -> None:
        # """Add VPC interface endpoints for common AWS services"""
        # self.vpc.add_interface_endpoint(
        #     "ECRDockerEndpoint", service=ec2.InterfaceVpcEndpointAwsService.ECR_DOCKER
        # )

        # self.vpc.add_interface_endpoint(
        #     "ECREndpoint", service=ec2.InterfaceVpcEndpointAwsService.ECR
        # )

        # self.vpc.add_interface_endpoint(
        #     "CloudWatchLogsEndpoint",
        #     service=ec2.InterfaceVpcEndpointAwsService.CLOUDWATCH_LOGS,
        # )

        # self.vpc.add_interface_endpoint(
        #     "SecretsManagerEndpoint",
        #     service=ec2.InterfaceVpcEndpointAwsService.SECRETS_MANAGER,
        # )

        # Create a CloudWatch Log Group for Flow Logs
        flow_log_group = logs.LogGroup(
            self,
            "VpcFlowLogGroup",
            log_group_name=f"{props.vpc_name}-flow-logs",
            retention=logs.RetentionDays.ONE_MONTH,  # Adjust retention as needed
            removal_policy=RemovalPolicy.DESTROY,  # Change as per compliance requirements
        )
        #  Enable VPC Flow Logs
        flow_log = ec2.FlowLog(
            self,
            "VpcFlowLog",
            resource_type=ec2.FlowLogResourceType.from_vpc(self.vpc),
            traffic_type=ec2.FlowLogTrafficType.ALL,  # Capture all traffic
            destination=ec2.FlowLogDestination.to_cloud_watch_logs(flow_log_group),
        )

    def get_subnet_ids(self, subnet_type: ec2.SubnetType) -> List[str]:
        """Get subnet IDs for a specific subnet type"""
        return self.vpc.select_subnets(subnet_type=subnet_type).subnet_ids
