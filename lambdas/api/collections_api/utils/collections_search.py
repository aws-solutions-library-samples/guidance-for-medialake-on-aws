"""OpenSearch search utilities for Collections API."""

import os
from typing import Any, Dict, List, Optional, Tuple

from aws_lambda_powertools import Logger
from utils.opensearch_utils import get_opensearch_client

logger = Logger(service="collections-search")

COLLECTIONS_INDEX_NAME = os.environ.get("COLLECTIONS_INDEX_NAME", "")
# NOTE: COLLECTIONS_INDEX_NAME is the OpenSearch index for collection/group metadata
# documents (synced from DynamoDB). This is distinct from OPENSEARCH_INDEX used in
# opensearch_utils.py, which points to the media/assets index.


def search_collections(
    user_id: str,
    search_text: Optional[str] = None,
    status_filter: Optional[str] = None,
    collection_type_filter: Optional[str] = None,
    owner_filter: Optional[str] = None,
    parent_id_filter: Optional[str] = None,
    metadata_filters: Optional[Dict[str, str]] = None,
    tag_filter: Optional[List[str]] = None,
    visibility_filter: Optional[List[str]] = None,
    updated_within: Optional[str] = None,
    collection_ids_filter: Optional[set] = None,
    page: int = 1,
    page_size: int = 50,
    sort_field: str = "name",
    sort_direction: str = "asc",
) -> Tuple[List[Dict[str, Any]], int]:
    """
    Search/list collections via OpenSearch with access control at query time.

    Access control is enforced via a bool should clause:
    - ownerId == user_id
    - isPublic == true
    - sharedWithUserIds contains user_id

    No post-filtering needed. totalResults from hits.total.value is accurate.

    Args:
        user_id: Required. Current user ID for access control.
        search_text: Optional free-text search query (name, description, and metadata).
        status_filter: Optional status value to filter by (exact match).
        collection_type_filter: Optional collectionTypeId to filter by.
        owner_filter: Optional ownerId to filter by.
        metadata_filters: Optional dict of metadata key-value pairs for near-exact filtering.
            Each entry produces a fuzzy filter on customMetadata.{key}.keyword
            with fuzziness 1 (tolerates one character difference).
            Multiple entries use AND logic.
        tag_filter: Optional list of tag values (`terms` clause on `tags`). Multiple
            values match via OR semantics within the filter.
        visibility_filter: Optional list of visibility buckets — "public" matches
            `isPublic=true`, "shared" matches `sharedWithUserIds contains user_id`,
            "private" matches owner-and-not-public.
        updated_within: Optional bucket string ("24h" | "7d" | "30d") — adds a
            `range` filter on `updatedAt`.
        collection_ids_filter: Optional set of collection IDs to restrict results to.
            Used for groupIds filtering — pushed into the OpenSearch query so
            pagination and total_hits remain accurate.
        parent_id_filter: Controls parentId filtering:
            - None or "__root__": must_not exists on parentId (roots only)
            - specific ID: term filter on parentId
            - "__all__": skip parentId filtering entirely
        page: 1-based page number (default 1).
        page_size: Results per page (default 50).
        sort_field: Sort field — "name", "createdAt", "updatedAt", or
            "customMetadata.<key>" (default "name").
        sort_direction: "asc" or "desc" (default "asc").

    Returns:
        Tuple of (results, total_hits)

    Raises:
        ConnectionError: When OpenSearch is unreachable or not configured.
        Exception: For other OpenSearch query failures.
    """
    client = get_opensearch_client()
    if not client:
        raise ConnectionError("OpenSearch client not available")

    if not COLLECTIONS_INDEX_NAME:
        raise ConnectionError("COLLECTIONS_INDEX_NAME not configured")

    # Compute from/size — no over-fetch
    from_offset = (page - 1) * page_size
    size = page_size

    # --- Build bool query ---

    # Always filter on documentType
    filter_clauses: List[Dict[str, Any]] = [{"term": {"documentType": "collection"}}]

    if status_filter:
        filter_clauses.append({"term": {"status": status_filter}})

    if collection_type_filter:
        filter_clauses.append({"term": {"collectionTypeId": collection_type_filter}})

    if owner_filter:
        filter_clauses.append({"term": {"ownerId": owner_filter}})

    # parentId filtering
    must_not_clauses: List[Dict[str, Any]] = []
    if parent_id_filter == "__all__":
        # No parentId filtering — return all collections (roots + children)
        pass
    elif parent_id_filter is None or parent_id_filter == "__root__":
        # Roots only: must not have a parentId field
        must_not_clauses.append({"exists": {"field": "parentId"}})
    else:
        # Specific parent: return children of that parent
        filter_clauses.append({"term": {"parentId": parent_id_filter}})

    # Collection IDs filter (for groupIds — pushed into OpenSearch for correct pagination)
    if collection_ids_filter is not None:
        if collection_ids_filter:
            filter_clauses.append({"terms": {"id": list(collection_ids_filter)}})
        else:
            # Empty set means no collections match the groups — short-circuit
            return [], 0

    # Metadata key-value filters (AND logic — near-exact match with fuzziness 1)
    if metadata_filters:
        for key, value in metadata_filters.items():
            filter_clauses.append(
                {
                    "fuzzy": {
                        f"customMetadata.{key}.keyword": {
                            "value": value,
                            "fuzziness": 1,
                        }
                    }
                }
            )

    # Tag filter — OR semantics across values via the OpenSearch `terms` clause.
    # Empty list is treated as "no filter" so callers can pass through an unparsed
    # optional cleanly.
    if tag_filter:
        filter_clauses.append({"terms": {"tags": tag_filter}})

    # Visibility filter — multi-select across public/shared/private. Each value
    # maps to a different structural query so we combine them as `should` clauses
    # under a dedicated bool with `minimum_should_match: 1`. This is separate from
    # the access-control `should` block so the two concerns don't interfere.
    if visibility_filter:
        visibility_should: List[Dict[str, Any]] = []
        for v in visibility_filter:
            if v == "public":
                visibility_should.append({"term": {"isPublic": True}})
            elif v == "shared":
                visibility_should.append({"term": {"sharedWithUserIds": user_id}})
            elif v == "private":
                # Private = not public AND owned by the current user. Anything
                # else in DynamoDB that isn't public/shared to this user is
                # already filtered out by the access-control should block.
                visibility_should.append(
                    {
                        "bool": {
                            "must": [
                                {"term": {"ownerId": user_id}},
                                {"term": {"isPublic": False}},
                            ]
                        }
                    }
                )
        if visibility_should:
            filter_clauses.append(
                {
                    "bool": {
                        "should": visibility_should,
                        "minimum_should_match": 1,
                    }
                }
            )

    # Updated-within — bucket values map to simple range clauses. "now-" syntax
    # is OpenSearch's date math and doesn't require parsing on our side.
    if updated_within:
        window_map = {"24h": "now-24h", "7d": "now-7d", "30d": "now-30d"}
        window_lower = window_map.get(updated_within)
        if window_lower:
            filter_clauses.append({"range": {"updatedAt": {"gte": window_lower}}})

    # Access control should clause (always present)
    should_clauses: List[Dict[str, Any]] = [
        {"term": {"ownerId": user_id}},
        {"term": {"isPublic": True}},
        {"term": {"sharedWithUserIds": user_id}},
    ]

    # Optional full-text search. We combine three shapes so the user's typing
    # experience matches what a normal app search feels like:
    #   1. `multi_match` (phrase_prefix): ranks documents whose `name` starts with
    #      what the user typed — so typing "acc" surfaces "Accessibility" after
    #      three keystrokes, not after they type the whole word.
    #   2. `multi_match` (best_fields, fuzzy): tolerates typos on full tokens so
    #      "accesibility" (missing an s) still finds the collection.
    #   3. `wildcard` on `name.keyword`: substring match for cases where the typed
    #      fragment sits in the middle of the name (e.g. "essib" → "Accessibility").
    # Wrapping them in a `should` bool with `minimum_should_match: 1` means any one
    # of the three is enough; matching multiple boosts relevance.
    #
    # NOTE: `phrase_prefix` and fuzzy `multi_match` cannot target `keyword` fields —
    # OpenSearch rejects the query if the field set expands to a keyword via
    # `customMetadata.*` (which includes auto-generated `.keyword` subfields).
    # So the two `multi_match` clauses stick to analyzed `text` fields (`name`,
    # `description`) and a separate `match` clause handles customMetadata values.
    must_clauses: List[Dict[str, Any]] = []
    if search_text:
        search_text_lower = search_text.lower()
        must_clauses.append(
            {
                "bool": {
                    "should": [
                        # Prefix match — most important for typing experience.
                        # Prefix matches on `name` (text field, standard analyzer →
                        # lowercased tokens) so casing differences don't matter.
                        {
                            "multi_match": {
                                "query": search_text,
                                "type": "phrase_prefix",
                                "fields": ["name^3", "description"],
                            }
                        },
                        # Fuzzy full-token match — tolerates typos.
                        {
                            "multi_match": {
                                "query": search_text,
                                "type": "best_fields",
                                "fields": ["name^2", "description"],
                                "fuzziness": "AUTO",
                                "prefix_length": 1,
                            }
                        },
                        # Custom metadata is indexed as `object, dynamic: true`, so
                        # every key lands as a text+keyword pair. We match against
                        # the base text fields (not `.keyword`) so phrase_prefix
                        # isn't needed here — a regular match with fuzziness covers
                        # it. `customMetadata.*` is safe for `match` / `multi_match`
                        # without phrase_prefix.
                        {
                            "multi_match": {
                                "query": search_text,
                                "type": "best_fields",
                                "fields": ["customMetadata.*"],
                                "fuzziness": "AUTO",
                                "prefix_length": 1,
                                "lenient": True,
                            }
                        },
                        # Substring match on the raw keyword via wildcard. Covers
                        # cases where the typed fragment sits in the middle of the
                        # name — the analyzed `text` field wouldn't surface those.
                        {
                            "wildcard": {
                                "name.keyword": {
                                    "value": f"*{search_text_lower}*",
                                    "case_insensitive": True,
                                }
                            }
                        },
                    ],
                    "minimum_should_match": 1,
                }
            }
        )

    # Assemble bool query
    bool_query: Dict[str, Any] = {
        "filter": filter_clauses,
        "should": should_clauses,
        "minimum_should_match": 1,
    }

    if must_clauses:
        bool_query["must"] = must_clauses

    if must_not_clauses:
        bool_query["must_not"] = must_not_clauses

    # Sort clause
    # Standard fields map directly. For `name` we use a Painless script that
    # lowercases the `.keyword` subfield so casing doesn't fragment the order —
    # e.g. "Accessibility", "animation", "Archive" all cluster alphabetically
    # rather than uppercase first then lowercase. Custom metadata fields sort on
    # the dynamically-generated `.keyword` subfield that OpenSearch creates for
    # every string value written under `customMetadata.*`. `missing: _last` keeps
    # documents without the field from polluting the top of the list.
    if sort_field == "name":
        sort_clause: Dict[str, Any] = {
            "_script": {
                "type": "string",
                "script": {
                    "lang": "painless",
                    "source": (
                        "doc['name.keyword'].size() > 0 "
                        "? doc['name.keyword'].value.toLowerCase() : ''"
                    ),
                },
                "order": sort_direction,
            }
        }
    elif sort_field.startswith("customMetadata."):
        sort_clause = {
            f"{sort_field}.keyword": {
                "order": sort_direction,
                "missing": "_last",
                "unmapped_type": "keyword",
            }
        }
    else:
        # createdAt, updatedAt — use directly
        sort_clause = {sort_field: {"order": sort_direction}}

    query_body: Dict[str, Any] = {
        "query": {"bool": bool_query},
        "sort": [sort_clause, {"createdAt": {"order": "asc"}}, {"_id": "asc"}],
        "from": from_offset,
        "size": size,
    }

    logger.info(
        "Executing OpenSearch collections query",
        extra={
            "user_id": user_id,
            "search_text": search_text,
            "parent_id_filter": parent_id_filter,
            "page": page,
            "page_size": page_size,
            "from_offset": from_offset,
            "sort_field": sort_field,
            "sort_direction": sort_direction,
        },
    )
    logger.debug(
        "OpenSearch collections query body",
        extra={"query_body": query_body},
    )

    response = client.search(body=query_body, index=COLLECTIONS_INDEX_NAME)

    hits = response.get("hits", {})
    total_hits = hits.get("total", {}).get("value", 0)
    results: List[Dict[str, Any]] = []

    for hit in hits.get("hits", []):
        doc = hit["_source"]
        # Add PK/SK fields for backward compatibility with format_collection_item
        doc_id = doc.get("id", hit["_id"])
        doc["PK"] = f"COLL#{doc_id}"
        doc["SK"] = "METADATA"
        results.append(doc)

    logger.info(
        "OpenSearch query completed",
        extra={
            "total_hits": total_hits,
            "results_returned": len(results),
        },
    )

    return results, total_hits


