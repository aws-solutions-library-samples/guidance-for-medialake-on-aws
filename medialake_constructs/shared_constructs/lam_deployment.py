# In a new file, e.g., lambda_deployment.py
from aws_cdk import (
    aws_lambda as lambda_,
    aws_s3_deployment as s3deploy,
    aws_s3 as s3,
    Duration,
    Stack,
    Fn
)
import os
import shutil

from constructs import Construct

class LambdaDeployment(Construct):
    def __init__(self, scope: Construct, id: str, destination_bucket: s3.IBucket, **kwargs):
        super().__init__(scope, id, **kwargs)

        # Define the paths for Lambda
        lambda_source_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", "lambdas", "ingest", "s3")
        )
        requirements_path = os.path.join(lambda_source_path, "requirements.txt")
        
        # Create a temporary directory for packaging
        lambda_package_path = os.path.join(os.path.dirname(lambda_source_path), "package")
        os.makedirs(lambda_package_path, exist_ok=True)
        
        # Create zip file path and name
        zip_filename = "lambda_function.zip"
        zip_path = os.path.join(os.path.dirname(lambda_package_path), zip_filename)

        # Install dependencies and create zip if requirements.txt exists
        if os.path.exists(requirements_path):
            pip_cmd = f'pip install -r {requirements_path} -t {lambda_package_path}'
            os.system(pip_cmd)
            
            # Copy Lambda source files to package directory
            cp_cmd = f'cp {os.path.join(lambda_source_path, "*")} {lambda_package_path}'
            os.system(cp_cmd)
            
            # Create zip file from package directory
            shutil.make_archive(zip_path.replace('.zip', ''), 'zip', lambda_package_path)
            
            # Use the packaged code for Lambda
            lambda_code = lambda_.Code.from_asset(zip_path)
            deploy_source_path = zip_path
        else:
            # If no requirements.txt, zip the source directory directly
            shutil.make_archive(zip_path.replace('.zip', ''), 'zip', lambda_source_path)
            # Use the source directly for Lambda
            lambda_code: lambda_.AssetCode = lambda_.Code.from_asset(lambda_source_path)
            deploy_source_path: str = zip_path

        # Deploy the Lambda zip to the destination bucket
        self.deployment = s3deploy.BucketDeployment(
            self,
            'LambdaCodeDeployment',
            sources=[s3deploy.Source.asset(deploy_source_path)],
            destination_bucket=destination_bucket,
            destination_key_prefix='lambda-code',
            extract=False
        )
        # zip_key = Fn.select(0, self.deployment.objectKeys)

    @property
    def deployment_key(self) -> str:
        return f"lambda-code/{Fn.select(0, self.deployment.object_keys)}"
