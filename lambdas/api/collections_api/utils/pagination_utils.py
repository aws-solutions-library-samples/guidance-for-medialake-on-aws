"""Pagination utilities for Collections API."""

import base64
import json
from typing import List, Optional

from aws_lambda_powertools import Logger

logger = Logger(service="pagination-utils")


def parse_cursor(cursor_str: Optional[str]) -> Optional[dict]:
    """Parse base64-encoded cursor"""
    if not cursor_str:
        return None
    try:
        decoded = base64.b64decode(cursor_str).decode("utf-8")
        return json.loads(decoded)
    except Exception as e:
        logger.warning(f"Invalid cursor format: {e}")
        return None


def create_cursor(
    pk: str, sk: str, gsi_pk: Optional[str] = None, gsi_sk: Optional[str] = None
) -> str:
    """Create base64-encoded cursor"""
    cursor_data = {"pk": pk, "sk": sk}
    if gsi_pk:
        cursor_data["gsi_pk"] = gsi_pk
    if gsi_sk:
        cursor_data["gsi_sk"] = gsi_sk
    json_str = json.dumps(cursor_data)
    return base64.b64encode(json_str.encode("utf-8")).decode("utf-8")


def apply_sorting(items: List[dict], sort_param: Optional[str]) -> List[dict]:
    """Apply sorting to items"""
    if not sort_param:
        return items

    reverse = sort_param.startswith("-")
    field = sort_param.lstrip("-")

    return sorted(items, key=lambda x: x.get(field, ""), reverse=reverse)
