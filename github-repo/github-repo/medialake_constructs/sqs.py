from dataclasses import dataclass
from typing import Any, Dict, Optional

from aws_cdk import CfnOutput, Duration, RemovalPolicy, Stack
from aws_cdk import aws_kms as kms
from aws_cdk import aws_sqs as sqs
from constructs import Construct

from config import config


@dataclass
class SQSProps:
    queue_name: Optional[str] = None
    fifo: bool = False
    content_based_deduplication: bool = False
    visibility_timeout: Duration = Duration.seconds(30)
    delivery_delay: Duration = Duration.seconds(0)
    receive_message_wait_time: Duration = Duration.seconds(0)
    retention_period: Duration = Duration.days(4)
    encryption: bool = True
    enforce_ssl: bool = True
    dead_letter_queue: Optional[Dict[str, Any]] = None
    max_receive_count: int = 3
    removal_policy: RemovalPolicy = RemovalPolicy.DESTROY


class SQSConstruct(Construct):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        props: SQSProps,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Get the region from the stack
        stack = Stack.of(self)
        stack.region

        # Use provided props or create default props
        self.props = props or SQSProps()

        # Handle queue name for FIFO queues
        queue_name = (
            f"{config.resource_prefix}-{self.props.queue_name}-{config.environment}"
        )
        if self.props.fifo and queue_name and not queue_name.endswith(".fifo"):
            queue_name = f"{queue_name}.fifo"

        # Create KMS key for encryption if enabled
        encryption_key = None
        if self.props.encryption:
            encryption_key = kms.Key(
                self,
                f"{construct_id}EncryptionKey",
                enable_key_rotation=True,
                removal_policy=self.props.removal_policy,
            )

        # Setup dead letter queue if specified
        dlq = None
        if self.props.dead_letter_queue:
            # Use an existing DLQ if provided
            dlq = self.props.dead_letter_queue.get("queue")

        # If no DLQ provided but max_receive_count > 0, create a new DLQ
        if dlq is None and self.props.max_receive_count > 0:
            dlq_props = SQSProps(
                queue_name=f"{queue_name}" if queue_name else None,
                fifo=self.props.fifo,
                content_based_deduplication=self.props.content_based_deduplication,
                encryption=self.props.encryption,
                enforce_ssl=self.props.enforce_ssl,
                removal_policy=self.props.removal_policy,
                max_receive_count=0,
            )

            dlq_construct = SQSConstruct(
                self,
                f"{construct_id}DLQ",
                dlq_props,
            )
            dlq = dlq_construct.queue

        # Create the main queue
        queue_props = {
            "queue_name": queue_name,
            "fifo": self.props.fifo,
            "content_based_deduplication": self.props.content_based_deduplication
            and self.props.fifo,
            "visibility_timeout": self.props.visibility_timeout,
            "delivery_delay": self.props.delivery_delay,
            "receive_message_wait_time": self.props.receive_message_wait_time,
            "retention_period": self.props.retention_period,
            "enforce_ssl": self.props.enforce_ssl,
            "removal_policy": self.props.removal_policy,
        }

        # Add encryption if enabled
        if self.props.encryption:
            queue_props["encryption"] = sqs.QueueEncryption.KMS
            queue_props["encryption_master_key"] = encryption_key

        # Add DLQ if available
        if dlq:
            queue_props["dead_letter_queue"] = {
                "queue": dlq,
                "max_receive_count": self.props.max_receive_count,
            }

        # Create the queue
        self._queue = sqs.Queue(self, f"{construct_id}Queue", **queue_props)

        # Output queue URL
        CfnOutput(
            self,
            f"{construct_id}QueueUrl",
            value=self._queue.queue_url,
            export_name=f"{construct_id}QueueUrl",
        )

        # Output queue ARN
        CfnOutput(
            self,
            f"{construct_id}QueueArn",
            value=self._queue.queue_arn,
            export_name=f"{construct_id}QueueArn",
        )

        # Store the key for properties
        self._encryption_key = encryption_key
        self._dlq = dlq

    @property
    def queue(self) -> sqs.IQueue:
        return self._queue

    @property
    def queue_url(self) -> str:
        return self._queue.queue_url

    @property
    def queue_arn(self) -> str:
        return self._queue.queue_arn

    @property
    def queue_name(self) -> str:
        return self._queue.queue_name

    @property
    def encryption_key(self) -> Optional[kms.IKey]:
        return self._encryption_key

    @property
    def dead_letter_queue(self) -> Optional[sqs.IQueue]:
        return self._dlq
