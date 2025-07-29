import os
import shutil
import subprocess
import tempfile

from aws_cdk import Fn
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_s3_deployment as s3deploy
from constructs import Construct


class LambdaDeployment(Construct):
    """
        A construct that packages Lambda code and deploys it to an S3 bucket.

        This construct handles packaging Lambda code (Python or Node.js) with its dependencies,
        creating a zip file, and deploying it to an S3 bucket.

        When layers are provided, their content is extracted and included directly in the Lambda
        deployment package. This is particularly useful for:
        1. Reducing cold start times by eliminating the need to download layers separately
        2. Ensuring consistent access to layer resources in all environments
        3. Simplifying deployment by bundling everything into a single package

        Example:

    python
        # Create a Lambda deployment with layers
        lambda_deployment = LambdaDeployment(
            self,
            "MyLambda",
            destination_bucket=my_bucket,
            code_path=["lambdas", "my_function"],

        )

        # Create the Lambda function with the deployment
        lambda_function = lambda_.Function(
            self,
            "MyLambdaFunction",
            code=lambda_.S3Code(
                bucket=my_bucket,
                key=lambda_deployment.deployment_key
            ),
            handler="index.handler",
            runtime=lambda_.Runtime.PYTHON_3_12,
            # No need to specify layers here as they're already baked into the deployment
        )

    """

    def __init__(
        self,
        scope: Construct,
        id: str,
        destination_bucket: s3.IBucket,
        code_path: list,
        runtime: str = "python3.12",
        parent_folder: str = "",
        **kwargs,
    ):
        """
        Initialize a new LambdaDeployment.

        Parameters:
        -----------
        scope: Construct
            The scope in which to define this construct
        id: str
            The ID of this construct
        destination_bucket: s3.IBucket
            The S3 bucket where the Lambda code will be deployed
        code_path: list
            A list of path components to the Lambda code
        runtime: str
            The Lambda runtime (default: "python3.12")
        parent_folder: str
            An optional parent folder for the Lambda code in the S3 bucket

        """
        super().__init__(scope, id, **kwargs)
        self.id = id
        self.parent_folder = parent_folder

        lambda_source_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", *code_path)
        )
        with tempfile.TemporaryDirectory() as lambda_package_path:
            zip_filename = f"{self.id}_lambda_function.zip"
            zip_path = os.path.join(os.path.dirname(lambda_package_path), zip_filename)

            if runtime.startswith("python"):
                self._package_python_lambda(
                    lambda_source_path, lambda_package_path, zip_path
                )
            elif runtime.startswith("nodejs"):
                self._package_nodejs_lambda(
                    lambda_source_path, lambda_package_path, zip_path
                )
            else:
                raise ValueError(f"Unsupported runtime: {runtime}")

            # Construct the destination_key_prefix
            if parent_folder:
                destination_key_prefix = f"lambda-code/{parent_folder}/{self.id}"
            else:
                destination_key_prefix = f"lambda-code/{self.id}"

            self.deployment = s3deploy.BucketDeployment(
                self,
                f"{self.id}-LambdaCodeDeployment",
                sources=[s3deploy.Source.asset(zip_path)],
                destination_bucket=destination_bucket,
                destination_key_prefix=destination_key_prefix,
                extract=False,
            )

    def _package_python_lambda(self, source_path, package_path, zip_path):
        requirements_path = os.path.join(source_path, "requirements.txt")
        if os.path.exists(requirements_path):
            subprocess.run(
                [
                    "pip",
                    "install",
                    "-r",
                    requirements_path,
                    "-t",
                    package_path,
                    "--platform",
                    "manylinux2014_x86_64",
                    "--only-binary=:all:",
                ],
                check=True,
            )

        # Copy source files to package directory
        for item in os.listdir(source_path):
            s = os.path.join(source_path, item)
            d = os.path.join(package_path, item)
            if os.path.isfile(s):
                shutil.copy2(s, d)

        shutil.make_archive(zip_path.replace(".zip", ""), "zip", package_path)

    def _package_nodejs_lambda(self, source_path, package_path, zip_path):
        package_json_path = os.path.join(source_path, "package.json")
        if os.path.exists(package_json_path):
            subprocess.run(["npm", "install"], cwd=source_path, check=True)

        shutil.copytree(source_path, package_path, dirs_exist_ok=True)
        shutil.make_archive(zip_path.replace(".zip", ""), "zip", package_path)

    @property
    def deployment_key(self) -> str:
        if self.parent_folder:
            return f"lambda-code/{self.parent_folder}/{self.id}/{Fn.select(0, self.deployment.object_keys)}"
        else:
            return f"lambda-code/{self.id}/{Fn.select(0, self.deployment.object_keys)}"
