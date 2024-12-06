import tempfile
import os
import shutil
import subprocess
from aws_cdk import (
    aws_s3_deployment as s3deploy,
    aws_s3 as s3,
    Fn,
)
from constructs import Construct


class LambdaDeployment(Construct):

    def __init__(
        self,
        scope: Construct,
        id: str,
        destination_bucket: s3.IBucket,
        code_path: list,
        runtime: str = "python3.12",
        **kwargs,
    ):
        super().__init__(scope, id, **kwargs)
        self.id = id

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

            self.deployment = s3deploy.BucketDeployment(
                self,
                f"{self.id}-LambdaCodeDeployment",
                sources=[s3deploy.Source.asset(zip_path)],
                destination_bucket=destination_bucket,
                destination_key_prefix=f"lambda-code/{self.id}",
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
        return f"lambda-code/{self.id}/{Fn.select(0, self.deployment.object_keys)}"
