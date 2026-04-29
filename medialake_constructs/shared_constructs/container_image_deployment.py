"""
Container Image Deployment construct for Lambda container nodes.

Builds a Docker image for a Lambda node and pushes it to ECR during CDK synth.
Uses CDK's DockerImageAsset which handles the build + push lifecycle automatically.

Note: DockerImageAsset pushes images to the CDK bootstrap ECR repository
(cdk-hnb659fds-container-assets-*), not to a user-provided repository.
The image_uri property returns the correct URI for Lambda configuration.
"""

import os
import shutil
import tempfile

from aws_cdk import aws_ecr_assets as ecr_assets
from aws_cdk.aws_ecr_assets import Platform
from constructs import Construct


class ContainerImageDeployment(Construct):
    """
    Builds a Docker image for a Lambda node and pushes it to ECR.

    During CDK synth, this construct:
    1. Copies the node's source code to a temp build context
    2. Uses a provided Dockerfile or generates one from a template
    3. Uses CDK's DockerImageAsset to build and push the image

    Example::

        deployment = ContainerImageDeployment(
            self, "ImageProxyContainer",
            code_path=["lambdas", "nodes", "image_proxy"],
            image_tag="image_proxy",
            dockerfile_path="lambdas/nodes/image_proxy/Dockerfile",
        )

        # Use deployment.image_uri to reference the image
    """

    def __init__(
        self,
        scope: Construct,
        id: str,
        code_path: list = None,
        source_path: str = None,
        image_tag: str = "latest",
        dockerfile_path: str = None,
        build_args: dict = None,
        platform: Platform = Platform.LINUX_ARM64,
        **kwargs,
    ):
        super().__init__(scope, id, **kwargs)

        # Resolve source directory
        if source_path:
            lambda_source_path = source_path
        elif code_path:
            lambda_source_path = os.path.abspath(
                os.path.join(os.path.dirname(__file__), "..", "..", *code_path)
            )
        else:
            raise ValueError("Either source_path or code_path must be provided")

        # Resolve Dockerfile path relative to project root
        project_root = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..")
        )

        resolved_dockerfile = None
        if dockerfile_path:
            candidate = os.path.join(project_root, dockerfile_path)
            if os.path.exists(candidate):
                resolved_dockerfile = candidate

        # Build context: copy source + Dockerfile into a temp directory
        build_context = tempfile.mkdtemp(prefix=f"container_{id}_")
        src_dest = os.path.join(build_context, "src")
        shutil.copytree(lambda_source_path, src_dest, dirs_exist_ok=True)

        if resolved_dockerfile:
            shutil.copy2(resolved_dockerfile, os.path.join(build_context, "Dockerfile"))
        else:
            self._generate_dockerfile(build_context, lambda_source_path)

        # Use CDK DockerImageAsset for build + push.
        # Platform defaults to linux/arm64 (Graviton Lambda, cheaper) but can
        # be overridden per-node via the YAML ``architecture`` field to
        # linux/amd64 for libraries that don't ship arm64 wheels. The Lambda
        # function's ``Architectures`` setting must match this platform or
        # the container will fail with Runtime.InvalidEntrypoint /
        # ProcessSpawnFailed at init.
        self._image_asset = ecr_assets.DockerImageAsset(
            self,
            f"{id}-Image",
            directory=build_context,
            build_args=build_args or {},
            platform=platform,
        )

        self._image_tag = image_tag
        self._platform = platform
        self._build_context = build_context

        # DockerImageAsset has consumed the build context; clean up the temp dir
        self._cleanup_build_context()

    def _cleanup_build_context(self):
        """Remove the temporary build context directory."""
        if hasattr(self, "_build_context") and os.path.exists(self._build_context):
            shutil.rmtree(self._build_context, ignore_errors=True)

    def _generate_dockerfile(self, build_context: str, source_path: str):
        """Generate a Dockerfile from a base template when none is provided."""
        has_requirements = os.path.exists(os.path.join(source_path, "requirements.txt"))

        lines = [
            "FROM public.ecr.aws/lambda/python:3.12",
            "",
        ]

        if has_requirements:
            lines.extend(
                [
                    "# Install Python dependencies",
                    "COPY src/requirements.txt /tmp/requirements.txt",
                    "RUN pip install --no-cache-dir -r /tmp/requirements.txt "
                    "-t ${LAMBDA_TASK_ROOT}/ && rm /tmp/requirements.txt",
                    "",
                ]
            )

        lines.extend(
            [
                "# Copy function code",
                "COPY src/ ${LAMBDA_TASK_ROOT}/",
                "",
                "# Set the handler",
                'CMD ["index.lambda_handler"]',
                "",
            ]
        )

        with open(os.path.join(build_context, "Dockerfile"), "w") as f:
            f.write("\n".join(lines))

    @property
    def image_uri(self) -> str:
        """The full image URI including the CDK asset hash tag.

        This points to the CDK bootstrap ECR repository where DockerImageAsset
        pushes the image. Use this URI when configuring Lambda container images.
        """
        return self._image_asset.image_uri

    @property
    def image_tag(self) -> str:
        """The CDK asset image hash tag (the actual deployed tag).

        Returns the content-hash tag assigned by DockerImageAsset, not the
        user-provided logical tag. Use ``image_uri`` for Lambda configuration.
        """
        return self._image_asset.asset_hash

    @property
    def platform(self) -> Platform:
        """The Docker build platform (LINUX_ARM64 or LINUX_AMD64).

        The Lambda function created to run this image MUST use a matching
        ``architectures`` setting (``arm64`` ↔ LINUX_ARM64, ``x86_64`` ↔
        LINUX_AMD64) or initialization will fail.
        """
        return self._platform
