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
    url = f"{host}/{index_name}"
    print(f"URL: {url}")

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

            response = request(
                method=req.method, url=req.url, headers=req.headers, data=req.body
            )

            if response.status_code == 200:
                print(f"Index create SUCCESS - status: {response.text}")
                return True
            else:
                if (
                    response.json()["error"]["root_cause"][0]["type"]
                    == "resource_already_exists_exception"
                ):
                    return True
                # print(response.json()["error"])
                print(
                    f"Failed to create OS index - status: {response.status_code} {response.text}"
                )

        except Exception as e:
            print(
                f"Error creating OS index (attempt {attempt + 1}/{max_retries}): {str(e)}"
            )

        # Exponential backoff
        time.sleep(2**attempt)

    return False


def handler(event, context):
    print(event)

    if event["RequestType"] == "Create":
        host = os.environ["COLLECTION_ENDPOINT"]
        print(f"Collection Endpoint: {host}")

        index_names = os.environ["INDEX_NAMES"]
        print(f"Index names: {index_names}")

        headers = {
            "content-type": "application/json",
            "accept": "application/json",
        }

        payload = {
                "settings": {
                    "index": {
                        "knn": True,
                        "number_of_shards": 2,
                        "knn.algo_param.ef_search": 100
                    }
                },
                "mappings": {
                    "properties": {
                        "type": {
                            "type": "keyword"
                        },
                        "document_id": {
                            "type": "keyword"
                        },
                        "asset_id": {
                            "type": "keyword"
                        },
                        "start_offset_sec": {
                            "type": "float"
                        },
                        "end_offset_sec": {
                            "type": "float"
                        },
                        "embedding_scope": {
                            "type": "keyword"
                        },
                        "embedding": {
                            "type": "knn_vector",
                            "dimension": VECTOR_DIMENSION,
                            "method": {
                                "name": "hnsw",
                                "space_type": "cosinesimil",
                                "engine": "nmslib",
                                "parameters": {
                                    "ef_construction": 128,
                                    "m": 16
                                }
                            }
                        }
                    }
                }
            }

        region = os.environ["REGION"]
        service = os.environ["SCOPE"]
        credentials = boto3.Session().get_credentials()

        indexes = index_names.split(",")
        for index_name in indexes:
            success = create_index_with_retry(
                host, index_name, payload, headers, credentials, service, region
            )
            if not success:
                raise Exception(
                    f"Failed to create index {index_name} after multiple retries"
                )
