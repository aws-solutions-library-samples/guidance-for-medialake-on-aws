"""Validation, normalization and fingerprinting of a stored search definition.

A *search definition* is everything needed to reproduce a search exactly: the
query text, semantic flags and every filter. It is what search history and
saved searches persist, and it mirrors ``SearchDefinition`` in
``medialake_user_interface/src/features/search-history/searchDefinition.ts``.

The fingerprint identifies "the same search" so history can move a repeated
search to the top and saving an identical search twice returns the existing
one. The browser computes the same fingerprint to show whether the current
search is already saved; the two implementations are held together by the
shared vectors in
``medialake_user_interface/src/features/search-history/__fixtures__/fingerprint-vectors.json``.

Rules that make the fingerprint stable:

* the query is trimmed and internal whitespace collapsed;
* semantic mode and search modes only count when the search is semantic, and
  search modes are de-duplicated and sorted;
* comma-separated ``type``/``extension`` lists are trimmed, de-duplicated and
  sorted (extensions upper-cased);
* a relative date range (``24h``/``7d``/``14d``/``30d``) drops the absolute
  dates, which the browser recomputes from "now" when the search is replayed;
* empty values are dropped, integral floats become ints, and custom metadata
  filters are sorted;
* the canonical form is JSON with sorted keys and no whitespace.
"""

import hashlib
import json
from typing import Any, Dict, List, Optional, Tuple

DEFINITION_VERSION = 1

MAX_QUERY_LENGTH = 1000
MAX_CUSTOM_METADATA_FILTERS = 25
MAX_FILTER_STRING_LENGTH = 500
MAX_DEFINITION_BYTES = 8 * 1024

SEMANTIC_MODES = ("full", "clip")
SEARCH_MODES = ("visual", "audio", "transcript")
RELATIVE_DATE_RANGES = ("24h", "7d", "14d", "30d")
CUSTOM_METADATA_OPERATORS = ("term", "match", "range")
CUSTOM_METADATA_TYPES = ("string", "number", "date")

_STRING_FILTERS = (
    "filename",
    "ingested_date_gte",
    "ingested_date_lte",
    "date_range_option",
)
_NUMBER_FILTERS = ("asset_size_gte", "asset_size_lte", "LargerThan")
_LIST_FILTERS = ("type", "extension")
_KNOWN_FILTERS = set(_STRING_FILTERS + _NUMBER_FILTERS + _LIST_FILTERS) | {
    "customMetadataFilters"
}


class SearchDefinitionError(ValueError):
    """Raised with a client-safe message when a definition is invalid."""


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _canonical_number(value: Any) -> Any:
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def _normalize_list_filter(name: str, value: Any) -> Optional[str]:
    if value is None:
        return None
    if not isinstance(value, str):
        raise SearchDefinitionError(f"filters.{name} must be a string")
    if len(value) > MAX_FILTER_STRING_LENGTH:
        raise SearchDefinitionError(f"filters.{name} is too long")
    parts = {part.strip() for part in value.split(",") if part.strip()}
    if name == "extension":
        parts = {part.upper() for part in parts}
    return ",".join(sorted(parts)) or None


