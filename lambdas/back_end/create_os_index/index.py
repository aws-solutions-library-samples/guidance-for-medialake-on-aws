"""
OpenSearch Index Creation for Media Assets

ARCHITECTURE: Separate Documents Approach
------------------------------------------
Clip embeddings are stored as individual documents (not nested arrays) to avoid:
- Document size limits (4GB max caused circuit breaker errors)
- Version conflicts from concurrent writes to same parent document
- Slow updates as arrays grow large

Each clip document has parent_asset_id linking to its master asset document.
Search queries filter by embedding_scope="clip" and group results by parent_asset_id.
"""

import json
import os
import time

import boto3
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from lambda_utils import lambda_handler_decorator, logger
from requests import request

VECTOR_DIMENSION = 1024  # Twelve Labs embeddings dimension

# Index name for the separate asset embeddings index (Marengo 3.0)
ASSET_EMBEDDINGS_INDEX = "asset-embeddings"

# Prefix for the collections index — the full name is "{prefix}_collections_{env}"
# passed via INDEX_NAMES env var. We match by checking if the name contains "_collections_".
COLLECTIONS_INDEX_MARKER = "_collections_"


def index_exists(
    host: str, index_name: str, credentials, service: str, region: str
) -> bool:
    """
    HEAD /{index} – returns True if index already exists.
    """
    url = f"{host}/{index_name}"
    req = AWSRequest(method="HEAD", url=url, headers={})
    # required for SigV4
    req.headers["X-Amz-Content-SHA256"] = SigV4Auth(
        credentials, service, region
    ).payload(req)
    SigV4Auth(credentials, service, region).add_auth(req)
    prepared = req.prepare()

    logger.info(
        "Checking if index exists",
        extra={"method": prepared.method, "url": prepared.url},
    )
    resp = request(
        method=prepared.method,
        url=prepared.url,
        headers=prepared.headers,
        data=prepared.body,
    )
    return resp.status_code == 200


def delete_index(
    host: str, index_name: str, credentials, service: str, region: str
) -> None:
    """
    DELETE /{index}.  Ignores 404s.
    """
    url = f"{host}/{index_name}"
    req = AWSRequest(method="DELETE", url=url, headers={})
    req.headers["X-Amz-Content-SHA256"] = SigV4Auth(
        credentials, service, region
    ).payload(req)
    SigV4Auth(credentials, service, region).add_auth(req)
    prepared = req.prepare()

    resp = request(
        method=prepared.method,
        url=prepared.url,
        headers=prepared.headers,
        data=prepared.body,
    )
    if resp.status_code not in (200, 404):
        raise Exception(
            f"Unexpected status deleting index {index_name}: "
            f"{resp.status_code} – {resp.text}"
        )
    logger.info(
        "Index deleted (or did not exist)",
        extra={"index_name": index_name, "status_code": resp.status_code},
    )


