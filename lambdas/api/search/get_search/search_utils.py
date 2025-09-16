import decimal
import json
import re
import uuid
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

from aws_lambda_powertools import Logger

logger = Logger()

# Supported special keywords for search
KEYWORDS = {
    "type": r"type:(\w+)",
    "asset_size_gte": r"asset_size_gte:([<>]=?\d+(?:\.\d+)?(?:KB|MB|GB|TB))",
    "asset_size_lte": r"asset_size_lte:([<>]=?\d+(?:\.\d+)?(?:KB|MB|GB|TB))",
    "extension": r"extension:([a-zA-Z0-9._\-*/]+)",
    "ingested_date_gte": r"ingested_date_gte:([<>]=?\d{4}-\d{2}-\d{2})",
    "ingested_date_lte": r"ingested_date_lte:([<>]=?\d{4}-\d{2}-\d{2})",
}


def parse_size_value(size_str: str) -> Optional[Dict[str, Any]]:
    """Convert size string (e.g., '1GB', '500MB') to bytes"""
    try:
        pattern = r"([<>]=?)(\d+(?:\.\d+)?)(KB|MB|GB|TB)"
        match = re.match(pattern, size_str)
        if not match:
            return None

        operator, value, unit = match.groups()
        value = float(value)

        multipliers = {"KB": 1024, "MB": 1024**2, "GB": 1024**3, "TB": 1024**4}

        bytes_value = int(value * multipliers[unit])
        return {"operator": operator, "value": bytes_value}
    except Exception as e:
        logger.warning(f"Error parsing size value: {str(e)}")
        return None


def parse_date_value(date_str: str) -> Optional[Dict]:
    """Parse date string with operator (e.g., '>2024-01-01')"""
    try:
        pattern = r"([<>]=?)(\d{4}-\d{2}-\d{2})"
        match = re.match(pattern, date_str)
        if not match:
            return None

        operator, date = match.groups()
        parsed_date = datetime.strptime(date, "%Y-%m-%d")

        return {"operator": operator, "value": parsed_date.isoformat()}
    except Exception as e:
        logger.warning(f"Error parsing date value: {str(e)}")
        return None


def parse_metadata_value(metadata_str: str) -> Optional[Dict]:
    """Parse metadata filter (e.g., 'resolution:1080p')"""
    try:
        key, value = metadata_str.split(":")
        return {"key": key, "value": value}
    except Exception as e:
        logger.warning(f"Error parsing metadata value: {str(e)}")
        return None


def parse_search_query(query: str) -> Tuple[str, Dict[str, Any]]:
    """
    Parse search query to extract filters and clean search term
    Returns tuple of (clean_query, filters)
    """
    filters = {}
    clean_query = query

    # Extract special keywords
    for keyword, pattern in KEYWORDS.items():
        matches = re.finditer(pattern, query)
        keyword_values = []

        for match in matches:
            value = match.group(1)

            # Process value based on keyword type
            if keyword == "asset_size_gte":
                parsed_value = parse_size_value(value)
            elif keyword == "asset_size_lte":
                parsed_value = parse_size_value(value)
            elif keyword == "ingested_date_gte":
                parsed_value = parse_date_value(value)
            elif keyword == "ingested_date_lte":
                parsed_value = parse_date_value(value)
            elif keyword == "extension":
                parsed_value = parse_metadata_value(value)
            elif keyword == "type":
                parsed_value = parse_metadata_value(value)
            else:
                parsed_value = value

            if parsed_value:
                keyword_values.append(parsed_value)
                # Remove the keyword:value from the clean query
                clean_query = clean_query.replace(match.group(0), "").strip()

        if keyword_values:
            filters[keyword] = keyword_values

    # Clean up extra spaces
    clean_query = " ".join(clean_query.split())

    return clean_query, filters


def replace_decimals(obj):
    if isinstance(obj, list):
        return [replace_decimals(o) for o in obj]
    elif isinstance(obj, dict):
        return {k: replace_decimals(v) for k, v in obj.items()}
    elif isinstance(obj, decimal.Decimal):
        return int(obj) if obj % 1 == 0 else float(obj)
    else:
        return obj


class CustomEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, decimal.Decimal):
            if obj % 1 > 0:
                return float(obj)
            else:
                return int(obj)

        if isinstance(obj, uuid.UUID):
            return str(obj)

        if callable(obj):  # Check if the object is a function
            return None  # Ignore function objects

        return super(CustomEncoder, self).default(obj)


def normalize_distance(dist: float) -> float:
    """
    Convert a raw embedding distance into a similarity on (0, 1],
    monotonically decreasing as distance ↑.
    """
    return 1.0 / (1.0 + dist)
