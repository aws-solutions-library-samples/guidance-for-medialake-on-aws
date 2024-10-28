from aws_cdk import (
    Stack,
)
from constructs import Construct
from config import config
from medialake_constructs.shared_constructs.s3bucket import S3Bucket, S3Config


class BaseInfrastructureStack(Stack):
    def __init__(self, scope: Construct, id: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        # Load the configuration
        config.load()

        # Access the list of regions
        self.regions = config.regions

        # Use the regions list in your construct
        for region in self.regions:
            s3_bucket_config = S3Config(
                bucket_name=f"{config.DEMO_MEDIA_ASSETS_BUCKET_NAME}-{region}",
            )
            s3_bucket = S3Bucket(
                self, f"MediaLakeLogBucket-{region}", config=s3_bucket_config
            )
