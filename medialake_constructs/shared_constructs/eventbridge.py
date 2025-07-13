from dataclasses import dataclass

from aws_cdk import RemovalPolicy, Stack
from aws_cdk import aws_events as events
from aws_cdk import aws_events_targets as targets
from aws_cdk import aws_iam as iam
from aws_cdk import aws_kms as kms
from aws_cdk import aws_logs as logs
from constructs import Construct


@dataclass
class EventBusConfig:
    """Configuration for EventBus creation."""

    bus_name: str
    description: str = None
    encryption: bool = False
    logging: bool = True
    log_retention: logs.RetentionDays = logs.RetentionDays.ONE_MONTH
    log_all: bool = False


class EventBus(Construct):
    def __init__(
        self, scope: Construct, construct_id: str, props: EventBusConfig, **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Create KMS Key for encryption
        if props.encryption:
            encryption_key = kms.Key(
                self,
                "EventBusEncryptionKey",
                enable_key_rotation=True,
                description="KMS Key for EventBridge Event Bus Encryption",
                removal_policy=RemovalPolicy.DESTROY,
            )
        else:
            pass

        # Create EventBridge Event Bus
        self._event_bus = events.EventBus(
            self,
            "SecureEventBus",
            event_bus_name=props.bus_name,
        )

        # Enable logging if specified
        if props.logging:
            log_group = logs.LogGroup(
                self,
                "EventBusLogGroup",
                log_group_name=f"/aws/events/{props.bus_name}",
                retention=props.log_retention,
                removal_policy=RemovalPolicy.DESTROY,
            )

            # Create IAM role for EventBridge to write logs
            log_role = iam.Role(
                self,
                "EventBusLogRole",
                assumed_by=iam.ServicePrincipal("events.amazonaws.com"),
                description="IAM role for EventBridge to write logs",
            )
            log_role.add_to_policy(
                iam.PolicyStatement(
                    actions=["logs:CreateLogStream", "logs:PutLogEvents"],
                    resources=[log_group.log_group_arn],
                )
            )
        # Add EventBridge rule to log all events if log_all is True
        if props.log_all:
            log_all_group = logs.LogGroup(
                self,
                "EventBusLogAllGroup",
                log_group_name=f"eventbus_{props.bus_name}",
                retention=logs.RetentionDays.ONE_WEEK,
                removal_policy=RemovalPolicy.DESTROY,
            )

            events.Rule(
                self,
                "LogAllEventsRule",
                event_bus=self._event_bus,
                event_pattern=events.EventPattern(account=[Stack.of(self).account]),
                targets=[targets.CloudWatchLogGroup(log_all_group)],
            )

        # Grant permissions to the event bus
        self._event_bus.grant_put_events_to(iam.AccountRootPrincipal())

    def grant_put_events(self, grantee: iam.IGrantable):
        """
        Grants permissions to put events to the Event Bus
        """
        return self._event_bus.grant_put_events_to(grantee)

    @property
    def event_bus(self) -> events.EventBus:
        """Get the EventBus instance."""
        return self._event_bus

    @property
    def event_bus_name(self) -> str:
        """Get the name of the EventBus."""
        return self._event_bus.event_bus_name

    @property
    def pipelines_event_bus_name(self) -> str:
        return self._event_bus.event_bus_name
