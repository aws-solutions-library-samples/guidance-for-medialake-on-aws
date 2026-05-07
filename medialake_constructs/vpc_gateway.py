from typing import List, Optional

from aws_cdk import CfnOutput
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_iam as iam
from constructs import Construct


class S3VpcGateway(Construct):
    """
    A CDK construct that creates an S3 Gateway VPC Endpoint.

    This allows resources within the VPC to access S3 without going through the public internet,
    which provides better security, lower latency, and no bandwidth charges for data transfer
    between the VPC and S3.
    """

    def __init__(
        self,
        scope: Construct,
        id: str,
        vpc: ec2.IVpc,
        subnet_selection: Optional[ec2.SubnetSelection] = None,
        policy_statements: Optional[List[iam.PolicyStatement]] = None,
        **kwargs,
    ):
        """
        Initialize the S3VpcGateway construct.

        Parameters:
        -----------
        scope: Construct
            The scope in which to define this construct
        id: str
            The scoped ID of the construct
        vpc: ec2.IVpc
            The VPC to create the gateway endpoint in
        subnet_selection: Optional[ec2.SubnetSelection]
            Specific subnets to route to the gateway endpoint.
            If not specified, all subnets in the VPC will be routed.
        policy_statements: Optional[List[iam.PolicyStatement]]
            List of IAM policy statements to attach to the gateway endpoint
        """
        super().__init__(scope, id, **kwargs)

        # Create the S3 Gateway VPC Endpoint
        self.gateway = ec2.GatewayVpcEndpoint(
            self,
            "S3GatewayEndpoint",
            vpc=vpc,
            service=ec2.GatewayVpcEndpointAwsService.S3,
            subnets=[subnet_selection] if subnet_selection else None,
        )

        # Add policy statements if provided
        if policy_statements:
            for statement in policy_statements:
                self.gateway.add_to_policy(statement)
        else:
            # Add default policy to allow all S3 actions
            self.gateway.add_to_policy(
                iam.PolicyStatement(
                    principals=[iam.AnyPrincipal()],
                    actions=["s3:*"],
                    resources=["*"],
                )
            )

        # Output the gateway endpoint ID
        CfnOutput(
            self,
            "S3GatewayEndpointId",
            description="ID of the S3 Gateway VPC Endpoint",
            value=self.gateway.vpc_endpoint_id,
        )


class S3AndDynamoDBVpcGateways(Construct):
    """
    A convenience construct that creates both S3 and DynamoDB Gateway VPC Endpoints.

    This is commonly used together as these are the only two services that support
    Gateway VPC Endpoints.
    """

    def __init__(
        self,
        scope: Construct,
        id: str,
        vpc: ec2.IVpc,
        subnet_selection: Optional[ec2.SubnetSelection] = None,
        s3_policy_statements: Optional[List[iam.PolicyStatement]] = None,
        dynamodb_policy_statements: Optional[List[iam.PolicyStatement]] = None,
        **kwargs,
    ):
        """
        Initialize the S3AndDynamoDBVpcGateways construct.

        Parameters:
        -----------
        scope: Construct
            The scope in which to define this construct
        id: str
            The scoped ID of the construct
        vpc: ec2.IVpc
            The VPC to create the gateway endpoints in
        subnet_selection: Optional[ec2.SubnetSelection]
            Specific subnets to route to the gateway endpoints
        s3_policy_statements: Optional[List[iam.PolicyStatement]]
            List of IAM policy statements to attach to the S3 gateway endpoint
        dynamodb_policy_statements: Optional[List[iam.PolicyStatement]]
            List of IAM policy statements to attach to the DynamoDB gateway endpoint
        """
        super().__init__(scope, id, **kwargs)

        # Create the S3 Gateway VPC Endpoint
        self.s3_gateway = ec2.GatewayVpcEndpoint(
            self,
            "S3GatewayEndpoint",
            vpc=vpc,
            service=ec2.GatewayVpcEndpointAwsService.S3,
            subnets=[subnet_selection] if subnet_selection else None,
        )

        # Create the DynamoDB Gateway VPC Endpoint
        self.dynamodb_gateway = ec2.GatewayVpcEndpoint(
            self,
            "DynamoDBGatewayEndpoint",
            vpc=vpc,
            service=ec2.GatewayVpcEndpointAwsService.DYNAMODB,
            subnets=[subnet_selection] if subnet_selection else None,
        )

        # Add S3 policy statements if provided
        if s3_policy_statements:
            for statement in s3_policy_statements:
                self.s3_gateway.add_to_policy(statement)
        else:
            # Add default policy to allow all S3 actions
            self.s3_gateway.add_to_policy(
                iam.PolicyStatement(
                    principals=[iam.AnyPrincipal()],
                    actions=["s3:*"],
                    resources=["*"],
                )
            )

        # Add DynamoDB policy statements if provided
        if dynamodb_policy_statements:
            for statement in dynamodb_policy_statements:
                self.dynamodb_gateway.add_to_policy(statement)
        else:
            # Add default policy to allow all DynamoDB actions
            self.dynamodb_gateway.add_to_policy(
                iam.PolicyStatement(
                    principals=[iam.AnyPrincipal()],
                    actions=["dynamodb:*"],
                    resources=["*"],
                )
            )

        # Output the gateway endpoint IDs
        CfnOutput(
            self,
            "S3GatewayEndpointId",
            description="ID of the S3 Gateway VPC Endpoint",
            value=self.s3_gateway.vpc_endpoint_id,
        )

        CfnOutput(
            self,
            "DynamoDBGatewayEndpointId",
            description="ID of the DynamoDB Gateway VPC Endpoint",
            value=self.dynamodb_gateway.vpc_endpoint_id,
        )
