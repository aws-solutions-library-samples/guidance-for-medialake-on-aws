#!/usr/bin/env python3
import json
import shutil
import subprocess  # nosec
import sys
from pathlib import Path

import click

# Add CDK directory to Python path
sys.path.append(str(Path(__file__).parent.parent))

from config import (
    DIST_PATH,
    LAMBDA_BASE_PATH,
    LAMBDA_DIST_PATH,
    LAYER_BASE_PATH,
    LAYER_DIST_PATH,
)


class LambdaBuilder:
    def __init__(self):
        self.lambdas_root_path = Path(LAMBDA_BASE_PATH)
        self.layers_root_path = Path(LAYER_BASE_PATH)
        self.build_path = Path(DIST_PATH)
        self.lambda_build_path = Path(LAMBDA_DIST_PATH)
        self.layer_build_path = Path(LAYER_DIST_PATH)

    def clean_build(self):
        """Remove previous build artifacts"""
        if self.build_path.exists():
            shutil.rmtree(self.build_path)
        self.build_path.mkdir(parents=True, exist_ok=True)

    def build_layer(self, layer_dir: Path):
        """Build layer if it exists"""
        if not layer_dir.is_dir() or layer_dir.name.startswith("."):
            return

        layer_build = self.layer_build_path / layer_dir.name
        layer_build.mkdir(parents=True, exist_ok=True)

        print(f"🔨 Building layer {layer_dir.name}...")

        # Check for custom build script first
        build_script = layer_dir / "build.py"
        if build_script.exists():
            print(f"  Using custom build script for {layer_dir.name}")
            # Run custom build script in the layer directory
            subprocess.run(
                ["python3", str(build_script)], cwd=str(layer_dir), check=True
            )

            # Copy the built python directory to the layer build path
            layer_python_dir = layer_dir / "python"
            if layer_python_dir.exists():
                target_python_dir = layer_build / "python"
                if target_python_dir.exists():
                    shutil.rmtree(target_python_dir)
                shutil.copytree(layer_python_dir, target_python_dir)
            return

        # Create python directory for the layer
        python_dir = layer_build / "python"
        python_dir.mkdir(parents=True, exist_ok=True)

        # Copy Python files and directories
        for item in layer_dir.iterdir():
            if item.is_file() and item.suffix == ".py":
                shutil.copy2(item, python_dir)
            elif item.is_dir() and not item.name.startswith("."):
                target_dir = python_dir / item.name
                if target_dir.exists():
                    shutil.rmtree(target_dir)
                shutil.copytree(item, target_dir)

        # Install requirements
        req_file = layer_dir / "requirements.txt"
        if req_file.exists():
            self._install_requirements(req_file, python_dir)

    def build_lambda(self, lambda_dir: Path, parent_path: str):
        """Build individual lambda function"""
        if not lambda_dir.is_dir() or lambda_dir.name.startswith("."):
            return

        # Lambda dir should not have any subdirectory
        if any(item.is_dir() for item in lambda_dir.iterdir()):
            return

        lambda_build = self.lambda_build_path.parent / parent_path
        lambda_build.mkdir(parents=True, exist_ok=True)

        print(f"🔨 Building {lambda_dir.name} in {lambda_build}...")

        # Copy Python files and directories
        for item in lambda_dir.iterdir():
            if item.is_file() and item.suffix == ".py":
                shutil.copy2(item, lambda_build)
            elif item.is_dir() and not item.name.startswith("."):
                target_dir = lambda_build / item.name
                if target_dir.exists():
                    shutil.rmtree(target_dir)
                shutil.copytree(item, target_dir)

        # Install requirements
        req_file = lambda_dir / "requirements.txt"
        if req_file.exists():
            self._install_requirements(req_file, lambda_build)

    def build_lambda_js(self, lambda_dir: Path, parent_path: str):
        """Build individual JS lambda function"""
        if not lambda_dir.is_dir() or lambda_dir.name.startswith("."):
            return

        # Lambda dir should not have any subdirectory
        if any(
            (item.is_dir() and item.name != "node_modules")
            for item in lambda_dir.iterdir()
        ):
            return

        lambda_build = self.lambda_build_path.parent / parent_path
        lambda_build.mkdir(parents=True, exist_ok=True)

        print(f"🔨 Building {lambda_dir.name} in {lambda_build}...")

        try:
            subprocess.run(  # nosec
                ["npm", "install", "--prefix", str(lambda_dir)],
                check=True,
            )

            subprocess.run(  # nosec
                [
                    "esbuild",
                    "--bundle",
                    "%s/index.js" % lambda_dir,
                    "--target=node20",
                    "--platform=node",
                    "--outfile=%s/index.js" % lambda_build,
                    '--external:"@aws-sdk/*"',
                    "--external:exifr",
                ],
                check=True,
            )

            with open("%s/package.json" % lambda_build, "w", encoding="utf-8") as f:
                json.dump(
                    {"dependencies": {"exifr": "7.1.3"}},
                    f,
                    ensure_ascii=False,
                    indent=4,
                )

            subprocess.run(  # nosec
                [
                    "cp",
                    "%s/lock.json" % lambda_dir,
                    "%s/package-lock.json" % lambda_build,
                ],
                check=True,
            )

            subprocess.run(  # nosec
                [
                    "npm",
                    "--prefix",
                    str(lambda_build),
                    "ci",
                    "run",
                ],
                check=True,
            )

        except subprocess.CalledProcessError as e:
            print(e.returncode)
            print(e.output)
            print(e)

            raise

    def _install_requirements(self, req_file: Path, target_dir: Path):
        """Install Python requirements in the target directory"""
        subprocess.run(  # nosec
            [
                "pip",
                "install",
                "-r",
                str(req_file),
                "--target",
                str(target_dir),
                "--no-cache-dir",
            ],
            check=True,
        )

    def build_all(self):
        """Build all lambda functions"""
        print("🏗️  Building Lambda functions...")

        self.clean_build()

        for layer_dir in self.layers_root_path.iterdir():
            self.build_layer(layer_dir)

        # build Lambda functions
        self.recursive_build(self.lambdas_root_path, self.lambdas_root_path.name)

        print("✅ Lambda build complete")

    def recursive_build(self, path: Path, parent_path):
        """Recursively build lambda functions"""
        for item in path.iterdir():
            if item.is_dir() and (item.name == "layers"):
                continue
            elif not item.is_dir() or item.name.startswith("."):
                continue

            if item.name == "image_metadata_extractor":
                self.build_lambda_js(item, parent_path + "/" + item.name)
            else:
                self.build_lambda(item, parent_path + "/" + item.name)

            self.recursive_build(item, "%s/%s" % (parent_path, item.name))


@click.group()
def cli():
    """AWS Lambda Build Tool - Manages building of Lambda functions and shared layers"""


@cli.command()
@click.option(
    "--root",
    default=LAMBDA_BASE_PATH,
    help="Root directory containing Lambda functions",
)
def build(root):
    """Build all Lambda functions and shared layers"""
    builder = LambdaBuilder()
    builder.build_all()


@cli.command()
@click.option(
    "--root",
    default=LAMBDA_BASE_PATH,
    help="Root directory containing Lambda functions",
)
def clean(root):
    """Clean build artifacts"""
    builder = LambdaBuilder()
    builder.clean_build()
    click.echo("🧹 Build directory cleaned")


if __name__ == "__main__":
    cli()
