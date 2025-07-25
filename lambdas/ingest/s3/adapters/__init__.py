"""
AWS-specific adapter implementations for hexagonal architecture.

This package contains concrete implementations of port interfaces using AWS services.
Adapters translate between the domain layer's needs and AWS infrastructure capabilities.

Structure:
- storage/: Storage adapter implementations (DynamoDB, S3)
- messaging/: Messaging adapter implementations (EventBridge, SNS)
- search/: Search adapter implementations (OpenSearch, S3 Vector)
- external/: External service adapter implementations (Lambda, hash detection)
- aws/: AWS SDK utilities and configuration
"""

from .aws.aws_config import AWSConfig
from .aws.connection_pool import ConnectionPool
from .aws.retry_handler import RetryHandler

__all__ = [
    "AWSConfig",
    "ConnectionPool",
    "RetryHandler",
]
