from dataclasses import dataclass
from constructs import Construct
from aws_cdk import Stack

@dataclass
class SharedAssetsStackProps:
    asset_table: dynamodb.TableV2
    media_assets_bucket: s3.IBucket


class SharedAssetsStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, props: SharedAssetsStackProps, **kwargs):
        super().__init__(scope, construct_id, **kwargs)

        env = kwargs.get("env")
        account = Stack.of(self).account
        region = Stack.of(self).region

