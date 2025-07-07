import os

# Environment variables
ACCOUNT_ID = os.environ.get("ACCOUNT_ID")
NODE_TABLE = os.environ.get("NODE_TABLE")
PIPELINES_TABLE = os.environ.get("PIPELINES_TABLE")
IAC_BUCKET = os.environ.get("IAC_ASSETS_BUCKET")
NODE_TEMPLATES_BUCKET = os.environ.get("NODE_TEMPLATES_BUCKET")
PIPELINES_EVENT_BUS_NAME = os.environ.get("PIPELINES_EVENT_BUS_NAME", "default")
MEDIALAKE_ASSET_TABLE = os.environ.get("MEDIALAKE_ASSET_TABLE")
MEDIA_ASSETS_BUCKET_NAME = os.environ.get("MEDIA_ASSETS_BUCKET_NAME")
MEDIA_ASSETS_BUCKET_ARN_KMS_KEY = os.environ.get("MEDIA_ASSETS_BUCKET_ARN_KMS_KEY")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

# Validate required environment variables
required_env_vars = [
    ACCOUNT_ID,
    PIPELINES_TABLE,
]

if not all(required_env_vars):
    raise ValueError("One or more required environment variables are not set.")
