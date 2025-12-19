import os

# Environment variables
ACCOUNT_ID = os.environ.get("ACCOUNT_ID")
NODE_TABLE = os.environ.get("NODE_TABLE")
PIPELINES_TABLE = os.environ.get("PIPELINES_TABLE")
IAC_ASSETS_BUCKET = os.environ.get("IAC_ASSETS_BUCKET")
NODE_TEMPLATES_BUCKET = os.environ.get("NODE_TEMPLATES_BUCKET")
EXTERNAL_PAYLOAD_BUCKET = os.environ.get("EXTERNAL_PAYLOAD_BUCKET")
PIPELINES_EVENT_BUS_NAME = os.environ.get("PIPELINES_EVENT_BUS_NAME")
MEDIALAKE_ASSET_TABLE = os.environ.get("MEDIALAKE_ASSET_TABLE")
MEDIA_ASSETS_BUCKET_NAME = os.environ.get("MEDIA_ASSETS_BUCKET_NAME")
MEDIA_ASSETS_BUCKET_ARN_KMS_KEY = os.environ.get("MEDIA_ASSETS_BUCKET_ARN_KMS_KEY")
OPENSEARCH_ENDPOINT = os.environ.get("OPENSEARCH_ENDPOINT")
OPENSEARCH_VPC_SUBNET_IDS = os.environ.get("OPENSEARCH_VPC_SUBNET_IDS")
OPENSEARCH_SECURITY_GROUP_ID = os.environ.get("OPENSEARCH_SECURITY_GROUP_ID")
MEDIACONVERT_QUEUE_ARN = os.environ.get("MEDIACONVERT_QUEUE_ARN")
MEDIACONVERT_ROLE_ARN = os.environ.get("MEDIACONVERT_ROLE_ARN")

# S3 Vector configuration
VECTOR_BUCKET_NAME = os.environ.get("VECTOR_BUCKET_NAME")
INDEX_NAME = os.environ.get("INDEX_NAME", "media-vectors")
VECTOR_DIMENSION = os.environ.get("VECTOR_DIMENSION", "1024")

AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
resource_prefix = os.environ.get("RESOURCE_PREFIX")

# Validate required environment variables
required_env_vars = [
    ACCOUNT_ID,
    NODE_TABLE,
    PIPELINES_TABLE,
    IAC_ASSETS_BUCKET,
    NODE_TEMPLATES_BUCKET,
    OPENSEARCH_ENDPOINT,
    OPENSEARCH_VPC_SUBNET_IDS,
    OPENSEARCH_SECURITY_GROUP_ID,
]

if not all(required_env_vars):
    raise ValueError("One or more required environment variables are not set.")
