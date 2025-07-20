#!/usr/bin/env python3
"""
Custom build script for the custom boto3 layer.
This script installs the custom boto3 and botocore wheel files.
"""
import subprocess
import sys
from pathlib import Path


def build_layer():
    """Build the custom boto3 layer from wheel files"""
    layer_dir = Path(__file__).parent
    python_dir = layer_dir / "python"

    # Create python directory if it doesn't exist
    python_dir.mkdir(exist_ok=True)

    # Find wheel files
    boto3_wheel = layer_dir / "boto3-1.39.4-py3-none-any.whl"
    botocore_wheel = layer_dir / "botocore-1.39.4-py3-none-any.whl"

    if not boto3_wheel.exists():
        raise FileNotFoundError(f"boto3 wheel not found: {boto3_wheel}")
    if not botocore_wheel.exists():
        raise FileNotFoundError(f"botocore wheel not found: {botocore_wheel}")

    # Install wheels
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            str(boto3_wheel),
            str(botocore_wheel),
            "--target",
            str(python_dir),
            "--no-deps",
            "--no-cache-dir",
        ],
        check=True,
    )

    print(f"✅ Custom boto3 layer built successfully in {python_dir}")


if __name__ == "__main__":
    build_layer()
