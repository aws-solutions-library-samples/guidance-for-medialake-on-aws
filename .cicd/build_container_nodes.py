#!/usr/bin/env python3
"""
Build Docker images for container-based pipeline nodes.

Scans node template YAMLs for package_type: Image, builds Docker images,
and optionally pushes them to ECR.

Usage:
    python3 .cicd/build_container_nodes.py --ecr-repo-uri <URI> [--region us-east-1] [--push]
"""

import os
import subprocess  # nosec
import sys
from pathlib import Path

import click
import yaml

sys.path.append(str(Path(__file__).parent.parent))
from config import LAMBDA_BASE_PATH

# Known node categories whose YAML may contain lambda configuration.
_NODE_CATEGORIES = ("integration", "utility", "trigger")


def _get_lambda_config(node_data: dict) -> dict:
    """Extract ``node.<category>.config.lambda`` checking all known categories."""
    node = node_data.get("node", {})
    for category in _NODE_CATEGORIES:
        cfg = node.get(category, {}).get("config", {}).get("lambda", {})
        if cfg:
            return cfg
    return {}


def find_container_nodes():
    """Scan node templates for nodes with package_type: Image."""
    templates_dir = Path("s3_bucket_assets/pipeline_nodes/node_templates")
    container_nodes = []

    for yaml_file in templates_dir.rglob("*.yaml"):
        with open(yaml_file) as f:
            data = yaml.safe_load(f)

        lambda_config = _get_lambda_config(data)

        if lambda_config.get("package_type", "Zip").lower() == "image":
            container_nodes.append(
                {
                    "node_id": data["node"]["id"],
                    "image_tag": lambda_config.get("image_tag", data["node"]["id"]),
                    "dockerfile_path": lambda_config.get("dockerfile_path"),
                    "code_path": (
                        lambda_config.get("handler", "").split("/")
                        if lambda_config.get("handler", "")
                        else []
                    ),
                }
            )

    return container_nodes


def build_image(node, ecr_repo_uri):
    """Build a Docker image for a container node."""
    node_id = node["node_id"]
    image_tag = node["image_tag"]

    # Determine Dockerfile location
    if node["dockerfile_path"] and os.path.exists(node["dockerfile_path"]):
        dockerfile = node["dockerfile_path"]
        context = os.path.dirname(dockerfile)
    else:
        # Use node_id to locate the Lambda source directory (handler is a CDK
        # construct path, not a filesystem path)
        code_path = os.path.join(LAMBDA_BASE_PATH, "nodes", node_id)
        dockerfile = os.path.join(code_path, "Dockerfile")
        context = code_path

        if not os.path.exists(dockerfile):
            print(
                f"WARNING: No Dockerfile found for {node_id} at {dockerfile}, skipping"
            )
            return False

    full_tag = f"{ecr_repo_uri}:{image_tag}"
    print(f"Building container image for {node_id}: {full_tag}")

    subprocess.run(  # nosec
        ["docker", "build", "-t", full_tag, "-f", dockerfile, context],
        check=True,
    )

    return True


def push_images(ecr_repo_uri, region):
    """Authenticate to ECR and push all built images."""
    token = subprocess.run(  # nosec
        ["aws", "ecr", "get-login-password", "--region", region],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    registry = ecr_repo_uri.split("/")[0]
    subprocess.run(  # nosec
        ["docker", "login", "--username", "AWS", "--password-stdin", registry],
        input=token,
        text=True,
        check=True,
    )

    for node in find_container_nodes():
        full_tag = f"{ecr_repo_uri}:{node['image_tag']}"
        print(f"Pushing {full_tag}")
        subprocess.run(["docker", "push", full_tag], check=True)  # nosec


@click.command()
@click.option("--ecr-repo-uri", required=True, help="ECR repository URI")
@click.option("--region", default="us-east-1", help="AWS region")
@click.option(
    "--push/--no-push", default=False, help="Push images to ECR after building"
)
def main(ecr_repo_uri, region, push):
    """Build Docker images for container-based pipeline nodes."""
    nodes = find_container_nodes()
    print(f"Found {len(nodes)} container node(s) to build")

    built = 0
    for node in nodes:
        if build_image(node, ecr_repo_uri):
            built += 1

    print(f"Built {built}/{len(nodes)} container images")

    if push and built > 0:
        push_images(ecr_repo_uri, region)
        print("All images pushed to ECR")


if __name__ == "__main__":
    main()