def wait_for_deletion(
    host: str,
    index_name: str,
    credentials,
    service: str,
    region: str,
    timeout: int = 60,
    interval: int = 2,
) -> None:
    """
    Poll until HEAD /{index} returns 404, or timeout expires.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not index_exists(host, index_name, credentials, service, region):
            logger.info("Index confirmed gone", extra={"index_name": index_name})
            return
        time.sleep(interval)
    raise TimeoutError(f"Index {index_name} still exists after {timeout}s")


def create_index_with_retry(
    host, index_name, payload, headers, credentials, service, region, max_retries=5
):
    """
    Create an OpenSearch index with retry logic and exponential backoff.
    If the index already exists, delete it and wait for deletion before creating.
    """
    # If it already exists, drop & recreate
    if index_exists(host, index_name, credentials, service, region):
        logger.info(
            "Index exists – deleting before recreation",
            extra={"index_name": index_name},
        )
        delete_index(host, index_name, credentials, service, region)
        wait_for_deletion(host, index_name, credentials, service, region)

    url = f"{host}/{index_name}"
    logger.info(
        "Creating OpenSearch index", extra={"url": url, "index_name": index_name}
    )

    for attempt in range(max_retries):
        try:
            req = AWSRequest(
                method="PUT", url=url, data=json.dumps(payload), headers=headers
            )
            req.headers["X-Amz-Content-SHA256"] = SigV4Auth(
                credentials, service, region
            ).payload(req)
            SigV4Auth(credentials, service, region).add_auth(req)
            prepared = req.prepare()

            logger.info(
                "Sending request to OpenSearch",
                extra={
                    "method": prepared.method,
                    "url": prepared.url,
                    "attempt": attempt + 1,
                    "max_retries": max_retries,
                },
            )

            response = request(
                method=prepared.method,
                url=prepared.url,
                headers=prepared.headers,
                data=prepared.body,
            )

            if response.status_code == 200:
                logger.info(
                    "Index creation successful",
                    extra={
                        "index_name": index_name,
                        "status_code": response.status_code,
                        "response": response.text,
                    },
                )
                return True
            else:
                # If it somehow reappeared in the meantime
                error = (
                    response.json()
                    .get("error", {})
                    .get("root_cause", [{}])[0]
                    .get("type")
                )
                if error == "resource_already_exists_exception":
                    logger.info(
                        "Index already exists",
                        extra={
                            "index_name": index_name,
                            "status_code": response.status_code,
                        },
                    )
                    return True

                logger.error(
                    "Failed to create OpenSearch index",
                    extra={
                        "index_name": index_name,
                        "status_code": response.status_code,
                        "response": response.text,
                        "attempt": attempt + 1,
                        "max_retries": max_retries,
                    },
                )

        except Exception as e:
            logger.error(
                "Error creating OpenSearch index",
                extra={
                    "index_name": index_name,
                    "error": str(e),
                    "attempt": attempt + 1,
                    "max_retries": max_retries,
                },
                exc_info=True,
            )

        # Exponential backoff
        backoff_time = 2**attempt
        logger.info(
            "Retrying index creation after backoff",
            extra={
                "index_name": index_name,
                "attempt": attempt + 1,
                "max_retries": max_retries,
                "backoff_seconds": backoff_time,
            },
        )
        time.sleep(backoff_time)

    return False


def create_index_if_not_exists(
    host, index_name, payload, headers, credentials, service, region, max_retries=5
):
    """
    Create an OpenSearch index ONLY if it does not already exist.
    This is safe for Update events — it will never delete existing data.
    """
    if index_exists(host, index_name, credentials, service, region):
        logger.info(
            "Index already exists – skipping creation (safe mode)",
            extra={"index_name": index_name},
        )
        return True

    url = f"{host}/{index_name}"
    logger.info(
        "Creating new OpenSearch index (safe mode)",
        extra={"url": url, "index_name": index_name},
    )

    for attempt in range(max_retries):
        try:
            req = AWSRequest(
                method="PUT", url=url, data=json.dumps(payload), headers=headers
            )
            req.headers["X-Amz-Content-SHA256"] = SigV4Auth(
                credentials, service, region
            ).payload(req)
            SigV4Auth(credentials, service, region).add_auth(req)
            prepared = req.prepare()

            response = request(
                method=prepared.method,
                url=prepared.url,
                headers=prepared.headers,
                data=prepared.body,
            )

            if response.status_code == 200:
                logger.info(
                    "Index creation successful (safe mode)",
                    extra={
                        "index_name": index_name,
                        "status_code": response.status_code,
                    },
                )
                return True
            else:
                error = (
                    response.json()
                    .get("error", {})
                    .get("root_cause", [{}])[0]
                    .get("type")
                )
                if error == "resource_already_exists_exception":
                    logger.info(
                        "Index already exists (race condition – safe)",
                        extra={"index_name": index_name},
                    )
                    return True

                logger.error(
                    "Failed to create OpenSearch index (safe mode)",
                    extra={
                        "index_name": index_name,
                        "status_code": response.status_code,
                        "response": response.text,
                        "attempt": attempt + 1,
                        "max_retries": max_retries,
                    },
                )

        except Exception as e:
            logger.error(
                "Error creating OpenSearch index (safe mode)",
                extra={
                    "index_name": index_name,
                    "error": str(e),
                    "attempt": attempt + 1,
                    "max_retries": max_retries,
                },
                exc_info=True,
            )

        backoff_time = 2**attempt
        logger.info(
            "Retrying index creation after backoff (safe mode)",
            extra={
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
    Lambda handler for creating OpenSearch indexes

    Handles CloudFormation custom resource lifecycle events:
    - Create: Creates all indexes (deletes and recreates if they exist)
    - Update: Safely creates only the asset-embeddings index if it doesn't exist
              (never deletes existing indexes or data)
    - Delete: No-op (indexes are not deleted to preserve data)

    Args:
        event: Lambda event
        context: Lambda context

    Returns:
        dict: Response indicating success or failure
    """
    logger.info("Received event", extra={"event": event})

    req_type = event.get("RequestType")

    if req_type == "Delete":
        logger.info("Skipping Delete request – indexes are preserved")
        return {"statusCode": 200, "body": "Skipped Delete request"}

    host = os.environ["COLLECTION_ENDPOINT"]
    index_names = os.environ["INDEX_NAMES"]
    region = os.environ["REGION"]
    service = os.environ["SCOPE"]
    credentials = boto3.Session().get_credentials()

    logger.info(
        "Environment",
        extra={
            "host": host,
            "indexes": index_names,
            "region": region,
            "service": service,
        },
    )

    headers = {
        "content-type": "application/json",
        "accept": "application/json",
    }

    payload = {
        "settings": {
            "index": {
                "knn": True,
                "mapping.total_fields.limit": 6000,
            }
        },
        "mappings": {
            "properties": {
                # ═══════════════════════════════════════════════════════════
                # COMMON FIELDS (used by both master and separate embedding documents)
                # ═══════════════════════════════════════════════════════════
                "type": {"type": "text"},
                "document_id": {"type": "text"},
                "InventoryID": {"type": "text"},
                "FileHash": {"type": "text"},
                "StoragePath": {"type": "text"},
                "timestamp": {"type": "date"},
                # ═══════════════════════════════════════════════════════════
                # LEGACY FIELDS (backward compatibility)
                # ═══════════════════════════════════════════════════════════
                "embedding_scope": {
                    "type": "keyword"
                },  # LEGACY: Used for backward compatibility
                # ═══════════════════════════════════════════════════════════
                # SEPARATE EMBEDDING DOCUMENT FIELDS (per EmbeddingSegment schema)
                # Used for separate clip/asset embedding documents
                # ═══════════════════════════════════════════════════════════
                # Required fields per schema
                "inventory_id": {"type": "keyword"},
                "embedding_type": {"type": "keyword"},
                "model_provider": {"type": "keyword"},
                "inference_provider": {"type": "keyword"},
                "model_name": {"type": "keyword"},
                "model_version": {"type": "keyword"},
                "start_seconds": {"type": "integer"},
                "end_seconds": {"type": "integer"},
                "start_smpte_timecode": {"type": "keyword"},
                "end_smpte_timecode": {"type": "keyword"},
                "created_at": {"type": "date"},
                "embedding_granularity": {"type": "keyword"},
                "segmentation_method": {"type": "keyword"},
                "embedding_representation": {"type": "keyword"},
                "embedding_dimension": {"type": "integer"},
                "space_type": {"type": "keyword"},
                # LEGACY: Kept for backward compatibility
                "parent_asset_id": {
                    "type": "keyword"
                },  # LEGACY: Use inventory_id instead
                "start_timecode": {
                    "type": "keyword"
                },  # LEGACY: Use start_smpte_timecode instead
                "end_timecode": {
                    "type": "keyword"
                },  # LEGACY: Use end_smpte_timecode instead
                "end_timecode": {
                    "type": "keyword"
                },  # LEGACY: Use end_smpte_timecode instead
                # NOTE: "timestamp" field is already defined in COMMON FIELDS above (line 394).
                # LEGACY: Use created_at instead.
                # ═══════════════════════════════════════════════════════════
                # EMBEDDING VECTOR FIELDS (multiple dimensions supported)
                # ═══════════════════════════════════════════════════════════
                "embedding": {
                    "type": "knn_vector",
                    "dimension": 1024,
                    "method": {
                        "name": "hnsw",
                        "space_type": "cosinesimil",
                        "engine": "nmslib",
                    },
                },
                "embedding_256_cosine": {
                    "type": "knn_vector",
                    "dimension": 256,
                    "method": {
                        "name": "hnsw",
                        "space_type": "cosinesimil",
                        "engine": "nmslib",
                    },
                },
                "embedding_384_cosine": {
                    "type": "knn_vector",
                    "dimension": 384,
                    "method": {
                        "name": "hnsw",
                        "space_type": "cosinesimil",
                        "engine": "nmslib",
                    },
                },
                "embedding_512_cosine": {
                    "type": "knn_vector",
                    "dimension": 512,
                    "method": {
                        "name": "hnsw",
                        "space_type": "cosinesimil",
                        "engine": "nmslib",
                    },
                },
                "embedding_1024_cosine": {
                    "type": "knn_vector",
                    "dimension": 1024,
                    "method": {
                        "name": "hnsw",
                        "space_type": "cosinesimil",
                        "engine": "nmslib",
                    },
                },
                "embedding_1536_cosine": {
                    "type": "knn_vector",
                    "dimension": 1536,
                    "method": {
                        "name": "hnsw",
                        "space_type": "cosinesimil",
                        "engine": "nmslib",
                    },
                },
                "embedding_3072_cosine": {
                    "type": "knn_vector",
                    "dimension": 3072,
                    "method": {
                        "name": "hnsw",
                        "space_type": "cosinesimil",
                        "engine": "nmslib",
                    },
                },
                # ═══════════════════════════════════════════════════════════
                # MASTER DOCUMENT FIELDS (asset metadata)
                # ═══════════════════════════════════════════════════════════
                "DerivedRepresentations": {
                    "type": "nested",
                    "properties": {
                        "Format": {"type": "text"},
                        "ID": {"type": "text"},
                        "Purpose": {"type": "text"},
                        "Type": {"type": "text"},
                        "ImageSpec": {
                            "type": "object",
                            "properties": {
                                "Resolution": {
                                    "properties": {
                                        "Height": {"type": "integer"},
                                        "Width": {"type": "integer"},
                                    }
                                }
                            },
                        },
                        "StorageInfo": {
                            "type": "object",
                            "properties": {
                                "PrimaryLocation": {
                                    "properties": {
                                        "Bucket": {"type": "text"},
                                        "Status": {"type": "text"},
                                        "Provider": {"type": "text"},
                                        "StorageType": {"type": "text"},
                                        "FileInfo": {
                                            "properties": {"Size": {"type": "long"}}
                                        },
                                        "ObjectKey": {
                                            "properties": {
                                                "FullPath": {"type": "text"},
                                                "Name": {"type": "text"},
                                                "Path": {"type": "text"},
                                            }
                                        },
                                    }
                                }
                            },
                        },
                    },
                },
                "DigitalSourceAsset": {
                    "type": "object",
                    "properties": {
                        "CreateDate": {"type": "date"},
                        "ID": {"type": "keyword"},
                        "IngestedAt": {"type": "date"},
                        "lastModifiedDate": {"type": "date"},
                        "originalIngestDate": {"type": "date"},
                        "Type": {"type": "keyword"},
                        "MainRepresentation": {
                            "type": "object",
                            "properties": {
                                "Format": {"type": "keyword"},
                                "ID": {"type": "text"},
                                "Purpose": {"type": "text"},
                                "Type": {"type": "text"},
                                "StorageInfo": {
                                    "type": "object",
                                    "properties": {
                                        "PrimaryLocation": {
                                            "properties": {
                                                "Bucket": {"type": "text"},
                                                "Status": {"type": "text"},
                                                "StorageType": {"type": "text"},
                                                "FileInfo": {
                                                    "properties": {
                                                        "CreateDate": {"type": "date"},
                                                        "Size": {"type": "long"},
                                                        "Hash": {
                                                            "properties": {
                                                                "Algorithm": {
                                                                    "type": "keyword"
                                                                },
                                                                "MD5Hash": {
                                                                    "type": "keyword"
                                                                },
                                                                "Value": {
                                                                    "type": "keyword"
                                                                },
                                                            }
                                                        },
                                                    }
                                                },
                                                "ObjectKey": {
                                                    "properties": {
                                                        "FullPath": {"type": "text"},
                                                        "Name": {"type": "text"},
                                                        "Path": {"type": "text"},
                                                    }
                                                },
                                            }
                                        }
                                    },
                                },
                            },
                        },
                    },
                },
                "Metadata": {
                    "type": "object",
                    "dynamic": True,
                    "properties": {
                        "CustomMetadata": {"type": "object", "dynamic": True},
                        "EmbeddedMetadata": {"type": "object", "dynamic": True},
                    },
                },
                # ═══════════════════════════════════════════════════════════
                # DEPRECATED: AssetEmbeddings Nested Structure
                # ═══════════════════════════════════════════════════════════
                # This nested structure was deprecated in favor of separate documents.
                #
                # WHY NOT USE NESTED STRUCTURE:
                # 1. Document size limits: Large videos with many clips hit 4GB limit
                # 2. Version conflicts: Concurrent writes to same parent cause conflicts
                # 3. Performance: Large nested arrays slow down updates and queries
                # 4. Scalability: Cannot distribute writes across multiple documents
                #
                # CURRENT ARCHITECTURE:
                # - Embeddings stored as separate documents with inventory_id reference
                # - Each embedding document links to parent via inventory_id field
                # - Search queries group results by inventory_id to reconstruct parent-child relationships
                # - This approach scales to unlimited embeddings per asset
                #
                # "AssetEmbeddings": {
                #     "type": "nested",
                #     "properties": {
                #         "inventory_id": {"type": "keyword"},
                #         "embedding_type": {"type": "keyword"},
                #         "model_provider": {"type": "keyword"},
                #         "inference_provider": {"type": "keyword"},
                #         "model_name": {"type": "keyword"},
                #         "model_version": {"type": "keyword"},
                #         "start_seconds": {"type": "integer"},
                #         "end_seconds": {"type": "integer"},
                #         "start_smpte_timecode": {"type": "keyword"},
                #         "end_smpte_timecode": {"type": "keyword"},
                #         "created_at": {"type": "date"},
                #         "embedding_granularity": {"type": "keyword"},
                #         "segmentation_method": {"type": "keyword"},
                #         "embedding_representation": {"type": "keyword"},
                #         "embedding_dimension": {"type": "integer"},
                #         "space_type": {"type": "keyword"},
                #         "embedding": {
                #             "type": "knn_vector",
                #             "dimension": 1024,
                #             "method": {
                #                 "name": "hnsw",
                #                 "space_type": "cosinesimil",
                #                 "engine": "nmslib",
                #             },
                #         },
                #         "embedding_256_cosine": {
                #             "type": "knn_vector",
                #             "dimension": 256,
                #             "method": {
                #                 "name": "hnsw",
                #                 "space_type": "cosinesimil",
                #                 "engine": "nmslib",
                #             },
                #         },
                #         "embedding_384_cosine": {
                #             "type": "knn_vector",
                #             "dimension": 384,
                #             "method": {
                #                 "name": "hnsw",
                #                 "space_type": "cosinesimil",
                #                 "engine": "nmslib",
                #             },
                #         },
                #         "embedding_512_cosine": {
                #             "type": "knn_vector",
                #             "dimension": 512,
                #             "method": {
                #                 "name": "hnsw",
                #                 "space_type": "cosinesimil",
                #                 "engine": "nmslib",
                #             },
                #         },
                #         "embedding_1024_cosine": {
                #             "type": "knn_vector",
                #             "dimension": 1024,
                #             "method": {
                #                 "name": "hnsw",
                #                 "space_type": "cosinesimil",
                #                 "engine": "nmslib",
                #             },
                #         },
                #         "embedding_1536_cosine": {
                #             "type": "knn_vector",
                #             "dimension": 1536,
                #             "method": {
                #                 "name": "hnsw",
                #                 "space_type": "cosinesimil",
                #                 "engine": "nmslib",
                #             },
                #         },
                #         "embedding_3072_cosine": {
                #             "type": "knn_vector",
                #             "dimension": 3072,
                #             "method": {
                #                 "name": "hnsw",
                #                 "space_type": "cosinesimil",
                #                 "engine": "nmslib",
                #             },
                #         },
                #     },
                # },
            }
        },
    }

    # Mapping for "asset-embeddings" index - optimized for Marengo 3.0 vector embeddings
    # This index stores embeddings separately from asset metadata for better scalability
    asset_embeddings_payload = {
        "settings": {
            "index": {
                "knn": True,
                "mapping.total_fields.limit": 1000,
            }
        },
        "mappings": {
            "properties": {
                # Reference to parent asset in the "media" index
                "inventory_id": {"type": "keyword"},
                # Embedding granularity: "asset" (whole asset) or "segment" (clip/segment)
                "embedding_granularity": {"type": "keyword"},
                # How the segment was created (e.g., "scene_detection", "fixed_interval")
                "segmentation_method": {"type": "keyword"},
                # Modality of the embedding: "visual", "audio", "text", "video"
                "embedding_representation": {"type": "keyword"},
                # Dimension of the embedding vector (e.g., 1024, 3072)
                "embedding_dimension": {"type": "integer"},
                # Type of embedding (e.g., "marengo_3.0", "clip")
                "embedding_type": {"type": "keyword"},
                # Model version that generated the embedding
                "model_version": {"type": "keyword"},
                # Model provider (e.g., "twelve_labs")
                "model_provider": {"type": "keyword"},
                # Inference provider (e.g., "bedrock", "api")
                "inference_provider": {"type": "keyword"},
                # Model name (e.g., "Marengo-retrieval-2.7")
                "model_name": {"type": "keyword"},
                # When the embedding was created
                "created_at": {"type": "date"},
                # Start time of segment in seconds (for segment embeddings)
                "start_seconds": {"type": "float"},
                # End time of segment in seconds (for segment embeddings)
                "end_seconds": {"type": "float"},
                # Start SMPTE timecode (for segment embeddings)
                "start_smpte_timecode": {"type": "keyword"},
                # End SMPTE timecode (for segment embeddings)
                "end_smpte_timecode": {"type": "keyword"},
                # Space type for the vector (e.g., "cosine", "l2")
                "space_type": {"type": "keyword"},
                # KNN vector fields for different dimensions
                "embedding": {
                    "type": "knn_vector",
                    "dimension": 1024,
                    "method": {
                        "name": "hnsw",
                        "space_type": "cosinesimil",
                        "engine": "nmslib",
                    },
                },
                "embedding_256_cosine": {
                    "type": "knn_vector",
                    "dimension": 256,
                    "method": {
                        "name": "hnsw",
                        "space_type": "cosinesimil",
                        "engine": "nmslib",
                    },
                },
                "embedding_384_cosine": {
                    "type": "knn_vector",
                    "dimension": 384,
                    "method": {
                        "name": "hnsw",
                        "space_type": "cosinesimil",
                        "engine": "nmslib",
                    },
                },
                "embedding_512_cosine": {
                    "type": "knn_vector",
                    "dimension": 512,
                    "method": {
                        "name": "hnsw",
                        "space_type": "cosinesimil",
                        "engine": "nmslib",
                    },
                },
                "embedding_1024_cosine": {
                    "type": "knn_vector",
                    "dimension": 1024,
                    "method": {
                        "name": "hnsw",
                        "space_type": "cosinesimil",
                        "engine": "nmslib",
                    },
                },
                "embedding_1536_cosine": {
                    "type": "knn_vector",
                    "dimension": 1536,
                    "method": {
                        "name": "hnsw",
                        "space_type": "cosinesimil",
                        "engine": "nmslib",
                    },
                },
                "embedding_3072_cosine": {
                    "type": "knn_vector",
                    "dimension": 3072,
                    "method": {
                        "name": "hnsw",
                        "space_type": "cosinesimil",
                        "engine": "nmslib",
                    },
                },
            }
        },
    }

    # Mapping for the collections index — stores collection metadata for listing/search.
    # Uses keyword types for all ID/filter fields to support term queries.
    #
    # WARNING: This mapping is an inline copy. The canonical version is maintained in
    # lambdas/sync/collections_sync/collections_index_mapping.json (also used by
    # collections_backfill). If you change the mapping here, update the JSON file too
    # and vice versa. A future refactor should load from a single shared source.
    collections_payload = {
        "settings": {
            "number_of_shards": 1,
            "number_of_replicas": 1,
            "index.max_result_window": 100000,
        },
        "mappings": {
            "properties": {
                "id": {"type": "keyword"},
                "name": {
                    "type": "text",
                    "fields": {"keyword": {"type": "keyword"}},
                },
                "description": {"type": "text"},
                "ownerId": {"type": "keyword"},
                "status": {"type": "keyword"},
                "isPublic": {"type": "boolean"},
                "collectionTypeId": {"type": "keyword"},
                "parentId": {"type": "keyword"},
                "tags": {"type": "keyword"},
                "childCollectionCount": {"type": "integer"},
                "itemCount": {"type": "integer"},
                "collectionIds": {"type": "keyword"},
                "sharedWithUserIds": {"type": "keyword"},
                "createdAt": {"type": "date"},
                "updatedAt": {"type": "date"},
                "thumbnailType": {"type": "keyword"},
                "thumbnailValue": {"type": "keyword"},
                "thumbnailS3Key": {"type": "keyword"},
                "customMetadata": {"type": "object", "dynamic": True},
                "expiresAt": {"type": "date"},
                "documentType": {"type": "keyword"},
            }
        },
    }

    logger.info(
        "Preparing to create indexes",
        extra={
            "region": region,
            "service": service,
            "vector_dimension": VECTOR_DIMENSION,
        },
    )

    indexes = index_names.split(",")
    logger.info(f"Creating {len(indexes)} indexes", extra={"indexes": indexes})

    if req_type == "Update":
        # On Update: safely create asset-embeddings and collections indexes
        # if they don't exist. Never delete or recreate existing indexes.
        logger.info(
            "Update request – safely creating new indexes only",
        )

        for index_name in indexes:
            index_name = index_name.strip()

            if index_name == ASSET_EMBEDDINGS_INDEX:
                logger.info(
                    "Safely creating asset-embeddings index if not exists",
                    extra={"index_name": index_name},
                )
                success = create_index_if_not_exists(
                    host,
                    index_name,
                    asset_embeddings_payload,
                    headers,
                    credentials,
                    service,
                    region,
                )
                if not success:
                    msg = f"Failed to create index {index_name} after multiple retries"
                    logger.error(msg)
                    raise Exception(msg)
            elif COLLECTIONS_INDEX_MARKER in index_name:
                logger.info(
                    "Safely creating collections index if not exists",
                    extra={"index_name": index_name},
                )
                success = create_index_if_not_exists(
                    host,
                    index_name,
                    collections_payload,
                    headers,
                    credentials,
                    service,
                    region,
                )
                if not success:
                    msg = f"Failed to create index {index_name} after multiple retries"
                    logger.error(msg)
                    raise Exception(msg)
            else:
                logger.info(
                    "Skipping existing index on Update (no changes)",
                    extra={"index_name": index_name},
                )

        logger.info("Update completed – all new indexes ensured")
        return {"statusCode": 200, "body": "Update completed successfully"}

    # Create: create indexes safely — only recreate if FORCE_RECREATE is set.
    # Default behavior uses create_index_if_not_exists to prevent accidental
    # data loss when CloudFormation replaces the custom resource (new logical ID).
    force_recreate = event.get("ResourceProperties", {}).get("ForceRecreate", "false")
    use_destructive_create = force_recreate.lower() == "true"

    if use_destructive_create:
        logger.warning(
            "FORCE_RECREATE is set — indexes will be deleted and recreated",
        )

    for index_name in indexes:
        index_name = index_name.strip()
        logger.info("Processing index", extra={"index_name": index_name})

        # Use index-specific mapping
        if index_name == ASSET_EMBEDDINGS_INDEX:
            index_payload = asset_embeddings_payload
            logger.info(
                "Using asset-embeddings specific mapping",
                extra={"index_name": index_name},
            )
        elif COLLECTIONS_INDEX_MARKER in index_name:
            index_payload = collections_payload
            logger.info(
                "Using collections specific mapping",
                extra={"index_name": index_name},
            )
        else:
            index_payload = payload
            logger.info(
                "Using default media index mapping", extra={"index_name": index_name}
            )

        if use_destructive_create:
            success = create_index_with_retry(
                host, index_name, index_payload, headers, credentials, service, region
            )
        else:
            success = create_index_if_not_exists(
                host, index_name, index_payload, headers, credentials, service, region
            )
        if not success:
            msg = f"Failed to create index {index_name} after multiple retries"
            logger.error(msg)
            raise Exception(msg)

    logger.info("Successfully created all indexes")
    return {"statusCode": 200, "body": "All indexes created successfully"}
