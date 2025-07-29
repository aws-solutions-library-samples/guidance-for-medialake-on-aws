from dataclasses import dataclass

import aws_cdk as cdk
from aws_cdk import Duration, RemovalPolicy
from constructs import Construct

from medialake_constructs.sqs import SQSConstruct, SQSProps


@dataclass
class StorageConnectorsStackProps:
    """Configuration for Storage Connectors Stack."""


class StorageConnectorsStack(cdk.NestedStack):
    def __init__(
        self, scope: Construct, id: str, props: StorageConnectorsStackProps, **kwargs
    ):
        super().__init__(scope, id, **kwargs)

        # Create SQS DLQ for API Gateway
        self.storage_ingest_connector_dlq = SQSConstruct(
            self,
            "StorageIngestConnectorDLQ",
            props=SQSProps(
                queue_name="storage-ingest-connector-dlq",
                visibility_timeout=Duration.seconds(60),
                retention_period=Duration.days(14),
                encryption=True,
                enforce_ssl=True,
                # No DLQ for this queue as it's already a DLQ
                max_receive_count=0,
                removal_policy=RemovalPolicy.DESTROY,
            ),
        )

    @property
    def storage_ingest_connector_dlq_url(self) -> str:
        return self.storage_ingest_connector_dlq.queue_url

    @property
    def storage_ingest_connector_dlq_arn(self) -> str:
        return self.storage_ingest_connector_dlq.queue_arn

    @property
    def storage_ingest_connector_dlq_name(self) -> str:
        return self.storage_ingest_connector_dlq.queue_name
