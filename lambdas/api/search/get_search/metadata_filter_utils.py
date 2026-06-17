"""
Shared utilities for custom metadata filtering across all search providers.

Provides:
- Filter normalization (frontend schema → unified schema)
- OpenSearch filter DSL generation (.keyword suffix, terms grouping)
- Batched parent-doc enrichment with filters applied at query time

All semantic providers (Bedrock/TwelveLabs, Coactive, future) use these
utilities so filter behavior is consistent regardless of search path.
"""

from typing import Any, Dict, List, Optional, Tuple

from opensearchpy import OpenSearch

# Required source fields for every search result — the minimum needed to
# render an asset card in the UI.
REQUIRED_SOURCE_FIELDS: List[str] = [
    "InventoryID",
    "DigitalSourceAsset.Type",
    "DigitalSourceAsset.MainRepresentation.Format",
    "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.ObjectKey",
    "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.FileInfo.Size",
    "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.FileInfo.CreateDate",
    "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.FileSize",
    "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.CreateDate",
    "DigitalSourceAsset.CreateDate",
    "DerivedRepresentations.Purpose",
    "DerivedRepresentations.StorageInfo.PrimaryLocation",
    "Metadata.Consolidated.type",
]


def normalize_filters(raw_filters: List[Dict]) -> List[Dict]:
    """Normalize frontend filter format to the unified provider format.

    The frontend sends custom metadata filters as:
        {"field": "Metadata.X", "operator": "term", "value": "Y"}

    Providers expect the unified format:
        {"key": "Metadata.X", "operator": "term", "value": "Y"}

    This function ensures both schemas work everywhere by normalizing
    ``field`` → ``key`` when ``key`` is absent.  It also groups multiple
    ``term`` filters on the same field into a single ``in`` filter so
    providers can emit a single ``terms`` query (OR semantics).
    """
    if not raw_filters:
        return []

    # Step 1: normalize field → key
    normalized = []
    for f in raw_filters:
        entry = dict(f)
        if "key" not in entry and "field" in entry:
            entry["key"] = entry.pop("field")
        normalized.append(entry)

    # Step 2: group term filters by key → in (OR)
    term_groups: Dict[str, List[str]] = {}
    others: List[Dict] = []

    for entry in normalized:
        if entry.get("operator") == "term" and isinstance(entry.get("value"), str):
            key = entry["key"]
            term_groups.setdefault(key, []).append(entry["value"])
        else:
            others.append(entry)

    for key, values in term_groups.items():
        if len(values) == 1:
            others.append({"key": key, "operator": "term", "value": values[0]})
        else:
            others.append({"key": key, "operator": "in", "value": values})

    return others


def build_opensearch_filters(filters: List[Dict]) -> List[Dict]:
    """Convert unified filters to OpenSearch query DSL clauses.

    Handles:
    - ``term`` / ``in`` → ``term`` / ``terms`` with ``.keyword`` suffix for
      Metadata text fields
    - ``match`` → ``match`` (analyzed, no .keyword)
    - ``range`` → ``range``
    - ``==`` / ``eq`` → ``term``

    Returns a list of OpenSearch filter clauses ready to be appended to
    ``bool.filter``.
    """
    os_filters: List[Dict] = []

    for f in filters:
        key = f.get("key", "")
        op = f.get("operator", "")
        value = f.get("value")

        # Resolve the correct field name for term/in queries on Metadata fields
        term_field = _resolve_term_field(key)
        # Map abstract keys to real OpenSearch paths for all operators
        mapped_key = _map_field_path(key)

        if op == "term":
            os_filters.append({"term": {term_field: value}})

        elif op == "in":
            if isinstance(value, list):
                os_filters.append({"terms": {term_field: value}})
            else:
                os_filters.append({"term": {term_field: value}})

        elif op in ("==", "eq"):
            os_filters.append({"term": {term_field: value}})

        elif op == "match":
            # match uses the analyzed field (no .keyword)
            os_filters.append({"match": {mapped_key: value}})

        elif op == "range":
            if isinstance(value, dict):
                range_clause: Dict[str, Any] = {}
                for bound in ("gte", "lte", "gt", "lt"):
                    if bound in value:
                        range_clause[bound] = value[bound]
                if range_clause:
                    os_filters.append({"range": {mapped_key: range_clause}})
            else:
                # Flat gte/lte on the filter dict itself (frontend format)
                range_clause = {}
                if f.get("gte") is not None:
                    range_clause["gte"] = f["gte"]
                if f.get("lte") is not None:
                    range_clause["lte"] = f["lte"]
                if range_clause:
                    os_filters.append({"range": {mapped_key: range_clause}})

    return os_filters


def _resolve_term_field(field_path: str) -> str:
    """Append .keyword for Metadata text fields so term queries match
    the unanalyzed value.  Non-Metadata fields and fields already ending
    in .keyword are returned as-is."""
    mapped = _map_field_path(field_path)
    if mapped.startswith("Metadata.") and not mapped.endswith(".keyword"):
        return f"{mapped}.keyword"
    return mapped


