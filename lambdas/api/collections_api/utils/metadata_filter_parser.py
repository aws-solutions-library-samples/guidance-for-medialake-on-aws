"""Utility for parsing metadata filter query parameters."""

import re
from typing import Dict

from aws_lambda_powertools import Logger

logger = Logger(service="metadata-filter-parser")

METADATA_FILTER_PREFIX = "filter[metadata."
METADATA_FILTER_SUFFIX = "]"
VALID_METADATA_KEY = re.compile(r"^[a-zA-Z0-9_-]+$")


def parse_metadata_filter_params(query_params: Dict[str, str]) -> Dict[str, str]:
    """Extract metadata filter key-value pairs from query string parameters.

    Matches parameters of the form ``filter[metadata.{KEY}]=VALUE`` and returns
    a dictionary mapping each extracted ``{KEY}`` to its ``VALUE``.  Empty keys
    (e.g. ``filter[metadata.]``) are excluded.  Keys containing characters
    other than alphanumerics, hyphens, and underscores are rejected to prevent
    OpenSearch field-path injection.  Non-matching parameters are ignored.
    """
    metadata_filters: Dict[str, str] = {}
    for param_name, param_value in query_params.items():
        if param_name.startswith(METADATA_FILTER_PREFIX) and param_name.endswith(
            METADATA_FILTER_SUFFIX
        ):
            meta_key = param_name[
                len(METADATA_FILTER_PREFIX) : -len(METADATA_FILTER_SUFFIX)
            ]
            if meta_key and VALID_METADATA_KEY.match(meta_key):
                metadata_filters[meta_key] = param_value
            elif meta_key:
                logger.warning(
                    "Invalid metadata filter key rejected",
                    extra={"key": meta_key},
                )
    return metadata_filters
