from aws_cdk import (
    Stack,
    aws_events as events,
    aws_kms as kms,
    aws_logs as logs,
    aws_iam as iam,
    RemovalPolicy,
    Duration,
)
from constructs import Construct


class EventBusConstruct(Construct):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id)

        # Extract optional parameters with default values
        bus_name = kwargs.get("bus_name", "default-event-bus")
        description = kwargs.get("description", "Secure EventBridge Event Bus")
        enable_encryption = kwargs.get("enable_encryption", True)
        enable_logging = kwargs.get("enable_logging", True)
        log_retention = kwargs.get("log_retention", logs.RetentionDays.ONE_MONTH)

        # Create KMS Key for encryption
        if enable_encryption:
            encryption_key = kms.Key(
                self,
                "EventBusEncryptionKey",
                enable_key_rotation=True,
                description="KMS Key for EventBridge Event Bus Encryption",
                removal_policy=RemovalPolicy.DESTROY,
            )
        else:
            encryption_key = None

        # Create EventBridge Event Bus
        self.event_bus = events.EventBus(
            self,
            "SecureEventBus",
            event_bus_name=bus_name,
            description=description,
            kms_key=encryption_key,
        )

        # Enable logging if specified
        if enable_logging:
            log_group = logs.LogGroup(
                self,
                "EventBusLogGroup",
                log_group_name=f"/aws/events/{bus_name}",
                retention=log_retention,
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

            # Add CloudWatch Logs as a target for all events
            self.event_bus.archive(
                "EventBusArchive",
                archive_name=f"{bus_name}-archive",
                description="Archive for all events",
                event_pattern=events.EventPattern(account=[Stack.of(self).account]),
                retention=Duration.days(90),
            )

        # Grant permissions to the event bus
        self.event_bus.grant_put_events_to(iam.AccountRootPrincipal())

    def grant_put_events(self, grantee: iam.IGrantable):
        """
        Grants permissions to put events to the Event Bus
        """
        return self.event_bus.grant_put_events_to(grantee)
