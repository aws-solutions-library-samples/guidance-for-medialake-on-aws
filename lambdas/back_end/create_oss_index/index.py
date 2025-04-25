import boto3
from botocore.exceptions import ClientError
from requests import request
import json
import os
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
import time

VECTOR_DIMENSION = 1024  # Twelve Labs embeddings dimension

def create_index_with_retry(
    host, index_name, payload, headers, credentials, service, region, max_retries=5
):
    """
    Create an OpenSearch index with retry logic and exponential backoff
    
    Args:
        host: OpenSearch host endpoint
        index_name: Name of the index to create
        payload: Index configuration payload
        headers: HTTP headers for the request
        credentials: AWS credentials for SigV4 signing
        service: AWS service name for SigV4 signing
        region: AWS region for SigV4 signing
        max_retries: Maximum number of retry attempts
        
    Returns:
        bool: True if index creation was successful, False otherwise
    """
    url = f"{host}/{index_name}"
    print(f"Creating OpenSearch index - url: {url}, index_name: {index_name}")

    for attempt in range(max_retries):
        try:
            req = AWSRequest(
                method="PUT", url=url, data=json.dumps(payload), headers=headers
            )
            req.headers["X-Amz-Content-SHA256"] = SigV4Auth(
                credentials, service, region
            ).payload(req)
            SigV4Auth(credentials, service, region).add_auth(req)
            req = req.prepare()

            print(f"Sending request to OpenSearch - method: {req.method}, url: {req.url}, attempt: {attempt + 1}, max_retries: {max_retries}")
            
            response = request(
                method=req.method, url=req.url, headers=req.headers, data=req.body
            )

            if response.status_code == 200:
                print(f"Index creation successful - index_name: {index_name}, status_code: {response.status_code}, response: {response.text}")
                return True
            else:
                if (
                    response.json()["error"]["root_cause"][0]["type"]
                    == "resource_already_exists_exception"
                ):
                    print(f"Index already exists - index_name: {index_name}, status_code: {response.status_code}")
                    return True
                
                print(f"Failed to create OpenSearch index - index_name: {index_name}, status_code: {response.status_code}, response: {response.text}, attempt: {attempt + 1}, max_retries: {max_retries}")

        except Exception as e:
            print(f"Error creating OpenSearch index - index_name: {index_name}, error: {str(e)}, attempt: {attempt + 1}, max_retries: {max_retries}")

        # Exponential backoff
        backoff_time = 2**attempt
        print(f"Retrying index creation after backoff - index_name: {index_name}, attempt: {attempt + 1}, max_retries: {max_retries}, backoff_seconds: {backoff_time}")
        time.sleep(backoff_time)

    return False


def handler(event, context):
    """
    Lambda handler for creating OpenSearch indexes
    
    Args:
        event: Lambda event
        context: Lambda context
        
    Returns:
        dict: Response indicating success or failure
    """
    print(f"Received event: {event}")

    if event["RequestType"] == "Create":
        host = os.environ["COLLECTION_ENDPOINT"]
        print(f"Retrieved collection endpoint - host: {host}")

        index_names = os.environ["INDEX_NAMES"]
        print(f"Retrieved index names - index_names: {index_names}")

        headers = {
            "content-type": "application/json",
            "accept": "application/json",
        }

        # payload = {
        #         "settings": {
        #             "index": {
        #                 "knn": True,
        #                 "mapping.total_fields.limit": 3000
        #             }
        #         },
        #         "mappings": {
        #             "properties": {
        #                 "type": {
        #                     "type": "keyword"
        #                 },
        #                 "document_id": {
        #                     "type": "keyword"
        #                 },
        #                 "asset_id": {
        #                     "type": "keyword"
        #                 },
        #                 "start_timecode": {
        #                     "type": "keyword"
        #                 },
        #                 "end_timecode": {
        #                     "type": "keyword"
        #                 },
        #                 "embedding_scope": {
        #                     "type": "keyword"
        #                 },
        #                 "embedding": {
        #                     "type": "knn_vector",
        #                     "dimension": VECTOR_DIMENSION,
        #                     "method": {
        #                         "name": "hnsw",
        #                         "space_type": "cosinesimil",
        #                         "engine": "nmslib",
        #                     }
        #                 }
        #             }
        #         }
        #     }

        payload = {
            "settings": {
                "index": {
                "knn": True,
                "mapping.total_fields.limit": 6000
                }
            },
            "mappings": {
                "properties": {
                    "type":        {"type":"keyword"},
                    "document_id": {"type":"keyword"},
                    "asset_id":    {"type":"keyword"},
                    "start_timecode": {"type":"keyword"},
                    "end_timecode":   {"type":"keyword"},
                    "embedding_scope":{"type":"keyword"},
                    "embedding": {
                    "type": "knn_vector",
                    "dimension": VECTOR_DIMENSION,
                    "method": {
                        "name": "hnsw",
                        "space_type": "cosinesimil",
                        "engine": "nmslib"
                    }
                    },
                    "EmbeddedMetadata": {
                        "type": "object",
                        "dynamic": True
                    }
                }
            }
        }

        region = os.environ["REGION"]
        service = os.environ["SCOPE"]
        credentials = boto3.Session().get_credentials()

        print(f"Preparing to create indexes - region: {region}, service: {service}, vector_dimension: {VECTOR_DIMENSION}")

        indexes = index_names.split(",")
        print(f"Creating {len(indexes)} indexes - indexes: {indexes}")
        
        for index_name in indexes:
            print(f"Processing index - index_name: {index_name}")
            success = create_index_with_retry(
                host, index_name, payload, headers, credentials, service, region
            )
            if not success:
                error_msg = f"Failed to create index {index_name} after multiple retries"
                print(f"ERROR: {error_msg}")
                raise Exception(error_msg)
            
        print("Successfully created all indexes")
        return {"statusCode": 200, "body": "All indexes created successfully"}
    else:
        print(f"Skipping non-Create request type - RequestType: {event['RequestType']}")
        return {"statusCode": 200, "body": f"Skipped {event['RequestType']} request"}
