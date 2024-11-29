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
import subprocess

from constructs import Construct

class LambdaDeployment(Construct):
    def __init__(self, scope: Construct, id: str, destination_bucket: s3.IBucket, code_path: list, **kwargs):
        super().__init__(scope, id, **kwargs)
        self.id = id

        # Define the paths for Lambda
        lambda_source_path = os.path.abspath(
            # os.path.join(os.path.dirname(__file__), "..", "..", "lambdas", "ingest", "s3")
            os.path.join(os.path.dirname(__file__), "..", "..",*code_path)
        )
        requirements_path = os.path.join(lambda_source_path, "requirements.txt")
        
        # Create a temporary directory for packaging
        lambda_package_path = os.path.join(os.path.dirname(lambda_source_path), "package")
        os.makedirs(lambda_package_path, exist_ok=True)
        
        # Create zip file path and name
        zip_filename = f"{self.id}_lambda_function.zip"
        zip_path = os.path.join(os.path.dirname(lambda_package_path), zip_filename)

        # Install dependencies and create zip if requirements.txt exists
        if os.path.exists(requirements_path):
            # Using manylinux2014_x86_64 platform tag ensures compatibility with AWS Lambda's execution environment
            # --platform: Specifies the target platform for wheel installation
            # --only-binary=:all: Forces pip to use pre-built wheels instead of building from source
            # This helps avoid compatibility issues that can occur when packages are built on different platforms
            # For pip install
            subprocess.run([
                'pip', 'install',
                '-r', requirements_path,
                '-t', lambda_package_path,
                '--platform', 'manylinux2014_x86_64',
                '--only-binary=:all:'
            ], check=True)

            # Use shutil.copy instead of subprocess.run for copying files
            for item in os.listdir(lambda_source_path):
                s = os.path.join(lambda_source_path, item)
                d = os.path.join(lambda_package_path, item)
                if os.path.isfile(s):
                    shutil.copy2(s, d)
            
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
            f'{self.id}-LambdaCodeDeployment',
            sources=[s3deploy.Source.asset(deploy_source_path)],
            destination_bucket=destination_bucket,
            destination_key_prefix=f'lambda-code/{self.id}',
            extract=False
        )
        # zip_key = Fn.select(0, self.deployment.objectKeys)

    @property
    def deployment_key(self) -> str:
        return f"lambda-code/{self.id}/{Fn.select(0, self.deployment.object_keys)}"



# class BaseInfrastructureStack(Stack):
#     def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
#         super().__init__(scope, construct_id, **kwargs)

#         # Create or import your S3 bucket
#         self.lambda_code_bucket = s3.Bucket(self, "LambdaCodeBucket")
#         # Or if you're using an existing bucket:
#         # self.lambda_code_bucket = s3.Bucket.from_bucket_name(self, "LambdaCodeBucket", "your-existing-bucket-name")

#         lambda_deployment = LambdaDeployment(
#             self, 'LambdaDeployment',
#             destination_bucket=self.lambda_code_bucket
#         )

    
