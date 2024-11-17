from aws_cdk import (
    Stack,
    aws_iam as iam,
    aws_lambda as _lambda,
    aws_opensearchservice as opensearch,
    aws_ec2 as ec2,
    CustomResource,
    custom_resources as cr,
    aws_logs as logs,
    Duration,
    RemovalPolicy,
    CfnOutput,
)
from constructs import Construct
from typing import Optional, List, Dict
from dataclasses import dataclass, field
from aws_cdk.aws_lambda_python_alpha import PythonLayerVersion
import json, time
import hashlib
from pathlib import Path

@dataclass
class OpenSearchClusterProps:
    domain_name: str
    engine_version: str = "OPENSEARCH_2_15"
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
    collection_indexes: List[str] = field(default_factory=lambda: ["my-collection-index"])

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

         # Create an access policy using the VPC's CIDR
        vpc_cidr = props.vpc.vpc_cidr_block
        # handling error - Apply a restrictive access policy to your domain
        access_policy = iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "es:ESHttpGet",
                "es:ESHttpPost",
                "es:ESHttpPut"
            ],
            principals=[iam.AnyPrincipal()],
            resources=[f"arn:aws:es:{self.region}:{self.account_id}:domain/{props.domain_name}/*"],
            conditions={
                "IpAddress": {
                    "aws:SourceIp": [vpc_cidr]
                }
            }
        )
        isolated_subnets = props.vpc.isolated_subnets
        if not isolated_subnets:
            raise ValueError("No isolated subnets found in the VPC")

        # Select the first isolated subnet
        selected_subnet = isolated_subnets[0]
        
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
            # access_policies=[access_policy],
            # VPC configuration
            vpc=props.vpc,
            vpc_subnets=[ec2.SubnetSelection(subnets=[selected_subnet])],
    
            # vpc_subnets=[ec2.SubnetSelection(
            #     subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
            # )],
            # vpc_subnets = ec2.SubnetConfiguration(
            #         cidr_mask=24,
            #         name='oss',
            #         subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
            # ),
            # Advanced options
            advanced_options={
                "rest.action.multi.allow_explicit_index": "true",
                "indices.fielddata.cache.size": "25",
                "indices.query.bool.max_clause_count": "2048",
            },
            removal_policy=RemovalPolicy.DESTROY,
        )
        self.domain.connections.allow_default_port_from_any_ipv4('Allow From All')
        
        

        # Create Lambda function for index creation
        create_index_lambda = _lambda.Function(
            self,
            "Index",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="index.handler",
            vpc=props.vpc,
            code=_lambda.Code.from_asset("lambdas/back_end/create_oss_index/"),
            timeout=Duration.seconds(60),
            environment={
                "COLLECTION_ENDPOINT": f"https://{self.domain.domain_endpoint}",
                "INDEX_NAMES": ",".join(props.collection_indexes),
                "REGION": self.region,
                "SCOPE": "es",
            },
        )

        layer = PythonLayerVersion(
            self,
            "RequestsLayer",
            entry="lambdas/back_end/create_oss_index",
            compatible_runtimes=[_lambda.Runtime.PYTHON_3_12],
        )

        create_index_lambda.add_layers(layer)

        # Define IAM permission policy for the Lambda function
        create_index_lambda.role.add_to_principal_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "es:ESHttpPut",
                    "es:ESHttpPost",
                    "es:ESHttpGet",
                ],
                resources=[f"{self.domain.domain_arn}/*"],
            )
        )

        # Allow the Lambda function to access the OpenSearch domain
        self.domain.grant_read_write(create_index_lambda)

        # Create a custom resource that uses the Lambda
        provider = cr.Provider(
            self,
            "IndexCreateResourceProvider",
            on_event_handler=create_index_lambda,
            log_retention=logs.RetentionDays.ONE_WEEK,
        )

        lambda_code = Path("lambdas/back_end/create_oss_index/index.py").read_text(
            encoding="utf-8"
        )

        code_hash = hashlib.md5(lambda_code.encode()).hexdigest()

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

        # Ensure the custom resource is created after the domain
        create_index_resource.node.add_dependency(self.domain)

        # access_policies = iam.PolicyStatement(
        #     effect=iam.Effect.ALLOW,
        #     actions=["es:*"],
        #     principals=[iam.AnyPrincipal()],
        #     resources=[f"{self.domain.domain_arn}/*"],
        # )

        # self.domain.add_access_policies(access_policies)

    @property
    def domain_endpoint(self) -> str:
        return f"https://{self.domain.domain_endpoint}"

    @property
    def domain_arn(self) -> str:
        return self.domain.domain_arn

    @property
    def opensearch_instance(self) -> opensearch.Domain:
        return self.domain