from aws_cdk import (
    Stack,
    aws_dynamodb as dynamodb,
    # aws_lambda as lambda_,
    # aws_iam as iam,
    # custom_resources as cr,
)

from constructs import Construct
from dataclasses import dataclass

# Local imports
from config import config
from medialake_constructs.shared_constructs.dynamodb import DynamoDB, DynamoDBProps

# from medialake_constructs.shared_constructs.lambda_base import (
#     Lambda,
#     LambdaConfig,
# )


# @dataclass
# class PipelineStackProps:
#     asset_table: dynamodb.TableV2


class PipelineStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        props: None,  # PipelineStackProps,
        **kwargs,
    ):
        super().__init__(scope, construct_id, **kwargs)

        self._pipelne_table = DynamoDB(
            self,
            "PipelinesTable",
            props=DynamoDBProps(
                name=f"{config.global_prefix}_pipeline_table",
                partition_key_name="id",
                partition_key_type=dynamodb.AttributeType.STRING,
            ),
        )

    @property
    def pipeline_table(self) -> dynamodb.TableV2:
        """
        Returns the DynamoDB table used for storing pipelines.

        Returns:
            dynamodb.TableV2: The configured DynamoDB table
        """

        return self._pipelne_table.table
