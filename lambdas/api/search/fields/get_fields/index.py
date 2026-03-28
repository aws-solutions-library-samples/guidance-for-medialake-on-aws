import json
import os

import boto3
from aws_lambda_powertools import Logger, Metrics
from aws_lambda_powertools.event_handler import APIGatewayRestResolver
from aws_lambda_powertools.event_handler.api_gateway import CORSConfig
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.utilities.typing import LambdaContext
from opensearchpy import OpenSearch, RequestsAWSV4SignerAuth, RequestsHttpConnection

logger = Logger()
metrics = Metrics()

cors_config = CORSConfig(
    allow_origin="*",
    allow_headers=[
        "Content-Type",
        "X-Amz-Date",
        "Authorization",
        "X-Api-Key",
        "X-Amz-Security-Token",
    ],
)

app = APIGatewayRestResolver(
    serializer=lambda x: json.dumps(x, default=str),
    strip_prefixes=["/api"],
    cors=cors_config,
)

dynamodb = boto3.resource("dynamodb")

_opensearch_client = None


def get_opensearch_client() -> OpenSearch:
    """Create and return a cached OpenSearch client with IAM SigV4 auth."""
    global _opensearch_client

    if _opensearch_client is None:
        host = os.environ["OPENSEARCH_ENDPOINT"].replace("https://", "")
        region = os.environ["AWS_REGION"]
        service_scope = os.environ["SCOPE"]

        auth = RequestsAWSV4SignerAuth(
            boto3.Session().get_credentials(), region, service_scope
        )

        _opensearch_client = OpenSearch(
            hosts=[{"host": host, "port": 443}],
            http_auth=auth,
            use_ssl=True,
            verify_certs=True,
            connection_class=RequestsHttpConnection,
            region=region,
            timeout=30,
            max_retries=2,
            retry_on_timeout=True,
        )

    return _opensearch_client


DISPLAY_TYPE_MAP = {
    "text": "string",
    "keyword": "string",
    "long": "number",
    "integer": "number",
    "float": "number",
    "double": "number",
    "short": "number",
    "byte": "number",
    "half_float": "number",
    "scaled_float": "number",
    "date": "date",
    "boolean": "boolean",
}

DEFAULT_FIELDS = [
    {
        "name": "DigitalSourceAsset.Type",
        "displayName": "Asset Type",
        "type": "string",
        "isDefault": True,
    },
    {
        "name": "DigitalSourceAsset.MainRepresentation.Format",
        "displayName": "File Format",
        "type": "string",
        "isDefault": True,
    },
    {
        "name": "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.FileSize",
        "displayName": "File Size",
        "type": "number",
        "isDefault": True,
    },
    {
        "name": "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.CreateDate",
        "displayName": "Created date",
        "type": "date",
        "isDefault": True,
    },
    {
        "name": "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.ObjectKey.Name",
        "displayName": "File name",
        "type": "string",
        "isDefault": True,
    },
]


def traverse_mapping(properties: dict, prefix: str = "") -> list:
    """Recursively traverse OpenSearch mapping to extract leaf fields."""
    fields = []
    for field_name, field_def in properties.items():
        full_path = f"{prefix}.{field_name}" if prefix else field_name

        if "properties" in field_def or field_def.get("type") == "nested":
            fields.extend(traverse_mapping(field_def.get("properties", {}), full_path))
            continue

        raw_type = field_def.get("type", "object")
        if raw_type == "object":
            continue

        display_type = DISPLAY_TYPE_MAP.get(raw_type, "string")
        keyword_name = None
        if raw_type == "text" and "keyword" in field_def.get("fields", {}):
            keyword_name = f"{full_path}.keyword"

        fields.append(
            {
                "name": full_path,
                "type": raw_type,
                "displayType": display_type,
                "keywordName": keyword_name,
            }
        )

    return fields


@app.get("/search/fields/mapping")
def handle_get_fields_mapping():
    """Return all leaf fields under the Metadata namespace from the OpenSearch index mapping."""
    try:
        client = get_opensearch_client()
        index_name = os.environ["OPENSEARCH_INDEX"]
        response = client.indices.get_mapping(index=index_name)
        mapping = response.get(index_name) or next(iter(response.values()))
        properties = mapping["mappings"]["properties"]

        # Only traverse the Metadata subtree — other top-level fields
        # (DigitalSourceAsset, InventoryID, etc.) are handled by the defaults.
        metadata_props = properties.get("Metadata", {}).get("properties", {})
        fields = traverse_mapping(metadata_props, prefix="Metadata")

        return {"status": "200", "message": "ok", "data": {"fields": fields}}
    except Exception as e:
        logger.error(f"Error retrieving fields mapping: {str(e)}")
        return {
            "status": "500",
            "message": f"Error retrieving fields mapping: {str(e)}",
            "data": None,
        }


@app.get("/search/fields")
def handle_get_fields():
    """Return default fields and user-configured displayable fields from DynamoDB."""
    try:
        table_name = os.environ["SYSTEM_SETTINGS_TABLE"]
        table = dynamodb.Table(table_name)
        response = table.get_item(
            Key={"PK": "SYSTEM_SETTINGS", "SK": "METADATA_FIELDS"},
            ConsistentRead=True,
        )
        item = response.get("Item")
        available_fields = []
        if item:
            available_fields = [
                f for f in item.get("fields", []) if f.get("isDisplayable") is True
            ]
        default_as_available = [
            {**f, "isDisplayable": True, "isFilterable": True} for f in DEFAULT_FIELDS
        ]
        return {
            "status": "200",
            "message": "ok",
            "data": {
                "defaultFields": DEFAULT_FIELDS,
                "availableFields": default_as_available + available_fields,
            },
        }
    except Exception as e:
        logger.error(f"Error retrieving search fields: {str(e)}")
        return {
            "status": "500",
            "message": f"Error retrieving search fields: {str(e)}",
            "data": None,
        }


@metrics.log_metrics
@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_HTTP)
def lambda_handler(event: dict, context: LambdaContext) -> dict:
    """Lambda handler function"""
    return app.resolve(event, context)
