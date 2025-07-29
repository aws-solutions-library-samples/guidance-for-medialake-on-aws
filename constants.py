#!/usr/bin/env python3
"""
Constants used throughout the Media Lake CDK application.
This file contains named constants to ensure consistency across stacks and constructs.
"""

from enum import Enum
from typing import Dict

from config import config


# Environment names
class Environment(str, Enum):
    DEVELOPMENT = "dev"
    STAGING = "stage"
    PRODUCTION = "prod"


# General constants
APP_NAME = "medialake"
APP_PREFIX = "ml"


# Resource naming patterns
class ResourceNames:
    """Standard naming patterns for resources"""

    # Format: {app_prefix}-{resource_type}-{name}-{environment}
    @staticmethod
    def format(resource_type: str, name: str, environment: str) -> str:
        """Format a resource name using standard pattern"""
        return f"{APP_PREFIX}-{resource_type}-{name}-{environment}"

    @staticmethod
    def lambda_name(name: str, environment: str) -> str:
        """Format a Lambda function name"""
        return ResourceNames.format("lambda", name, environment)

    @staticmethod
    def bucket_name(name: str, environment: str) -> str:
        """Format an S3 bucket name"""
        return ResourceNames.format("s3", name, environment)

    @staticmethod
    def table_name(name: str, environment: str) -> str:
        """Format a DynamoDB table name"""
        return ResourceNames.format("ddb", name, environment)


# Default tags to apply to all resources
DEFAULT_TAGS: Dict[str, str] = {
    "Project": APP_NAME,
    "ManagedBy": "CDK",
}


# S3 constants
class S3:
    """S3 related constants"""

    ASSETS_BUCKET_EXPORT = "MediaLakeAssetsBucket"
    LOGS_BUCKET_EXPORT = "MediaLakeLogsBucket"
    DEPLOYMENT_BUCKET_EXPORT = "MediaLakeDeploymentBucket"

    # Lifecycle rules
    DEFAULT_EXPIRATION_DAYS = 90
    LOGS_EXPIRATION_DAYS = 365

    # CORS configuration
    DEFAULT_CORS_ALLOWED_ORIGINS = ["*"]
    DEFAULT_CORS_ALLOWED_METHODS = ["GET", "HEAD", "PUT", "POST"]
    DEFAULT_CORS_ALLOWED_HEADERS = ["*"]
    DEFAULT_CORS_MAX_AGE = 3600


# Lambda constants
class Lambda:
    """Lambda related constants"""

    DEFAULT_MEMORY_SIZE = 256
    DEFAULT_TIMEOUT_SECONDS = 60
    LONG_RUNNING_TIMEOUT_SECONDS = 900  # 15 minutes

    # Runtime versions
    PYTHON_RUNTIME = "python3.12"
    NODE_RUNTIME = "nodejs20.x"

    # Layer names
    COMMON_LAYER_NAME = "media-lake-common-layer"
    AUTH_LAYER_NAME = "media-lake-auth-layer"

    # Warmer interval (minutes)
    WARMER_INTERVAL_MINUTES = 5


# IAM constants
class IAM:
    """IAM related constants"""

    # Role prefixes
    LAMBDA_ROLE_PREFIX = "LambdaExecutionRole"
    API_ROLE_PREFIX = "ApiGatewayRole"

    # Managed policies
    LAMBDA_BASIC_EXECUTION_POLICY = "service-role/AWSLambdaBasicExecutionRole"
    LAMBDA_VPC_EXECUTION_POLICY = "service-role/AWSLambdaVPCAccessExecutionRole"


# API Gateway constants
class ApiGateway:
    """API Gateway related constants"""

    API_NAME = f"{APP_NAME}-api"
    DEFAULT_STAGE_NAME = "v1"

    # Endpoint types
    REGIONAL = "REGIONAL"
    EDGE = "EDGE"
    PRIVATE = "PRIVATE"

    # Authentication types
    COGNITO = "COGNITO_USER_POOLS"
    IAM = "AWS_IAM"
    NONE = "NONE"


# DynamoDB constants
class DynamoDB:
    """DynamoDB related constants"""

    DEFAULT_BILLING_MODE = "PAY_PER_REQUEST"
    PROVISIONED_BILLING_MODE = "PROVISIONED"

    # Table names
    SETTINGS_TABLE = "settings"
    ASSETS_TABLE = "assets"
    METADATA_TABLE = "metadata"
    USERS_TABLE = "users"
    CONNECTOR_TABLE = "connectors"
    ASSET_SYNC_JOB_TABLE = "asset-sync-job"
    ASSET_SYNC_CHUNK_TABLE = "asset-sync-chunk"
    ASSET_SYNC_ERROR_TABLE = "asset-sync-error"

    # Default capacity
    DEFAULT_READ_CAPACITY = 5
    DEFAULT_WRITE_CAPACITY = 5

    @staticmethod
    def connector_table_name(environment: str = None) -> str:
        """Get the full connector table name with prefix and environment"""
        env = environment or config.environment
        return f"{config.resource_prefix}_{DynamoDB.CONNECTOR_TABLE}_table_{env}"

    @staticmethod
    def asset_sync_job_table_name() -> str:
        """Get the full asset sync job table name with prefix"""
        return f"{config.resource_prefix}-{DynamoDB.ASSET_SYNC_JOB_TABLE}-table"

    @staticmethod
    def asset_sync_chunk_table_name() -> str:
        """Get the full asset sync chunk table name with prefix"""
        return f"{config.resource_prefix}-{DynamoDB.ASSET_SYNC_CHUNK_TABLE}-table"

    @staticmethod
    def asset_sync_error_table_name() -> str:
        """Get the full asset sync error table name with prefix"""
        return f"{config.resource_prefix}-{DynamoDB.ASSET_SYNC_ERROR_TABLE}-table"

    @staticmethod
    def connector_table_arn(region: str, account: str) -> str:
        """Get the full connector table ARN"""
        return f"arn:aws:dynamodb:{region}:{account}:table/{DynamoDB.connector_table_name()}"


