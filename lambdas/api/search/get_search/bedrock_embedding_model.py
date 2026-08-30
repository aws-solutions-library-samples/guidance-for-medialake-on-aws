"""
Version-aware selection of the TwelveLabs Marengo text-embedding model on Bedrock.

The query text MUST be embedded with the same model version as the stored
vectors, or the query lands in an incompatible embedding space (cosine distances
collapse to ~1.0 and ranking becomes random). These pure helpers centralize the
version -> (inference profile, request payload) mapping so every embedding path
stays consistent.
"""

from typing import Any, Dict


def _region_prefix(region: str) -> str:
    """Map an AWS region to its Bedrock cross-region inference prefix."""
    if region.startswith("eu-"):
        return "eu"
    if region.startswith("ap-"):
        return "apac"
    return "us"  # us-* and any unknown region default to US


def resolve_inference_profile(version: str, region: str) -> str:
    """Return the regional inference profile id for the given Marengo version."""
    model = (
        "twelvelabs.marengo-embed-3-0-v1:0"
        if str(version) == "3.0"
        else "twelvelabs.marengo-embed-2-7-v1:0"
    )
    return f"{_region_prefix(region)}.{model}"


def build_text_payload(version: str, query_text: str) -> Dict[str, Any]:
    """Return the InvokeModel body for a text query, per the version's schema.

    Marengo 3.0 nests the text under a ``text`` object; 2.7 uses a flat field.
    """
    if str(version) == "3.0":
        return {"inputType": "text", "text": {"inputText": query_text}}
    return {"inputType": "text", "inputText": query_text}
