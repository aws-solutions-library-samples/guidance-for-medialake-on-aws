"""
Unit tests for twelvelabs_bedrock_invoke chunk mode detection.
"""

import sys
from unittest.mock import MagicMock

# ── Module-level mock setup (before any Lambda imports) ──────────────

mock_powertools = MagicMock()
mock_logger = MagicMock()
mock_tracer = MagicMock()
mock_powertools.Logger = MagicMock(return_value=mock_logger)
mock_powertools.Tracer = MagicMock(return_value=mock_tracer)
mock_tracer.capture_lambda_handler = lambda f: f
mock_logger.inject_lambda_context = lambda f: f
sys.modules["aws_lambda_powertools"] = mock_powertools
sys.modules["aws_lambda_powertools.utilities.typing"] = MagicMock()

mock_middleware = MagicMock()
mock_middleware.lambda_middleware = MagicMock(return_value=lambda f: f)
sys.modules["lambda_middleware"] = mock_middleware

sys.modules["boto3"] = MagicMock()
sys.modules["botocore"] = MagicMock()
sys.modules["botocore.exceptions"] = MagicMock()
sys.modules["bedrock_utils"] = MagicMock()

import pytest
from nodes.twelvelabs_bedrock_invoke.index import _detect_chunk_item

# ─────────────────────────────────────────────────────────────────────


@pytest.mark.unit
class TestDetectChunkItem:

    def test_detect_chunk_item_from_map_item(self):
        chunk = {"is_chunk": True, "mediaType": "Video", "url": "s3://b/k.mp4"}
        event = {"payload": {"map": {"item": chunk}}}
        result = _detect_chunk_item(event)
        assert result is chunk
        assert result.get("url") == "s3://b/k.mp4"

    def test_detect_chunk_item_from_payload_data(self):
        chunk = {"is_chunk": True, "mediaType": "Video", "url": "s3://b/k.mp4"}
        event = {"payload": {"data": chunk}}
        result = _detect_chunk_item(event)
        assert result is chunk
        assert result.get("url") == "s3://b/k.mp4"

    def test_detect_chunk_item_from_payload_data_item(self):
        chunk = {"is_chunk": True, "mediaType": "Video", "url": "s3://b/k.mp4"}
        event = {"payload": {"data": {"item": chunk}}}
        result = _detect_chunk_item(event)
        assert result is chunk
        assert result.get("url") == "s3://b/k.mp4"

    def test_detect_chunk_item_returns_none_for_non_chunk(self):
        chunk = {"is_chunk": False, "mediaType": "Video", "url": "s3://b/k.mp4"}
        event = {"payload": {"map": {"item": chunk}}}
        result = _detect_chunk_item(event)
        assert result is None

    def test_detect_chunk_item_returns_none_when_missing(self):
        result = _detect_chunk_item({})
        assert result is None
