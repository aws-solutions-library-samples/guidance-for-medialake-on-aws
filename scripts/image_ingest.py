import boto3
import os
from pathlib import Path
from typing import Optional
from botocore.exceptions import ClientError


def upload_to_s3(
    aws_profile: str, bucket_name: str, folder_path: str, prefix: Optional[str] = ""
) -> None:
    """
    Upload all files from a local folder to an S3 bucket using specified AWS profile.

    Args:
        aws_profile (str): AWS profile name to use for authentication
        bucket_name (str): Name of the S3 bucket
        folder_path (str): Path to the local folder containing files to upload
        prefix (str, optional): Prefix to add to S3 object keys
    """
    try:
        # Create a boto3 session with the specified profile
        session = boto3.Session(profile_name=aws_profile)
        s3_client = session.client("s3")

        # Convert folder path to Path object and verify it exists
        folder = Path(folder_path)
        if not folder.exists() or not folder.is_dir():
            raise ValueError(
                f"Folder {folder_path} does not exist or is not a directory"
            )

        # Iterate through all files in the folder
        for file_path in folder.rglob("*"):
            if file_path.is_file():
                # Calculate relative path for S3 key
                relative_path = file_path.relative_to(folder)
                s3_key = str(Path(prefix) / relative_path)

                print(f"Uploading {file_path} to s3://{bucket_name}/{s3_key}")

                try:
                    s3_client.upload_file(str(file_path), bucket_name, s3_key)
                except ClientError as e:
                    print(f"Error uploading {file_path}: {e}")

        print("Upload completed successfully!")

    except Exception as e:
        print(f"An error occurred: {e}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Upload files to S3 bucket")
    parser.add_argument("--profile", required=True, help="AWS profile name")
    parser.add_argument("--bucket", required=True, help="S3 bucket name")
    parser.add_argument("--folder", required=True, help="Local folder path")
    parser.add_argument("--prefix", default="", help="S3 key prefix (optional)")

    args = parser.parse_args()

    upload_to_s3(args.profile, args.bucket, args.folder, args.prefix)