# CloudFront constants
class CloudFront:
    """CloudFront related constants"""

    DEFAULT_PRICE_CLASS = "PriceClass_100"  # US, Canada, Europe
    GLOBAL_PRICE_CLASS = "PriceClass_All"  # All regions

    # Cache behaviors
    DEFAULT_TTL = 86400  # 1 day in seconds
    MIN_TTL = 0
    MAX_TTL = 31536000  # 1 year in seconds


# CloudWatch constants
class CloudWatch:
    """CloudWatch related constants"""

    DEFAULT_RETENTION_DAYS = 30
    HIGH_RETENTION_DAYS = 90

    # Alarm thresholds
    ERROR_THRESHOLD = 5
    LATENCY_THRESHOLD_MS = 1000


# Pipeline constants
class Pipeline:
    """Pipeline related constants"""

    # States
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

    # Step types
    INGEST = "INGEST"
    PROCESS = "PROCESS"
    ANALYZE = "ANALYZE"
    TRANSFORM = "TRANSFORM"
    EXPORT = "EXPORT"


# VPC constants
class VPC:
    """VPC related constants"""

    CIDR_BLOCK = "10.0.0.0/16"
    PUBLIC_SUBNET_MASK = 24
    PRIVATE_SUBNET_MASK = 24

    # Number of AZs to use
    AZ_COUNT = 2


# Constants for headers
class Headers:
    """Common HTTP headers"""

    CONTENT_TYPE = "Content-Type"
    AUTHORIZATION = "Authorization"
    CORS_ORIGIN = "Access-Control-Allow-Origin"


# Environment variable names used across lambdas
class EnvVars:
    """Environment variable name constants"""

    CONNECTOR_TABLE_NAME = "CONNECTOR_TABLE_NAME"
    JOB_TABLE_NAME = "JOB_TABLE_NAME"
    CHUNK_TABLE_NAME = "CHUNK_TABLE_NAME"
    ERROR_TABLE_NAME = "ERROR_TABLE_NAME"
    PROCESSOR_QUEUE_URL = "PROCESSOR_QUEUE_URL"
    RESULTS_BUCKET_NAME = "RESULTS_BUCKET_NAME"
    BATCH_OPERATIONS_ROLE_ARN = "BATCH_OPERATIONS_ROLE_ARN"
    STATUS_TOPIC_ARN = "STATUS_TOPIC_ARN"
    PROCESSOR_FUNCTION_ARN = "PROCESSOR_FUNCTION_ARN"


# Common DynamoDB permission sets
class DynamoDBPermissions:
    """Common DynamoDB permission action sets"""

    READ_ONLY = [
        "dynamodb:GetItem",
        "dynamodb:Query",
        "dynamodb:Scan",
        "dynamodb:BatchGetItem",
    ]

    READ_WRITE = [
        "dynamodb:GetItem",
        "dynamodb:Query",
        "dynamodb:Scan",
        "dynamodb:BatchGetItem",
        "dynamodb:PutItem",
        "dynamodb:UpdateItem",
        "dynamodb:DeleteItem",
        "dynamodb:BatchWriteItem",
    ]

    QUERY_ONLY = [
        "dynamodb:Query",
        "dynamodb:GetItem",
    ]


# SNS Topic names
class SNS:
    """SNS topic name constants"""

    ASSET_SYNC_STATUS_TOPIC = "asset-sync-status"

    @staticmethod
    def asset_sync_status_topic_name() -> str:
        """Get the full asset sync status topic name with prefix"""
        return f"{config.resource_prefix}-{SNS.ASSET_SYNC_STATUS_TOPIC}-topic"


# Media formats and MIME types
class MediaFormats:
    """Supported media formats and their MIME types"""

    IMAGE_FORMATS = ["jpg", "jpeg", "png", "gif", "tiff", "bmp", "webp"]
    VIDEO_FORMATS = ["mp4", "mov", "avi", "wmv", "flv", "mkv", "webm"]
    AUDIO_FORMATS = ["mp3", "wav", "aac", "ogg", "flac", "m4a"]
    DOCUMENT_FORMATS = ["pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "txt"]

    # MIME types mapping
    MIME_TYPES = {
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "gif": "image/gif",
        "mp4": "video/mp4",
        "mov": "video/quicktime",
        "mp3": "audio/mpeg",
        "pdf": "application/pdf",
    }
