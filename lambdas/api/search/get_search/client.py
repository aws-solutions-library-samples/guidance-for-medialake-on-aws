import logging
import os

from opensearchpy import OpenSearch, RequestsHttpConnection

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
        from opensearchpy import RequestsAWSV4SignerAuth
        from refreshable_auth import get_refreshable_credentials

        credentials = get_refreshable_credentials()
        awsauth = RequestsAWSV4SignerAuth(credentials, self.region_name, self.service)
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
