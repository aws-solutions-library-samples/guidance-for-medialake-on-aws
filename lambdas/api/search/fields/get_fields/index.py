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


def resolve_agg_field(field_path: str, all_properties: dict) -> str:
    """Walk the mapping to find the correct aggregatable field name.

    Keyword fields are already aggregatable; text fields need .keyword suffix.
    Numeric and date fields are aggregatable as-is.
    """
    parts = field_path.split(".")
    current = all_properties
    for part in parts:
        if current is None:
            break
        field_def = current.get(part, {})
        if "properties" in field_def:
            current = field_def["properties"]
        else:
            raw_type = field_def.get("type", "object")
            if raw_type == "keyword":
                return field_path
            if raw_type == "text" and "keyword" in field_def.get("fields", {}):
                return f"{field_path}.keyword"
            # Numeric and date types are aggregatable directly
            if raw_type in (
                "long",
                "integer",
                "float",
                "double",
                "short",
                "byte",
                "half_float",
                "scaled_float",
                "unsigned_long",
                "date",
            ):
                return field_path
            # Default to .keyword for text-like fields
            return f"{field_path}.keyword"
    # Field not found in mapping - assume keyword suffix needed
    return f"{field_path}.keyword"


def populate_predefined_values(fields: list) -> list:
    """For fields with autoPopulateValues=True and type=string, query OpenSearch
    for distinct values and attach them as predefinedValues."""
    fields_to_populate = [
        f for f in fields if f.get("autoPopulateValues") and f.get("type") == "string"
    ]
    if not fields_to_populate:
        return fields

    try:
        client = get_opensearch_client()
        index_name = os.environ["OPENSEARCH_INDEX"]

        mapping_response = client.indices.get_mapping(index=index_name)
        mapping = mapping_response.get(index_name) or next(
            iter(mapping_response.values())
        )
        all_properties = mapping["mappings"]["properties"]

        aggs = {}
        for f in fields_to_populate:
            name = f["name"]
            agg_field = resolve_agg_field(name, all_properties)
            aggs[name] = {"terms": {"field": agg_field, "size": 500}}

        response = client.search(
            index=index_name,
            body={"size": 0, "aggs": aggs},
        )

        values_map = {}
        for f in fields_to_populate:
            name = f["name"]
            buckets = response.get("aggregations", {}).get(name, {}).get("buckets", [])
            values_map[name] = [b["key"] for b in buckets]

        for f in fields:
            if f["name"] in values_map:
                f["predefinedValues"] = values_map[f["name"]]
    except Exception as e:
        logger.warning(f"Failed to populate predefined values: {str(e)}")

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

        # Populate predefined values for fields with autoPopulateValues enabled
        available_fields = populate_predefined_values(available_fields)

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


@app.post("/search/fields/values")
def handle_post_fields_values():
    """Return distinct values for the requested string fields from OpenSearch.

    Expects JSON body: { "fields": ["Metadata.SomeField", ...] }
    For each field, runs a terms aggregation (size 500) and returns the unique values.
    """
    try:
        body = app.current_event.json_body or {}
    except Exception:
        return {
            "status": "400",
            "message": "Request body must be valid JSON with a 'fields' array",
            "data": None,
        }

    field_names = body.get("fields", [])
    if not isinstance(field_names, list) or not field_names:
        return {
            "status": "400",
            "message": "'fields' must be a non-empty array of field name strings",
            "data": None,
        }

    # Cap at 20 fields per request to avoid oversized aggregations
    field_names = field_names[:20]

    try:
        client = get_opensearch_client()
        index_name = os.environ["OPENSEARCH_INDEX"]

        # Fetch the index mapping to determine the correct aggregation field
        mapping_response = client.indices.get_mapping(index=index_name)
        mapping = mapping_response.get(index_name) or next(
            iter(mapping_response.values())
        )
        all_properties = mapping["mappings"]["properties"]

        aggs = {}
        for name in field_names:
            agg_field = resolve_agg_field(name, all_properties)
            aggs[name] = {"terms": {"field": agg_field, "size": 500}}

        response = client.search(
            index=index_name,
            body={"size": 0, "aggs": aggs},
        )

        result = {}
        for name in field_names:
            buckets = response.get("aggregations", {}).get(name, {}).get("buckets", [])
            result[name] = [
                {"key": b["key"], "doc_count": b.get("doc_count", 0)} for b in buckets
            ]

        return {"status": "200", "message": "ok", "data": result}
    except Exception as e:
        logger.error(f"Error fetching field values: {str(e)}")
        return {
            "status": "500",
            "message": f"Error fetching field values: {str(e)}",
            "data": None,
        }


@metrics.log_metrics
@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_HTTP)
def lambda_handler(event: dict, context: LambdaContext) -> dict:
    """Lambda handler function"""
    return app.resolve(event, context)
