import json
import os
import time

import boto3
from lambda_utils import lambda_handler_decorator, logger

VECTOR_DIMENSION = 1024  # Twelve Labs embeddings dimension
MAX_VECTOR_DIMENSION = 4096  # S3 Vector maximum supported dimension


def vector_bucket_exists(s3_vector_client, bucket_name: str) -> bool:
    """
    Check if S3 Vector bucket already exists using GetVectorBucket API.
    """
    try:
        response = s3_vector_client.get_vector_bucket(vectorBucketName=bucket_name)
        logger.info(
            "Vector bucket exists",
            extra={"bucket_name": bucket_name, "response": response},
        )
        return True
    except s3_vector_client.exceptions.NotFoundException:
        logger.info("Vector bucket does not exist", extra={"bucket_name": bucket_name})
        return False
    except Exception as e:
        logger.error(
            "Error checking vector bucket existence",
            extra={"bucket_name": bucket_name, "error": str(e)},
            exc_info=True,
        )
        raise


def index_exists(s3_vector_client, bucket_name: str, index_name: str) -> bool:
    """
    Check if S3 Vector index already exists using GetIndex API.
    """
    try:
        response = s3_vector_client.get_index(
            vectorBucketName=bucket_name, indexName=index_name
        )
        logger.info(
            "Vector index exists",
            extra={
                "bucket_name": bucket_name,
                "index_name": index_name,
                "response": response,
            },
        )
        return True
    except s3_vector_client.exceptions.NotFoundException:
        logger.info(
            "Vector index does not exist",
            extra={"bucket_name": bucket_name, "index_name": index_name},
        )
        return False
    except Exception as e:
        logger.error(
            "Error checking vector index existence",
            extra={
                "bucket_name": bucket_name,
                "index_name": index_name,
                "error": str(e),
            },
            exc_info=True,
        )
        raise


def delete_index(s3_vector_client, bucket_name: str, index_name: str) -> None:
    """
    Delete S3 Vector index using DeleteIndex API.
    """
    try:
        s3_vector_client.delete_index(
            vectorBucketName=bucket_name, indexName=index_name
        )
        logger.info(
            "Vector index deleted",
            extra={"bucket_name": bucket_name, "index_name": index_name},
        )
    except s3_vector_client.exceptions.NotFoundException:
        logger.info(
            "Vector index did not exist during deletion",
            extra={"bucket_name": bucket_name, "index_name": index_name},
        )
    except Exception as e:
        logger.error(
            "Error deleting vector index",
            extra={
                "bucket_name": bucket_name,
                "index_name": index_name,
                "error": str(e),
            },
            exc_info=True,
        )
        raise


