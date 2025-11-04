from dataclasses import dataclass
from typing import Dict, List, Optional

from aws_cdk import RemovalPolicy
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_logs as logs
from constructs import Construct

# Import the CDK logger instead of aws_lambda_powertools
from cdk_logger import get_logger

logger = get_logger("VPC")


@dataclass
class CustomVpcProps:
    use_existing_vpc: bool
    existing_vpc: Optional[Dict[str, any]] = None
    new_vpc: Optional[Dict[str, any]] = None


class CustomVpc(Construct):
    def __init__(self, scope: Construct, id: str, *, props: CustomVpcProps) -> None:
        super().__init__(scope, id)
        self.props = props

        logger.debug(f"Initializing CustomVpc with id: {id}")

        if self.props.use_existing_vpc:
            if not self.props.existing_vpc:
                logger.error("Existing VPC configuration is missing")
                raise ValueError("Existing VPC configuration is missing")

            vpc_id = self.props.existing_vpc.vpc_id
            subnet_ids = self.props.existing_vpc.subnet_ids
            vpc_cidr = self.props.existing_vpc.vpc_cidr

            # Determine the number of AZs based on the number of public subnets
            num_azs = len(subnet_ids.get("public", []))
            logger.info(f"Using existing VPC: {vpc_id}")
            logger.debug(f"Public subnets: {subnet_ids.get('public', [])[:num_azs]}")
            logger.debug(f"Private subnets: {subnet_ids.get('private', [])[:num_azs]}")
            logger.debug(f"CIDR: {vpc_cidr}")

            self.vpc = ec2.Vpc.from_vpc_attributes(
                self,
                "ExistingVPC",
                vpc_id=vpc_id,
                availability_zones=scope.availability_zones[:num_azs],
                private_subnet_ids=subnet_ids.get("private", [])[:num_azs],
                public_subnet_ids=subnet_ids.get("public", []),
                vpc_cidr_block=vpc_cidr,
            )
            logger.info(f"Successfully initialized existing VPC with ID: {vpc_id}")
        else:
            if not self.props.new_vpc:
                logger.error("New VPC configuration is missing")
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

            logger.info(f"Creating new VPC: {new_vpc_config.vpc_name}")
            logger.info(f"VPC CIDR: {new_vpc_config.cidr}")
            logger.info(f"Max AZs: {new_vpc_config.max_azs}")

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
            logger.info(f"Successfully created new VPC: {self.vpc.vpc_id}")

            # Configure Network ACLs to restrict SSH and RDP access from Internet
            self._configure_network_acls()

        self.vpc_id = self.vpc.vpc_id

        # Create a CloudWatch Log Group for Flow Logs
        logger.info("Creating VPC Flow Logs")
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

    def _configure_network_acls(self) -> None:
        """
        Configure custom Network ACL rules to restrict SSH and RDP access from the Internet.
        This addresses security findings from Prowler scan for ports 22 and 3389.
        """
        logger.info(
            "Configuring custom Network ACL rules to restrict SSH and RDP access"
        )

        # Create Network ACL for Public Subnets
        public_nacl = ec2.NetworkAcl(
            self,
            "PublicSubnetNACL",
            vpc=self.vpc,
            network_acl_name=f"{self.vpc.vpc_id}-public-nacl",
        )

        # Associate public subnets with the custom NACL
        for idx, subnet in enumerate(self.vpc.public_subnets):
            ec2.SubnetNetworkAclAssociation(
                self,
                f"PublicSubnetNACLAssoc{idx}",
                subnet=subnet,
                network_acl=public_nacl,
            )

        # Public NACL Ingress Rules
        # Allow HTTP from anywhere
        public_nacl.add_entry(
            "AllowHTTPInbound",
            cidr=ec2.AclCidr.any_ipv4(),
            rule_number=100,
            traffic=ec2.AclTraffic.tcp_port(80),
            direction=ec2.TrafficDirection.INGRESS,
            rule_action=ec2.Action.ALLOW,
        )

        # Allow HTTPS from anywhere
        public_nacl.add_entry(
            "AllowHTTPSInbound",
            cidr=ec2.AclCidr.any_ipv4(),
            rule_number=110,
            traffic=ec2.AclTraffic.tcp_port(443),
            direction=ec2.TrafficDirection.INGRESS,
            rule_action=ec2.Action.ALLOW,
        )

        # Allow ephemeral ports for return traffic
        public_nacl.add_entry(
            "AllowEphemeralInbound",
            cidr=ec2.AclCidr.any_ipv4(),
            rule_number=120,
            traffic=ec2.AclTraffic.tcp_port_range(1024, 65535),
            direction=ec2.TrafficDirection.INGRESS,
            rule_action=ec2.Action.ALLOW,
        )

        # Explicitly DENY SSH from Internet
        public_nacl.add_entry(
            "DenySSHFromInternet",
            cidr=ec2.AclCidr.any_ipv4(),
            rule_number=10,
            traffic=ec2.AclTraffic.tcp_port(22),
            direction=ec2.TrafficDirection.INGRESS,
            rule_action=ec2.Action.DENY,
        )

        # Explicitly DENY RDP from Internet
        public_nacl.add_entry(
            "DenyRDPFromInternet",
            cidr=ec2.AclCidr.any_ipv4(),
            rule_number=20,
            traffic=ec2.AclTraffic.tcp_port(3389),
            direction=ec2.TrafficDirection.INGRESS,
            rule_action=ec2.Action.DENY,
        )

        # Public NACL Egress Rules - Allow all outbound
        public_nacl.add_entry(
            "AllowAllOutbound",
            cidr=ec2.AclCidr.any_ipv4(),
            rule_number=100,
            traffic=ec2.AclTraffic.all_traffic(),
            direction=ec2.TrafficDirection.EGRESS,
            rule_action=ec2.Action.ALLOW,
        )

        logger.info("Public subnet NACL configured with SSH and RDP restrictions")

        # Create Network ACL for Private Subnets
        private_nacl = ec2.NetworkAcl(
            self,
            "PrivateSubnetNACL",
            vpc=self.vpc,
            network_acl_name=f"{self.vpc.vpc_id}-private-nacl",
        )

        # Associate private subnets with the custom NACL
        for idx, subnet in enumerate(self.vpc.private_subnets):
            ec2.SubnetNetworkAclAssociation(
                self,
                f"PrivateSubnetNACLAssoc{idx}",
                subnet=subnet,
                network_acl=private_nacl,
            )

        # Private NACL Ingress Rules
        # Allow all traffic from VPC CIDR
        private_nacl.add_entry(
            "AllowVPCInbound",
            cidr=ec2.AclCidr.ipv4(self.vpc.vpc_cidr_block),
            rule_number=100,
            traffic=ec2.AclTraffic.all_traffic(),
            direction=ec2.TrafficDirection.INGRESS,
            rule_action=ec2.Action.ALLOW,
        )

        # Allow ephemeral ports from Internet for return traffic
        private_nacl.add_entry(
            "AllowEphemeralFromInternet",
            cidr=ec2.AclCidr.any_ipv4(),
            rule_number=110,
            traffic=ec2.AclTraffic.tcp_port_range(1024, 65535),
            direction=ec2.TrafficDirection.INGRESS,
            rule_action=ec2.Action.ALLOW,
        )

        # Explicitly DENY SSH from Internet
        private_nacl.add_entry(
            "DenySSHFromInternet",
            cidr=ec2.AclCidr.any_ipv4(),
            rule_number=10,
            traffic=ec2.AclTraffic.tcp_port(22),
            direction=ec2.TrafficDirection.INGRESS,
            rule_action=ec2.Action.DENY,
        )

        # Explicitly DENY RDP from Internet
        private_nacl.add_entry(
            "DenyRDPFromInternet",
            cidr=ec2.AclCidr.any_ipv4(),
            rule_number=20,
            traffic=ec2.AclTraffic.tcp_port(3389),
            direction=ec2.TrafficDirection.INGRESS,
            rule_action=ec2.Action.DENY,
        )

        # Private NACL Egress Rules - Allow all outbound
        private_nacl.add_entry(
            "AllowAllOutbound",
            cidr=ec2.AclCidr.any_ipv4(),
            rule_number=100,
            traffic=ec2.AclTraffic.all_traffic(),
            direction=ec2.TrafficDirection.EGRESS,
            rule_action=ec2.Action.ALLOW,
        )

        logger.info("Private subnet NACL configured with SSH and RDP restrictions")
        logger.info("Network ACL configuration completed successfully")

    def get_subnet_ids(self, subnet_type: ec2.SubnetType) -> List[Dict[str, str]]:
        """Get subnet IDs and their availability zones for a specific subnet type"""
        logger.debug(f"Getting subnet IDs for subnet type: {subnet_type}")
        try:
            if self.props.use_existing_vpc:
                subnet_ids = self.props.existing_vpc["subnet_ids"]
                if subnet_type == ec2.SubnetType.PRIVATE_WITH_EGRESS:
                    subnets = [
                        {"subnet_id": subnet_id, "az": "unknown"}
                        for subnet_id in subnet_ids["private"]
                    ]
                    logger.debug(
                        f"Found {len(subnets)} private subnets in existing VPC"
                    )
                    return subnets
                elif subnet_type == ec2.SubnetType.PUBLIC:
                    subnets = [
                        {"subnet_id": subnet_id, "az": "unknown"}
                        for subnet_id in subnet_ids["public"]
                    ]
                    logger.debug(f"Found {len(subnets)} public subnets in existing VPC")
                    return subnets
            else:
                if isinstance(self.vpc, ec2.Vpc):
                    subnets = self.vpc.select_subnets(subnet_type=subnet_type).subnets
                    result = [
                        {"subnet_id": subnet.subnet_id, "az": subnet.availability_zone}
                        for subnet in subnets
                    ]
                    logger.debug(
                        f"Found {len(result)} subnets of type {subnet_type} in new VPC"
                    )
                    return result
                elif isinstance(self.vpc, ec2.IVpc):
                    if subnet_type == ec2.SubnetType.PRIVATE_WITH_EGRESS:
                        result = [
                            {
                                "subnet_id": subnet.subnet_id,
                                "az": subnet.availability_zone,
                            }
                            for subnet in self.vpc.private_subnets
                        ]
                        logger.debug(f"Found {len(result)} private subnets in VPC")
                        return result
                    elif subnet_type == ec2.SubnetType.PUBLIC:
                        result = [
                            {
                                "subnet_id": subnet.subnet_id,
                                "az": subnet.availability_zone,
                            }
                            for subnet in self.vpc.public_subnets
                        ]
                        logger.debug(f"Found {len(result)} public subnets in VPC")
                        return result
            logger.warning(f"No subnets found for subnet type: {subnet_type}")
            return []
        except Exception as e:
            logger.error(f"Error getting subnet IDs: {str(e)}")
            return []
