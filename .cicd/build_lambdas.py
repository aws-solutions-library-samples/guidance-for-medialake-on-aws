#!/usr/bin/env python3
import json
import os
import shutil
import subprocess  # nosec
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
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

# Number of parallel pip install workers.
# Kept modest to avoid pip lock contention and memory pressure in CodeBuild.
PIP_WORKERS = int(os.environ.get("LAMBDA_BUILD_WORKERS", "4"))


class LambdaBuilder:
    def __init__(self):
        self.lambdas_root_path = Path(LAMBDA_BASE_PATH)
        self.layers_root_path = Path(LAYER_BASE_PATH)
        self.build_path = Path(DIST_PATH)
        self.lambda_build_path = Path(LAMBDA_DIST_PATH)
        self.layer_build_path = Path(LAYER_DIST_PATH)

    def _detect_lambda_type(self, lambda_dir: Path) -> str:
        """Detect the type of Lambda function based on files present

        Returns:
            str: 'python', 'nodejs', or 'unknown'
        """
        has_python = any(
            item.is_file() and item.suffix == ".py" for item in lambda_dir.iterdir()
        )
        has_nodejs = any(
            item.is_file() and item.suffix == ".js" for item in lambda_dir.iterdir()
        )
        has_package_json = (lambda_dir / "package.json").exists()

        if has_nodejs or has_package_json:
            return "nodejs"
        elif has_python:
            return "python"
        else:
            return "unknown"

    # Native layer directories that are built by external scripts (not by this builder).
    # These are cached in CI and should not be wiped during clean.
    NATIVE_LAYER_NAMES = {"ffprobe", "ffmpeg", "resvg", "numpy", "openexr"}

    def clean_build(self):
        """Remove previous build artifacts, preserving cached native layers."""
        if not self.build_path.exists():
            self.build_path.mkdir(parents=True, exist_ok=True)
            return

        # Preserve native layer directories that may have been restored from cache.
        # Store them *outside* the build_path so rmtree doesn't destroy them.
        preserve_root = self.build_path.parent / ".preserve_layers"
        preserved: dict[str, Path] = {}
        for name in self.NATIVE_LAYER_NAMES:
            layer_dir = self.layer_build_path / name
            if layer_dir.exists():
                preserve_root.mkdir(parents=True, exist_ok=True)
                tmp = preserve_root / name
                shutil.move(str(layer_dir), str(tmp))
                preserved[name] = tmp

        shutil.rmtree(self.build_path)
        self.build_path.mkdir(parents=True, exist_ok=True)

        # Restore preserved native layers
        if preserved:
            self.layer_build_path.mkdir(parents=True, exist_ok=True)
            for name, tmp in preserved.items():
                shutil.move(str(tmp), str(self.layer_build_path / name))
                print(f"♻️  Preserved cached native layer: {name}")
            # Clean up the temporary preserve directory
            if preserve_root.exists():
                shutil.rmtree(preserve_root)

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

    def build_lambda(self, lambda_dir: Path, parent_path: str) -> bool:
        """Build individual lambda function

        Returns:
            bool: True if the directory was built as a Lambda function, False otherwise
        """
        if not lambda_dir.is_dir() or lambda_dir.name.startswith("."):
            return False

        # Check if this directory has any files at the root level
        # If it only contains subdirectories, it's an organizational directory, not a Lambda
        has_files = any(item.is_file() for item in lambda_dir.iterdir())

        if not has_files:
            return False

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

        return True

    def build_lambda_js(self, lambda_dir: Path, parent_path: str) -> bool:
        """Build individual JS lambda function

        Returns:
            bool: True if the directory was built as a Lambda function, False otherwise
        """
        if not lambda_dir.is_dir() or lambda_dir.name.startswith("."):
            return False

        # Check if this directory has any files at the root level
        has_files = any(item.is_file() for item in lambda_dir.iterdir())

        if not has_files:
            return False

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

            return True
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
            ],
            check=True,
        )

    def build_all(self):
        """Build all lambda functions and layers.

        Layers are built first (sequentially — there are few of them).
        Lambda file copies happen sequentially (fast, no I/O wait).
        pip install calls are then run in parallel across all Lambdas
        that have a requirements.txt, which is the main time sink.
        """
        print("🏗️  Building Lambda functions...")

        self.clean_build()

        # 1. Build layers (sequential — typically only ~8 layers)
        for layer_dir in self.layers_root_path.iterdir():
            self.build_layer(layer_dir)

        # 2. Collect all Lambda build targets and copy files (fast)
        pip_jobs: list[tuple[Path, Path]] = []  # (requirements.txt, target_dir)
        self._collect_and_copy(
            self.lambdas_root_path, self.lambdas_root_path.name, pip_jobs
        )

        # 3. Run pip installs in parallel
        if pip_jobs:
            print(
                f"📦 Installing requirements for {len(pip_jobs)} Lambdas ({PIP_WORKERS} workers)..."
            )
            errors: list[str] = []
            with ThreadPoolExecutor(max_workers=PIP_WORKERS) as pool:
                futures = {
                    pool.submit(self._install_requirements, req, target): str(req)
                    for req, target in pip_jobs
                }
                for future in as_completed(futures):
                    req_path = futures[future]
                    try:
                        future.result()
                    except subprocess.CalledProcessError as exc:
                        errors.append(f"{req_path}: exit code {exc.returncode}")
            if errors:
                for err in errors:
                    print(f"❌ {err}")
                raise SystemExit("pip install failed for one or more Lambdas")

        print("✅ Lambda build complete")

    def _collect_and_copy(
        self,
        path: Path,
        parent_path: str,
        pip_jobs: list[tuple[Path, Path]],
    ):
        """Walk the Lambda tree, copy source files, and collect pip install jobs."""
        for item in path.iterdir():
            if item.is_dir() and (item.name == "layers"):
                continue
            elif not item.is_dir() or item.name.startswith("."):
                continue

            lambda_type = self._detect_lambda_type(item)
            child_path = f"{parent_path}/{item.name}"
            was_built = False

            if lambda_type == "nodejs":
                was_built = self.build_lambda_js(item, child_path)
            elif lambda_type == "python":
                was_built = self._copy_lambda_files(item, child_path, pip_jobs)

            if not was_built:
                self._collect_and_copy(item, child_path, pip_jobs)

    def _copy_lambda_files(
        self,
        lambda_dir: Path,
        parent_path: str,
        pip_jobs: list[tuple[Path, Path]],
    ) -> bool:
        """Copy Lambda source files and queue pip install for later parallel execution.

        Returns:
            bool: True if the directory was built as a Lambda function, False otherwise
        """
        if not lambda_dir.is_dir() or lambda_dir.name.startswith("."):
            return False

        has_files = any(item.is_file() for item in lambda_dir.iterdir())
        if not has_files:
            return False

        lambda_build = self.lambda_build_path.parent / parent_path
        lambda_build.mkdir(parents=True, exist_ok=True)

        print(f"🔨 Copying {lambda_dir.name} → {lambda_build}")

        for item in lambda_dir.iterdir():
            if item.is_file() and item.suffix == ".py":
                shutil.copy2(item, lambda_build)
            elif item.is_dir() and not item.name.startswith("."):
                target_dir = lambda_build / item.name
                if target_dir.exists():
                    shutil.rmtree(target_dir)
                shutil.copytree(item, target_dir)

        # Queue pip install for parallel execution instead of running inline
        req_file = lambda_dir / "requirements.txt"
        if req_file.exists():
            pip_jobs.append((req_file, lambda_build))

        return True

    def recursive_build(self, path: Path, parent_path):
        """Recursively build lambda functions (legacy sequential path)"""
        for item in path.iterdir():
            if item.is_dir() and (item.name == "layers"):
                continue
            elif not item.is_dir() or item.name.startswith("."):
                continue

            # Detect Lambda type and build accordingly
            lambda_type = self._detect_lambda_type(item)
            was_built = False

            if lambda_type == "nodejs":
                was_built = self.build_lambda_js(item, parent_path + "/" + item.name)
            elif lambda_type == "python":
                was_built = self.build_lambda(item, parent_path + "/" + item.name)

            # Only recurse into subdirectories if this wasn't built as a Lambda
            if not was_built:
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
