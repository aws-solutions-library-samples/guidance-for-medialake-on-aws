import logging
import os

import boto3
from opensearchpy import OpenSearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth

LOGGER = logging.getLogger(__name__)


class OpenSearchClient:
    def __init__(self):
        self.collection_endpoint = os.environ.get("OPENSEARCH_COLLECTION_ENDPOINT")
        self.region_name = os.environ.get("AWS_REGION")
        self.service = "es"
        self.client = self._create_client()

    @staticmethod
    def _configure_logger():
        """Configure python logger for lambda function"""
        default_log_args = {
            "level": (
                logging.DEBUG if os.environ.get("VERBOSE", False) else logging.INFO
            ),
            "format": "%(asctime)s [%(levelname)s] %(name)s - %(message)s",
            "datefmt": "%d-%b-%y %H:%M",
            "force": True,
        }
        logging.basicConfig(**default_log_args)

    def _create_client(self):
        credentials = boto3.Session().get_credentials()
        awsauth = AWS4Auth(
            credentials.access_key,
            credentials.secret_key,
            self.region_name,
            self.service,
            session_token=credentials.token,
        )
        host = self.collection_endpoint.replace("https://", "")

        return OpenSearch(
            hosts=[{"host": host, "port": 443}],
            http_auth=awsauth,
            use_ssl=True,
            verify_certs=True,
            connection_class=RequestsHttpConnection,
        )

    def query(self, index, query):
        try:
            response = self.client.search(index=index, body=query)
            return response
        except Exception as e:
            LOGGER.error(f"Error executing query: {e}")
            raise e
