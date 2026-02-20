"""
Unit tests for twelvelabs_bedrock_results chunk offset logic.

Tests _detect_chunk_item and the derived offset/scope arithmetic
used in lambda_handler's video/audio embedding loop.
"""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# ── Module-level mock setup (before any Lambda imports) ──────────────

mock_powertools = MagicMock()
mock_logger = MagicMock()
mock_tracer = MagicMock()
mock_powertools.Logger = MagicMock(return_value=mock_logger)
mock_powertools.Tracer = MagicMock(return_value=mock_tracer)
mock_tracer.capture_lambda_handler = lambda f: f
mock_tracer.inject_lambda_context = lambda f: f
mock_logger.inject_lambda_context = lambda f: f
sys.modules["aws_lambda_powertools"] = mock_powertools
sys.modules["aws_lambda_powertools.utilities"] = MagicMock()
sys.modules["aws_lambda_powertools.utilities.typing"] = MagicMock()

mock_middleware = MagicMock()
mock_middleware.lambda_middleware = MagicMock(return_value=lambda f: f)
sys.modules["lambda_middleware"] = mock_middleware

sys.modules["boto3"] = MagicMock()
sys.modules["botocore"] = MagicMock()
mock_botocore_exc = MagicMock()


class _MockClientError(Exception):
    def __init__(self, error_response, operation_name):
        self.response = error_response
        self.operation_name = operation_name
        super().__init__(str(error_response))


mock_botocore_exc.ClientError = _MockClientError
sys.modules["botocore.exceptions"] = mock_botocore_exc

# Add lambdas source to sys.path
LAMBDAS_DIR = Path(__file__).parent.parent.parent.parent / "lambdas"
if str(LAMBDAS_DIR) not in sys.path:
    sys.path.insert(0, str(LAMBDAS_DIR))

import pytest
from nodes.twelvelabs_bedrock_results.index import _detect_chunk_item, lambda_handler

# ─────────────────────────────────────────────────────────────────────

# Shared Bedrock S3 response with a single video embedding
_BEDROCK_RESPONSE = {
    "data": [
        {
            "embedding": [0.1, 0.2, 0.3],
            "startSec": 10.0,
            "endSec": 20.0,
            "embeddingScope": "asset",
        }
    ]
}


def _make_s3_mock(bedrock_response=_BEDROCK_RESPONSE):
    """Return a mock S3 client whose get_object returns *bedrock_response*."""
    body = MagicMock()
    body.read.return_value = json.dumps(bedrock_response).encode()
    s3 = MagicMock()
    s3.get_object.return_value = {"Body": body}
    return s3


def _make_event(*, chunk_item=None):
    """Build a minimal lambda event with required job fields.

    If *chunk_item* is provided it is placed at ``payload.map.item``
    to trigger chunk-mode detection.
    """
    event = {
        "payload": {
            "data": {
                "invocation_arn": "arn:aws:bedrock:us-east-1:123456789012:invocation/abc",
                "s3_bucket": "results-bucket",
                "output_file_key": "output.json",
                "input_type": "video",
            },
        },
        "metadata": {},
    }
    if chunk_item is not None:
        event["payload"]["map"] = {"item": chunk_item}
    return event


# ── _detect_chunk_item unit tests ────────────────────────────────────


@pytest.mark.unit
class TestDetectChunkItem:

    def test_from_map_item(self):
        item = {
            "is_chunk": True,
            "mediaType": "Video",
            "url": "s3://b/k.mp4",
            "start_time": 3600.0,
        }
        assert _detect_chunk_item({"payload": {"map": {"item": item}}}) is item

    def test_from_payload_data(self):
        item = {
            "is_chunk": True,
            "mediaType": "Video",
            "bucket": "b",
            "key": "k",
            "start_time": 0.0,
        }
        assert _detect_chunk_item({"payload": {"data": item}}) is item

    def test_from_payload_data_item(self):
        item = {
            "is_chunk": True,
            "mediaType": "Video",
            "url": "s3://b/k.mp4",
            "start_time": 60.0,
        }
        assert _detect_chunk_item({"payload": {"data": {"item": item}}}) is item

    def test_returns_none_for_non_chunk(self):
        assert _detect_chunk_item({"payload": {}}) is None

    def test_rejects_empty_url(self):
        item = {"is_chunk": True, "mediaType": "Video", "url": "", "start_time": 0.0}
        assert _detect_chunk_item({"payload": {"map": {"item": item}}}) is None

    def test_rejects_empty_bucket_key(self):
        item = {
            "is_chunk": True,
            "mediaType": "Video",
            "bucket": "",
            "key": "",
            "start_time": 0.0,
        }
        assert _detect_chunk_item({"payload": {"map": {"item": item}}}) is None

    def test_rejects_empty_key_only(self):
        item = {
            "is_chunk": True,
            "mediaType": "Video",
            "bucket": "b",
            "key": "",
            "start_time": 0.0,
        }
        assert _detect_chunk_item({"payload": {"map": {"item": item}}}) is None


# ── lambda_handler integration tests ─────────────────────────────────


@pytest.mark.unit
class TestLambdaHandlerChunkOffset:

    @patch("nodes.twelvelabs_bedrock_results.index.boto3")
    @patch(
        "nodes.twelvelabs_bedrock_results.index.EXTERNAL_PAYLOAD_BUCKET", "ext-bucket"
    )
    def test_chunk_mode_applies_offset_and_clip_scope(self, mock_boto3):
        s3 = _make_s3_mock()
        mock_boto3.client.return_value = s3

        chunk_item = {
            "is_chunk": True,
            "mediaType": "Video",
            "url": "s3://bucket/key.mp4",
            "start_time": 3600.0,
        }
        event = _make_event(chunk_item=chunk_item)
        lambda_handler(event, MagicMock())

        # Grab the embeddings JSON written to S3 via put_object
        put_calls = [c for c in s3.put_object.call_args_list]
        embeddings_body = json.loads(
            put_calls[0].kwargs.get("Body") or put_calls[0][1]["Body"]
        )

        emb = embeddings_body[0]
        assert emb["start_offset_sec"] == 3610.0
        assert emb["end_offset_sec"] == 3620.0
        assert emb["embedding_scope"] == "clip"

    @patch("nodes.twelvelabs_bedrock_results.index.boto3")
    @patch(
        "nodes.twelvelabs_bedrock_results.index.EXTERNAL_PAYLOAD_BUCKET", "ext-bucket"
    )
    def test_non_chunk_preserves_bedrock_offsets_and_scope(self, mock_boto3):
        s3 = _make_s3_mock()
        mock_boto3.client.return_value = s3

        event = _make_event()  # no chunk item
        lambda_handler(event, MagicMock())

        put_calls = [c for c in s3.put_object.call_args_list]
        embeddings_body = json.loads(
            put_calls[0].kwargs.get("Body") or put_calls[0][1]["Body"]
        )

        emb = embeddings_body[0]
        assert emb["start_offset_sec"] == 10.0
        assert emb["end_offset_sec"] == 20.0
        assert emb["embedding_scope"] == "asset"