def _normalize_custom_metadata(value: Any) -> List[Dict[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise SearchDefinitionError("filters.customMetadataFilters must be a list")
    if len(value) > MAX_CUSTOM_METADATA_FILTERS:
        raise SearchDefinitionError(
            f"At most {MAX_CUSTOM_METADATA_FILTERS} custom metadata filters are allowed"
        )

    normalized = []
    for entry in value:
        if not isinstance(entry, dict):
            raise SearchDefinitionError("Each custom metadata filter must be an object")
        field = entry.get("field")
        operator = entry.get("operator")
        if not isinstance(field, str) or not field.strip():
            raise SearchDefinitionError("Custom metadata filter is missing 'field'")
        if len(field) > MAX_FILTER_STRING_LENGTH:
            raise SearchDefinitionError("Custom metadata filter field is too long")
        if operator not in CUSTOM_METADATA_OPERATORS:
            raise SearchDefinitionError(
                "Custom metadata filter operator must be one of "
                + ", ".join(CUSTOM_METADATA_OPERATORS)
            )

        item: Dict[str, Any] = {"field": field.strip(), "operator": operator}
        for bound in ("gte", "lte"):
            bound_value = entry.get(bound)
            if bound_value is None or bound_value == "":
                continue
            if not (_is_number(bound_value) or isinstance(bound_value, str)):
                raise SearchDefinitionError(
                    f"Custom metadata filter '{bound}' must be a number or string"
                )
            item[bound] = _canonical_number(bound_value)
        filter_value = entry.get("value")
        if filter_value is not None and filter_value != "":
            if not isinstance(filter_value, str):
                raise SearchDefinitionError(
                    "Custom metadata filter 'value' must be a string"
                )
            if len(filter_value) > MAX_FILTER_STRING_LENGTH:
                raise SearchDefinitionError("Custom metadata filter value is too long")
            item["value"] = filter_value
        field_type = entry.get("type")
        if field_type is not None:
            if field_type not in CUSTOM_METADATA_TYPES:
                raise SearchDefinitionError(
                    "Custom metadata filter type must be one of "
                    + ", ".join(CUSTOM_METADATA_TYPES)
                )
            item["type"] = field_type
        normalized.append(item)

    return sorted(normalized, key=canonical_json)


def _normalize_filters(value: Any) -> Dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise SearchDefinitionError("filters must be an object")
    unknown = set(value) - _KNOWN_FILTERS
    if unknown:
        raise SearchDefinitionError(
            "Unknown filter(s): " + ", ".join(sorted(str(k) for k in unknown))
        )

    filters: Dict[str, Any] = {}
    for name in _LIST_FILTERS:
        normalized = _normalize_list_filter(name, value.get(name))
        if normalized:
            filters[name] = normalized
    for name in _STRING_FILTERS:
        raw = value.get(name)
        if raw is None or raw == "":
            continue
        if not isinstance(raw, str):
            raise SearchDefinitionError(f"filters.{name} must be a string")
        if len(raw) > MAX_FILTER_STRING_LENGTH:
            raise SearchDefinitionError(f"filters.{name} is too long")
        filters[name] = raw.strip() if name == "filename" else raw
    for name in _NUMBER_FILTERS:
        raw = value.get(name)
        if raw is None:
            continue
        if not _is_number(raw) or raw < 0:
            raise SearchDefinitionError(f"filters.{name} must be a non-negative number")
        filters[name] = _canonical_number(raw)

    if filters.get("date_range_option") in RELATIVE_DATE_RANGES:
        # Recomputed from "now" when replayed, so the stored absolute dates
        # would only make a saved "last 7 days" search go stale.
        filters.pop("ingested_date_gte", None)
        filters.pop("ingested_date_lte", None)

    custom = _normalize_custom_metadata(value.get("customMetadataFilters"))
    if custom:
        filters["customMetadataFilters"] = custom
    return filters


def normalize_definition(raw: Any) -> Dict[str, Any]:
    """Validate a definition from a request and return its canonical form.

    Raises:
        SearchDefinitionError: with a client-safe message.
    """
    if not isinstance(raw, dict):
        raise SearchDefinitionError("definition must be an object")

    version = raw.get("v", DEFINITION_VERSION)
    if version != DEFINITION_VERSION:
        raise SearchDefinitionError(
            f"Unsupported definition version {version!r}; expected {DEFINITION_VERSION}"
        )

    query = raw.get("q", "")
    if query is None:
        query = ""
    if not isinstance(query, str):
        raise SearchDefinitionError("q must be a string")
    query = " ".join(query.split())
    if len(query) > MAX_QUERY_LENGTH:
        raise SearchDefinitionError(f"q must be at most {MAX_QUERY_LENGTH} characters")

    semantic = raw.get("semantic", False)
    if not isinstance(semantic, bool):
        raise SearchDefinitionError("semantic must be a boolean")

    definition: Dict[str, Any] = {
        "v": DEFINITION_VERSION,
        "q": query,
        "semantic": semantic,
    }

    if semantic:
        mode = raw.get("semanticMode")
        if mode is not None:
            if mode not in SEMANTIC_MODES:
                raise SearchDefinitionError(
                    "semanticMode must be one of " + ", ".join(SEMANTIC_MODES)
                )
            definition["semanticMode"] = mode
        modes = raw.get("searchModes")
        if modes is not None:
            if not isinstance(modes, list) or any(m not in SEARCH_MODES for m in modes):
                raise SearchDefinitionError(
                    "searchModes must be a list drawn from " + ", ".join(SEARCH_MODES)
                )
            if modes:
                definition["searchModes"] = sorted(set(modes))

    filters = _normalize_filters(raw.get("filters"))
    if filters:
        definition["filters"] = filters

    if len(canonical_json(definition).encode("utf-8")) > MAX_DEFINITION_BYTES:
        raise SearchDefinitionError(
            f"definition must be at most {MAX_DEFINITION_BYTES} bytes"
        )
    return definition


def canonical_json(definition: Dict[str, Any]) -> str:
    return json.dumps(
        definition, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )


def fingerprint(definition: Dict[str, Any]) -> str:
    """Stable identifier of a *normalized* definition."""
    return hashlib.sha256(canonical_json(definition).encode("utf-8")).hexdigest()[:32]


def is_blank(definition: Dict[str, Any]) -> bool:
    """A browse-everything search with no filters, which is not worth recording."""
    return definition.get("q", "") in ("", "*") and not definition.get("filters")


def parse_definition(raw: Any) -> Tuple[Dict[str, Any], str]:
    """Normalize a request definition and return it with its fingerprint."""
    definition = normalize_definition(raw)
    return definition, fingerprint(definition)