def wait_for_index_deletion(
    s3_vector_client,
    bucket_name: str,
    index_name: str,
    timeout: int = 60,
    interval: int = 2,
) -> None:
    """
    Poll until GetIndex returns NotFoundException, or timeout expires.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not index_exists(s3_vector_client, bucket_name, index_name):
            logger.info(
                "Index confirmed deleted",
                extra={"bucket_name": bucket_name, "index_name": index_name},
            )
            return
        time.sleep(interval)
    raise TimeoutError(
        f"Index {index_name} in bucket {bucket_name} still exists after {timeout}s"
    )


def create_vector_bucket(s3_vector_client, bucket_name: str, region: str) -> bool:
    """
    Create S3 Vector bucket using CreateVectorBucket API.
    """
    try:
        # Check if bucket already exists
        if vector_bucket_exists(s3_vector_client, bucket_name):
            logger.info(
                "Vector bucket already exists", extra={"bucket_name": bucket_name}
            )
            return True

        # Create the vector bucket
        encryption_config = {"sseType": "AES256"}  # Using AES256 encryption

        response = s3_vector_client.create_vector_bucket(
            vectorBucketName=bucket_name, encryptionConfiguration=encryption_config
        )

        logger.info(
            "Vector bucket created successfully",
            extra={"bucket_name": bucket_name, "response": response},
        )
        return True

    except Exception as e:
        logger.error(
            "Failed to create vector bucket",
            extra={"bucket_name": bucket_name, "error": str(e)},
            exc_info=True,
        )
        raise


def create_vector_index_with_retry(
    s3_vector_client,
    bucket_name: str,
    index_name: str,
    dimension: int,
    max_retries: int = 5,
    recreate_if_exists: bool = True,
) -> bool:
    """
    Create S3 Vector index with retry logic and exponential backoff.
    If recreate_if_exists is True and the index already exists, delete it and wait for deletion before creating.
    If recreate_if_exists is False and the index already exists, return True without recreating.
    """
    # Check if index already exists
    if index_exists(s3_vector_client, bucket_name, index_name):
        if recreate_if_exists:
            logger.info(
                "Index exists – deleting before recreation",
                extra={"bucket_name": bucket_name, "index_name": index_name},
            )
            delete_index(s3_vector_client, bucket_name, index_name)
            wait_for_index_deletion(s3_vector_client, bucket_name, index_name)
        else:
            logger.info(
                "Index already exists – skipping creation",
                extra={"bucket_name": bucket_name, "index_name": index_name},
            )
            return True

    logger.info(
        "Creating S3 Vector index",
        extra={
            "bucket_name": bucket_name,
            "index_name": index_name,
            "dimension": dimension,
        },
    )

    for attempt in range(max_retries):
        try:
            # Create the vector index
            response = s3_vector_client.create_index(
                vectorBucketName=bucket_name,
                indexName=index_name,
                dimension=dimension,
                dataType="float32",  # Using float32 for embeddings
                distanceMetric="cosine",  # Default distance metric
            )

            logger.info(
                "Vector index creation successful",
                extra={
                    "bucket_name": bucket_name,
                    "index_name": index_name,
                    "dimension": dimension,
                    "attempt": attempt + 1,
                    "response": response,
                },
            )
            return True

        except Exception as e:
            logger.error(
                "Failed to create S3 Vector index",
                extra={
                    "bucket_name": bucket_name,
                    "index_name": index_name,
                    "dimension": dimension,
                    "error": str(e),
                    "attempt": attempt + 1,
                    "max_retries": max_retries,
                },
                exc_info=True,
            )

            # Don't retry on certain errors
            if hasattr(e, "response") and e.response.get("Error", {}).get("Code") in [
                "InvalidParameterValue",
                "ValidationException",
            ]:
                logger.error(
                    "Non-retryable error encountered",
                    extra={"error_code": e.response.get("Error", {}).get("Code")},
                )
                break

        # Exponential backoff
        if attempt < max_retries - 1:
            backoff_time = 2**attempt
            logger.info(
                "Retrying index creation after backoff",
                extra={
                    "bucket_name": bucket_name,
                    "index_name": index_name,
                    "attempt": attempt + 1,
                    "max_retries": max_retries,
                    "backoff_seconds": backoff_time,
                },
            )
            time.sleep(backoff_time)

    return False


@lambda_handler_decorator(cors=True)
def handler(event, context):
    """
    Lambda handler for creating S3 Vector buckets and indexes

    Args:
        event: Lambda event
        context: Lambda context

    Returns:
        dict: Response indicating success or failure
    """
    logger.info("Received event", extra={"event": event})

    req_type = event.get("RequestType")
    if req_type not in ["Create", "Update"]:
        logger.info(
            "Skipping non-Create/Update request", extra={"RequestType": req_type}
        )
        return {"statusCode": 200, "body": f"Skipped {req_type} request"}

    # Determine if we should recreate existing resources
    recreate_if_exists = req_type == "Create"
    logger.info(
        "Processing request",
        extra={"RequestType": req_type, "recreate_if_exists": recreate_if_exists},
    )

    # Environment variables
    bucket_name = os.environ["VECTOR_BUCKET_NAME"]
    index_names = os.environ["INDEX_NAMES"]
    region = os.environ["REGION"]
    vector_dimension = int(os.environ.get("VECTOR_DIMENSION", VECTOR_DIMENSION))

    # Validate dimension
    if vector_dimension > MAX_VECTOR_DIMENSION:
        raise ValueError(
            f"Vector dimension {vector_dimension} exceeds maximum supported "
            f"dimension {MAX_VECTOR_DIMENSION}"
        )

    logger.info(
        "Environment configuration",
        extra={
            "bucket_name": bucket_name,
            "indexes": index_names,
            "region": region,
            "vector_dimension": vector_dimension,
        },
    )

    # Initialize S3 Vector client using the custom boto3 SDK
    try:
        session = boto3.Session()
        s3_vector_client = session.client("s3vectors", region_name=region)
        logger.info("S3 Vector client initialized successfully")
    except Exception as e:
        logger.error(
            "Failed to initialize S3 Vector client",
            extra={"error": str(e)},
            exc_info=True,
        )
        raise

    # Create vector bucket first
    try:
        bucket_created = create_vector_bucket(s3_vector_client, bucket_name, region)
        if not bucket_created:
            raise Exception(f"Failed to create vector bucket {bucket_name}")
    except Exception as e:
        logger.error(
            "Vector bucket creation failed",
            extra={"bucket_name": bucket_name, "error": str(e)},
            exc_info=True,
        )
        raise

    # Create indexes
    indexes = index_names.split(",")
    logger.info(f"Creating {len(indexes)} vector indexes", extra={"indexes": indexes})

    for index_name in indexes:
        index_name = index_name.strip()
        logger.info(
            "Processing vector index",
            extra={"bucket_name": bucket_name, "index_name": index_name},
        )

        success = create_vector_index_with_retry(
            s3_vector_client,
            bucket_name,
            index_name,
            vector_dimension,
            recreate_if_exists=recreate_if_exists,
        )

        if not success:
            msg = (
                f"Failed to create vector index {index_name} in bucket "
                f"{bucket_name} after multiple retries"
            )
            logger.error(msg)
            raise Exception(msg)

    logger.info("Successfully created all vector indexes and bucket")
    return {
        "statusCode": 200,
        "body": json.dumps(
            {
                "message": "All vector indexes and bucket created successfully",
                "bucket_name": bucket_name,
                "indexes": indexes,
                "vector_dimension": vector_dimension,
            }
        ),
    }
