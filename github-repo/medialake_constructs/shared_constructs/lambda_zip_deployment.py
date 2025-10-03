import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from aws_cdk import Duration
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_s3_deployment as s3deploy
from constructs import Construct


@dataclass
class LambdaZipDeploymentProps:
    """Configuration for Lambda function creation."""

    lambda_path: str
    deployment_bucket: str
    deployment_path: str = None
    package_name: str = None


class LambdaZipDeployment(Construct):
    def __init__(
        self, scope: Construct, id: str, props: LambdaZipDeploymentProps, **kwargs
    ):
        super().__init__(scope, id, **kwargs)

        Path(__file__).resolve().parent.parent.parent

        # Define the relative path to the Lambda source code as a single string
        # lambda_source_path = cdk_root / f"{props.deployment_path}"

        iac_assets_bucket = s3.Bucket.from_bucket_name(
            self, "ExistingBucket", f"{props.deployment_bucket}"
        )

        # Define the paths for Lambda
        lambda_source_path = os.path.abspath(
            os.path.join(__file__, "..", "..", "..", "lambdas", "ingest", "s3")
        )

        requirements_path = os.path.join(lambda_source_path, "requirements.txt")

        # Create a temporary directory for packaging
        lambda_package_path = os.path.join(
            os.path.dirname(lambda_source_path), "package"
        )
        os.makedirs(lambda_package_path, exist_ok=True)

        # Create zip file path and name
        zip_filename = "lambda_function.zip"
        zip_path = os.path.join(os.path.dirname(lambda_package_path), zip_filename)

        # Install dependencies and create zip if requirements.txt exists
        if os.path.exists(requirements_path):
            subprocess.run(
                [
                    "pip",
                    "install",
                    "--no-cache-dir",
                    "-r",
                    requirements_path,
                    "-t",
                    lambda_package_path,
                ],
                check=True,
            )

            # Copy Lambda source files to package directory
            for item in os.listdir(lambda_source_path):
                s = os.path.join(lambda_source_path, item)
                d = os.path.join(lambda_package_path, item)
                if os.path.isdir(s):
                    shutil.copytree(s, d, dirs_exist_ok=True)
                else:
                    shutil.copy2(s, d)

            # Create zip file from package directory
            shutil.make_archive(
                zip_path.replace(".zip", ""), "zip", lambda_package_path
            )

            # Use the packaged code for Lambda
            lambda_code = lambda_.Code.from_asset(zip_path)
            deploy_source_path = zip_path
        else:
            # If no requirements.txt, zip the source directory directly
            shutil.make_archive(zip_path.replace(".zip", ""), "zip", lambda_source_path)
            # Use the source directly for Lambda
            lambda_code = lambda_.Code.from_asset(lambda_source_path)
            deploy_source_path = zip_path

        lambda_function = lambda_.Function(
            self,
            "S3IngestLambda",
            runtime=lambda_.Runtime.PYTHON_3_13,
            handler="index.handler",
            code=lambda_code,
            timeout=Duration.seconds(300),
            memory_size=256,
        )

        # Grant permissions correctly
        iac_assets_bucket.grant_read_write(lambda_function)

        # Deploy the Lambda zip to the IAC assets bucket
        s3deploy.BucketDeployment(
            self,
            "DeployLambdaZip",
            sources=[s3deploy.Source.asset(deploy_source_path)],
            destination_bucket=iac_assets_bucket,
            destination_key_prefix="lambda",
            extract=False,
        )

    #     # Define the paths for Lambda
    #     requirements_path = os.path.join(
    #         lambda_source_path, "requirements.txt"
    #     )

    #     # Create a temporary directory for packaging
    #     lambda_package_path = os.path.join(
    #         os.path.dirname(lambda_source_path), "package"
    #     )
    #     os.makedirs(lambda_package_path, exist_ok=True)

    #     # Create zip file path and name
    #     zip_filename = f"{props.package_name}"
    #     zip_path = os.path.join(
    #         os.path.dirname(lambda_package_path),
    #         zip_filename
    #     )

    #     # Install dependencies and create zip if requirements.txt exists
    #     if os.path.exists(requirements_path):
    #         pip_cmd = (
    #             f'pip install -r {requirements_path} '
    #             f'-t {lambda_package_path}'
    #         )
    #         os.system(pip_cmd)

    #         # Copy Lambda source files to package directory
    #         cp_cmd = (
    #             f'cp {os.path.join(lambda_source_path, "*")} '
    #             f'{lambda_package_path}'
    #         )
    #         os.system(cp_cmd)

    #         # Create zip file from package directory
    #         shutil.make_archive(
    #             zip_path.replace('.zip', ''),
    #             'zip',
    #             lambda_package_path
    #         )

    #         # Use the packaged code for Lambda
    #         lambda_code = lambda_.Code.from_asset(zip_path)
    #         deploy_source_path = zip_path
    #     else:
    #         # If no requirements.txt, zip the source directory directly
    #         shutil.make_archive(
    #             zip_path.replace('.zip', ''),
    #             'zip',
    #             lambda_source_path
    #         )
    #         # Use the source directly for Lambda
    #         _ = lambda_.Code.from_asset(lambda_source_path)
    #         deploy_source_path = zip_path

    #     deployment_bucket = s3.Bucket.from_bucket_name(
    #         self, 'ExistingBucket', f'{props.deployment_bucket}'
    #     )

    #     # Deploy the Lambda zip to the IAC assets bucket
    #     s3deploy.BucketDeployment(
    #         self,
    #         "DeployLambdaZip",
    #         sources=[s3deploy.Source.asset(deploy_source_path)],
    #         destination_bucket=deployment_bucket,
    #         destination_key_prefix=f"{props.deployment_path}"
    #     )

    # @property
    # def deployment_bucket(self) -> str:
    #     """Get the name of the Lambda function."""
    #     return self.deployment_bucket.bucket_name
