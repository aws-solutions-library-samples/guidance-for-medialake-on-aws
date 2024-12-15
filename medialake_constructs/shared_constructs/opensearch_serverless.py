from aws_cdk import (
    Stack,
    aws_iam as iam,
    aws_lambda as _lambda,
    aws_opensearchserverless as opensearch_serverless,
    CustomResource,
    custom_resources as cr,
    aws_logs as logs,
    Duration,
    RemovalPolicy,
)
from constructs import Construct
from dataclasses import dataclass, field
from typing import Optional
from typing import List
from aws_cdk.aws_lambda_python_alpha import PythonLayerVersion
import json, time
import hashlib
from pathlib import Path


@dataclass
class OpenSearchServerlessProps:
    collection_name: str = "my-opensearch-serverless-collection"
    public_access: bool = True
    collection_type: str = "VECTORSEARCH"
    collection_desc: str = (
        "Collection to be used for vector search using OpenSearch Serverless"
    )
    collection_indexes: List[str] = field(default_factory=["my-collection-index"])


class OpenSearchServerlessConstruct(Construct):

    def __init__(
        self,
        scope: Construct,
        id: str,
        props: Optional[OpenSearchServerlessProps] = None,
    ):
        super().__init__(scope, id)

        self.props: OpenSearchServerlessProps = props or OpenSearchServerlessProps()

        # Determine the current stack
        stack = Stack.of(self)

        # Get the region and account ID
        self.region = stack.region
        self.account_id = stack.account

        network_security_policy = json.dumps(
            [
                {
                    "Rules": [
                        {
                            "Resource": [f"collection/{self.props.collection_name}"],
                            "ResourceType": "dashboard",
                        },
                        {
                            "Resource": [f"collection/{self.props.collection_name}"],
                            "ResourceType": "collection",
                        },
                    ],
                    "AllowFromPublic": self.props.public_access,
                }
            ],
            indent=2,
        )

        network_security_policy_name = f"{self.props.collection_name}-security-policy"
        assert (
            len(network_security_policy_name) <= 32
        ), f"Network Security Policy: {network_security_policy_name}"

        self.cfn_network_security_policy = opensearch_serverless.CfnSecurityPolicy(
            self,
            "NetworkSecurityPolicy",
            policy=network_security_policy,
            name=network_security_policy_name,
            type="network",
        )

        encryption_security_policy = json.dumps(
            {
                "Rules": [
                    {
                        "Resource": [f"collection/{self.props.collection_name}"],
                        "ResourceType": "collection",
                    }
                ],
                "AWSOwnedKey": True,
            },
            indent=2,
        )

        encryption_security_policy_name = (
            f"{self.props.collection_name}-security-policy"
        )
        assert (
            len(encryption_security_policy_name) <= 32
        ), f"Encryption Security Policy: {encryption_security_policy_name}"

        self.cfn_encryption_security_policy = opensearch_serverless.CfnSecurityPolicy(
            self,
            "EncryptionSecurityPolicy",
            policy=encryption_security_policy,
            name=encryption_security_policy_name,
            type="encryption",
        )

        self.cfn_collection = opensearch_serverless.CfnCollection(
            self,
            "OpssSearchCollection",
            name=self.props.collection_name,
            description=self.props.collection_desc,
            type=self.props.collection_type,
        )

        self.cfn_collection.add_dependency(self.cfn_network_security_policy)
        self.cfn_collection.add_dependency(self.cfn_encryption_security_policy)

        # Define the Lambda function that creates a new index in the opensearch serverless collection
        create_index_lambda = _lambda.Function(
            self,
            "Index",
            runtime=_lambda.Runtime.PYTHON_3_13,
            handler="index.handler",
            code=_lambda.Code.from_asset("lambdas/back_end/create_oss_index/"),
            timeout=Duration.seconds(60),
            environment={
                "COLLECTION_ENDPOINT": self.cfn_collection.attr_collection_endpoint,
                "INDEX_NAMES": ",".join(self.props.collection_indexes),
                "REGION": self.region,
                "SCOPE": "aoss",
            },
        )

        layer = PythonLayerVersion(
            self,
            "RequestsLayer",
            entry="lambdas/back_end/create_oss_index",
            compatible_runtimes=[_lambda.Runtime.PYTHON_3_13],
        )

        create_index_lambda.add_layers(layer)

        # Define IAM permission policy for the Lambda function.
        # This function calls the OpenSearch Serverless API to create a new index in the collection and must have the "aoss" permissions.
        create_index_lambda.role.add_to_principal_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "es:ESHttpPut",
                    "es:*",
                    "iam:CreateServiceLinkedRole",
                    "iam:PassRole",
                    "iam:ListUsers",
                    "iam:ListRoles",
                    "aoss:APIAccessAll",
                    "aoss:*",
                ],
                resources=["*"],
            )
        )

        data_access_policy = json.dumps(
            [
                {
                    "Rules": [
                        {
                            "Resource": [f"collection/{self.props.collection_name}"],
                            "Permission": [
                                "aoss:CreateCollectionItems",
                                "aoss:DeleteCollectionItems",
                                "aoss:UpdateCollectionItems",
                                "aoss:DescribeCollectionItems",
                            ],
                            "ResourceType": "collection",
                        },
                        {
                            "Resource": ["index/*/*"],
                            "Permission": [
                                "aoss:CreateIndex",
                                "aoss:DeleteIndex",
                                "aoss:UpdateIndex",
                                "aoss:DescribeIndex",
                                "aoss:ReadDocument",
                                "aoss:WriteDocument",
                            ],
                            "ResourceType": "index",
                        },
                    ],
                    "Principal": [
                        f"{iam.AccountPrincipal(self.account_id).arn}",
                        f"{create_index_lambda.role.role_arn}",
                    ],
                    "Description": "data-access-rule",
                }
            ],
            indent=2,
        )

        data_access_policy_name = f"{self.props.collection_name}-policy"
        assert (
            len(data_access_policy_name) <= 32
        ), f"Data Access Policy Name: {data_access_policy_name}"

        self.cfn_access_policy = opensearch_serverless.CfnAccessPolicy(
            self,
            "OpssDataAccessPolicy",
            name=data_access_policy_name,
            description="Policy for data access",
            policy=data_access_policy,
            type="data",
        )

        self.cfn_access_policy.add_dependency(self.cfn_collection)

        # Create a custom resource that uses the Lambda
        provider = cr.Provider(
            self,
            "IndexCreateResourceProvider",
            on_event_handler=create_index_lambda,
            log_retention=logs.RetentionDays.ONE_WEEK,  # Add log retention for debugging
        )

        lambda_code = Path("lambdas/back_end/create_oss_index/index.py").read_text(
            encoding="utf-8"
        )

        code_hash = hashlib.sha256(
            lambda_code.encode(), usedforsecurity=False
        ).hexdigest()

        create_index_resource = CustomResource(
            self,
            "IndexCreateResource",
            service_token=provider.service_token,
            properties={
                "code_hash": code_hash,
                "timestamp": str(int(time.time())),
            },
            resource_type="Custom::AOSSCreateIndex",
        )

        # Only trigger the custom resource after the opensearch access policy has been applied to the collection
        create_index_resource.node.add_dependency(self.cfn_access_policy)
        create_index_resource.node.add_dependency(self.cfn_collection)

    @property
    def collection_dashboards_url(self) -> str:
        return self.cfn_collection.attr_dashboard_endpoint

    @property
    def collection_endpoint(self) -> str:
        return self.cfn_collection.attr_collection_endpoint

    @property
    def collection_arn(self) -> str:
        return self.cfn_collection.attr_arn

    @property
    def opensearch_instance(self) -> opensearch_serverless.CfnCollection:
        return self.cfn_collection