# Mapping from abstract/shorthand filter keys to actual OpenSearch field paths.
_FIELD_PATH_MAP = {
    "mediaType": "DigitalSourceAsset.Type",
    "format": "DigitalSourceAsset.MainRepresentation.Format",
    "extension": "DigitalSourceAsset.MainRepresentation.Format",
    "fileSize": "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.FileInfo.Size",
    "asset_size": "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.FileInfo.Size",
    "createdAt": "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.FileInfo.CreateDate",
    "ingested_date": "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.FileInfo.CreateDate",
    "bucket": "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.Bucket",
    "objectName": "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.ObjectKey.Name",
    "fileName": "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.ObjectKey.Name",
}


def _map_field_path(key: str) -> str:
    """Map abstract/shorthand filter key to the actual OpenSearch field path.
    Returns the key unchanged if no mapping exists."""
    return _FIELD_PATH_MAP.get(key, key)


def compute_source_fields(ui_fields: Optional[List[str]] = None) -> List[str]:
    """Merge the required base fields with any UI-requested fields.

    Returns a deduplicated list suitable for ``_source.includes``.
    """
    base = set(REQUIRED_SOURCE_FIELDS)
    if ui_fields:
        base.update(ui_fields)
    return list(base)


def fetch_parent_docs_batch(
    client: OpenSearch,
    index_name: str,
    inventory_ids: List[str],
    filters: Optional[List[Dict]] = None,
    ui_fields: Optional[List[str]] = None,
) -> Dict[str, Dict]:
    """Fetch parent documents for a batch of InventoryIDs in a single query.

    Applies metadata filters at query time so non-matching docs are excluded
    by OpenSearch rather than in Python post-processing.

    For large batches (>50 IDs), splits into multiple queries to avoid
    OpenSearch clause limits.

    Args:
        client: OpenSearch client
        index_name: Main asset index name
        inventory_ids: List of InventoryIDs to fetch
        filters: Unified filters (already normalized) to apply
        ui_fields: Additional _source fields requested by the UI

    Returns:
        Dict mapping InventoryID → _source document for matching docs.
    """
    if not inventory_ids:
        return {}

    source_includes = compute_source_fields(ui_fields)
    os_filters = build_opensearch_filters(filters) if filters else []

    # Split into chunks to avoid OpenSearch max clause limits
    CHUNK_SIZE = 50
    result: Dict[str, Dict] = {}

    for i in range(0, len(inventory_ids), CHUNK_SIZE):
        chunk = inventory_ids[i : i + CHUNK_SIZE]

        # Try terms on .keyword first (fastest, exact match).
        # Fall back to match_phrase per ID for indices where InventoryID
        # is an analyzed text field — terms queries fail on values with
        # colons like "asset:uuid:..." because the analyzer tokenizes them.
        id_should_clauses: list = [
            {"terms": {"InventoryID.keyword": chunk}},
        ]
        id_should_clauses.extend(
            {"match_phrase": {"InventoryID": iid}} for iid in chunk
        )

        query_body: Dict[str, Any] = {
            "query": {
                "bool": {
                    "must": [
                        {
                            "bool": {
                                "should": id_should_clauses,
                                "minimum_should_match": 1,
                            }
                        },
                    ],
                    "must_not": [{"term": {"embedding_scope": "clip"}}],
                    "filter": list(os_filters),
                }
            },
            "size": len(chunk),
            "_source": {"includes": source_includes},
        }

        response = client.search(body=query_body, index=index_name)
        hits = response.get("hits", {}).get("hits", [])

        for hit in hits:
            source = hit.get("_source", {})
            inv_id = source.get("InventoryID", "")
            if inv_id:
                result[inv_id] = source

    return result


def classify_filters_for_embedding_index(
    filters: List[Dict],
) -> Tuple[List[Dict], List[Dict]]:
    """Split filters into those that can run on the embedding index vs those
    that must be deferred to the parent-doc enrichment step.

    The asset-embeddings index (Marengo 3.0) only has these fields:
    - embedding_type, embedding_representation, embedding_granularity,
      inventory_id, model_provider, model_name, model_version

    Everything else (Metadata.*, DigitalSourceAsset.*, etc.) must be deferred.

    Returns:
        (embedding_filters, deferred_filters)
    """
    EMBEDDING_INDEX_FIELDS = {
        "embedding_type",
        "embedding_representation",
        "embedding_granularity",
        "inventory_id",
        "model_provider",
        "model_name",
        "model_version",
        "mediaType",
    }

    embedding_filters: List[Dict] = []
    deferred_filters: List[Dict] = []

    for f in filters:
        key = f.get("key", "")
        if key in EMBEDDING_INDEX_FIELDS or key == "DigitalSourceAsset.Type":
            # These can be applied at query time on the embedding index
            # (DigitalSourceAsset.Type gets translated to embedding_type by the provider)
            embedding_filters.append(f)
        else:
            deferred_filters.append(f)

    return embedding_filters, deferred_filters