def search_groups(
    user_id: str,
    search_text: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    sort_field: str = "name",
    sort_direction: str = "asc",
) -> Tuple[List[Dict[str, Any]], int]:
    """
    Search/list collection groups via OpenSearch with access control.

    Access control: ownerId == user_id OR isPublic == true.

    Args:
        user_id: Required. Current user ID for access control.
        search_text: Optional free-text search (name, description).
        page: 1-based page number (default 1).
        page_size: Results per page (default 20).
        sort_field: Sort field — "name", "createdAt", or "updatedAt".
        sort_direction: "asc" or "desc".

    Returns:
        Tuple of (results, total_hits)
    """
    client = get_opensearch_client()
    if not client:
        raise ConnectionError("OpenSearch client not available")

    if not COLLECTIONS_INDEX_NAME:
        raise ConnectionError("COLLECTIONS_INDEX_NAME not configured")

    from_offset = (page - 1) * page_size

    filter_clauses: List[Dict[str, Any]] = [
        {"term": {"documentType": "collection_group"}}
    ]

    should_clauses: List[Dict[str, Any]] = [
        {"term": {"ownerId": user_id}},
        {"term": {"isPublic": True}},
    ]

    must_clauses: List[Dict[str, Any]] = []
    if search_text:
        must_clauses.append(
            {
                "multi_match": {
                    "query": search_text,
                    "fields": ["name", "description"],
                }
            }
        )

    bool_query: Dict[str, Any] = {
        "filter": filter_clauses,
        "should": should_clauses,
        "minimum_should_match": 1,
    }

    if must_clauses:
        bool_query["must"] = must_clauses

    if sort_field == "name":
        sort_clause = {
            "_script": {
                "type": "string",
                "script": {
                    "lang": "painless",
                    "source": "doc['name.keyword'].size() > 0 ? doc['name.keyword'].value.toLowerCase() : ''",
                },
                "order": sort_direction,
            }
        }
    else:
        sort_clause = {sort_field: {"order": sort_direction}}

    query_body: Dict[str, Any] = {
        "query": {"bool": bool_query},
        "sort": [sort_clause, {"createdAt": {"order": "asc"}}, {"_id": "asc"}],
        "from": from_offset,
        "size": page_size,
    }

    logger.info(
        "Executing OpenSearch groups query",
        extra={
            "user_id": user_id,
            "search_text": search_text,
            "page": page,
            "page_size": page_size,
        },
    )
    logger.debug(
        "OpenSearch groups query body",
        extra={"query_body": query_body},
    )

    response = client.search(body=query_body, index=COLLECTIONS_INDEX_NAME)

    hits = response.get("hits", {})
    total_hits = hits.get("total", {}).get("value", 0)
    results: List[Dict[str, Any]] = []

    for hit in hits.get("hits", []):
        doc = hit["_source"]
        doc_id = doc.get("id", hit["_id"])
        doc["PK"] = f"GROUP#{doc_id}"
        doc["SK"] = "METADATA"
        results.append(doc)

    logger.info(
        "OpenSearch groups query completed",
        extra={"total_hits": total_hits, "results_returned": len(results)},
    )

    return results, total_hits


def get_metadata_keys(user_id: str) -> List[str]:
    """
    Return sorted list of distinct metadata key names from the OpenSearch index mapping.

    Reads the index mapping and extracts property names under
    ``customMetadata.properties``.  Returns an empty list when no custom
    metadata properties have been indexed yet.

    Args:
        user_id: Current user ID (reserved for future access-control use).

    Returns:
        Alphabetically sorted list of metadata key name strings.

    Raises:
        ConnectionError: When the OpenSearch client is unavailable.
    """
    client = get_opensearch_client()
    if not client:
        raise ConnectionError("OpenSearch client not available")

    if not COLLECTIONS_INDEX_NAME:
        raise ConnectionError("COLLECTIONS_INDEX_NAME not configured")

    mapping = client.indices.get_mapping(index=COLLECTIONS_INDEX_NAME)
    props = mapping[COLLECTIONS_INDEX_NAME]["mappings"]["properties"]
    custom_metadata_props = props.get("customMetadata", {}).get("properties", {})

    return sorted(custom_metadata_props.keys())
