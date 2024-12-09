import boto3
import argparse
import re
from botocore.exceptions import ClientError


def parse_arguments():
    parser = argparse.ArgumentParser(description="Delete S3 buckets matching a pattern")
    parser.add_argument("--profile", required=True, help="AWS profile name")
    parser.add_argument(
        "--pattern", required=True, help="Pattern to match bucket names"
    )
    return parser.parse_args()


def empty_bucket(s3_resource, bucket_name):
    try:
        bucket = s3_resource.Bucket(bucket_name)
        # Delete all object versions
        bucket.object_versions.delete()
        print(f"Emptied bucket: {bucket_name}")
        return True
    except ClientError as e:
        print(f"Error emptying bucket {bucket_name}: {e}")
        return False


def delete_bucket(s3_client, bucket_name):
    try:
        s3_client.delete_bucket(Bucket=bucket_name)
        print(f"Deleted bucket: {bucket_name}")
        return True
    except ClientError as e:
        print(f"Error deleting bucket {bucket_name}: {e}")
        return False


def main():
    args = parse_arguments()

    # Create session with specified profile
    session = boto3.Session(profile_name=args.profile)
    s3_client = session.client("s3")
    s3_resource = session.resource("s3")

    # List all buckets
    try:
        response = s3_client.list_buckets()
        buckets = [bucket["Name"] for bucket in response["Buckets"]]
    except ClientError as e:
        print(f"Error listing buckets: {e}")
        return

    # Find matching buckets
    pattern = re.compile(args.pattern)
    matching_buckets = [bucket for bucket in buckets if pattern.search(bucket)]

    if not matching_buckets:
        print(f"No buckets found matching pattern: {args.pattern}")
        return

    print(f"Found {len(matching_buckets)} matching buckets:")
    for bucket in matching_buckets:
        print(f"Processing bucket: {bucket}")
        if empty_bucket(s3_resource, bucket):
            delete_bucket(s3_client, bucket)


if __name__ == "__main__":
    main()
