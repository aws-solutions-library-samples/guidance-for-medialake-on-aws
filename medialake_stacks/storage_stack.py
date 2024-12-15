# import os
# import shutil
# import sys
# import subprocess

# from aws_cdk import aws_lambda as lambda_
# from aws_cdk import (
#     aws_s3 as s3,
#     aws_logs as logs,
#     custom_resources as cr,
#     aws_iam as iam,
#     aws_cloudfront as cloudfront,
#     aws_s3_deployment as s3deploy,
#     aws_secretsmanager as secretsmanager,
#     aws_cloudfront_origins as origins,
#     aws_wafv2 as wafv2,
#     Duration,
#     RemovalPolicy,
#     ILocalBundling,
#     BundlingOptions,
#     DockerImage,
#     Stack,
# )
# from constructs import Construct

# from dataclasses import dataclass, field
# from medialake_constructs.shared_constructs.s3bucket import S3Bucket, S3BucketProps
# from typing import List, Dict, Optional
# from config import config
# import jsii


# class MediaLakeStorageStack(Stack):
#     def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
#         super().__init__(scope, construct_id, **kwargs)

#         # Move the S3 bucket creation here
#         self.medialake_ui_s3_bucket = S3Bucket(
#             self,
#             "MediaLakeUserInterfaceBucket",
#             props=S3BucketProps(
#                 bucket_name=f"{config.global_prefix}-user-interface-{config.account_id}-{config.environment}",
#                 website_index_document="index.html",
#                 website_error_document="index.html",
#                 access_logs_bucket=self.access_log_bucket,
#             ),
#         )

#     @property
#     def medialake_ui_s3_bucket(self) -> s3.IBucket:
#         return self.medialake_ui_s3_bucket.bucket
