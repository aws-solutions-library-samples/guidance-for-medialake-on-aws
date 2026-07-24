"""S3 Vectors index metadata-filterability configuration for the store node.

Return-only metadata keys declared non-filterable at index creation so the index's
filterable schema stays small and deterministic. This prevents the schema-
establishment race where `embedding_option` filterability is silently dropped for
vectors written into a fresh index under concurrent bulk load.

Keep this list in sync with NON_FILTERABLE_METADATA_KEYS in
medialake_constructs/shared_constructs/s3_vectors.py. The Lambda is a separate
deployment package and cannot import the CDK construct, so the list is duplicated;
tests/unit/test_store_node_metadata_config.py asserts the two stay identical.

The keys search filters on (inventory_id, embedding_option, embedding_scope,
content_type) are intentionally NOT listed here and remain filterable.
"""

NON_FILTERABLE_METADATA_KEYS = [
    "timestamp",
    "start_offset_sec",
    "end_offset_sec",
    "start_timecode",
    "end_timecode",
    "embedding_dimension",
    "space_type",
    "model_provider",
    "model_name",
    "model_version",
]
