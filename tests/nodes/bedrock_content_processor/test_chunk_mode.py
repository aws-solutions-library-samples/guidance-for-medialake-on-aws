"""
Unit tests for bedrock_content_processor chunk mode logic.

Tests _detect_chunk_mode, _build_chunk_label, and handler-level chunk
processing paths.
"""

import io
import json
import os
import sys
from unittest.mock import MagicMock, patch

# ── Module-level mock setup (before any Lambda imports) ──────────────

mock_powertools = MagicMock()
mock_logger = MagicMock()
mock_tracer = MagicMock()
mock_powertools.Logger = MagicMock(return_value=mock_logger)
mock_powertools.Tracer = MagicMock(return_value=mock_tracer)
mock_tracer.capture_lambda_handler = lambda f: f
mock_tracer.capture_method = lambda f: f
mock_tracer.inject_lambda_context = lambda f: f
mock_logger.inject_lambda_context = lambda f: f
sys.modules["aws_lambda_powertools"] = mock_powertools

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

# Mock pynamodb
sys.modules["pynamodb"] = MagicMock()
sys.modules["pynamodb.models"] = MagicMock()
sys.modules["pynamodb.attributes"] = MagicMock()
sys.modules["pynamodb.indexes"] = MagicMock()
mock_pynamodb_exc = MagicMock()
mock_pynamodb_exc.DoesNotExist = type("DoesNotExist", (Exception,), {})
mock_pynamodb_exc.PutError = type("PutError", (Exception,), {})
sys.modules["pynamodb.exceptions"] = mock_pynamodb_exc

# Mock nodes_utils (Lambda imports from it)
sys.modules["nodes_utils"] = MagicMock()

os.environ.setdefault("MEDIALAKE_ASSET_TABLE", "test-asset-table")

import pytest
from nodes.bedrock_content_processor.index import (
    _build_chunk_label,
    _detect_chunk_mode,
    lambda_handler,
)

# ─────────────────────────────────────────────────────────────────────


@pytest.mark.unit
class TestDetectChunkMode:

    def test_primary_path_map_item(self):
        event = {
            "payload": {
                "map": {
                    "item": {"is_chunk": True, "url": "s3://b/k", "mediaType": "Video"}
                }
            }
        }
        ok, item = _detect_chunk_mode(event)
        assert ok is True
        assert item["url"] == "s3://b/k"

    def test_fallback_to_payload_data(self):
        event = {
            "payload": {
                "data": {"is_chunk": True, "url": "s3://b/k", "mediaType": "Video"}
            }
        }
        ok, item = _detect_chunk_mode(event)
        assert ok is True
        assert item["url"] == "s3://b/k"

    def test_missing_is_chunk_marker(self):
        event = {
            "payload": {"map": {"item": {"url": "s3://b/k", "mediaType": "Video"}}}
        }
        ok, item = _detect_chunk_mode(event)
        assert ok is False
        assert item is None

    def test_wrong_media_type(self):
        event = {
            "payload": {
                "map": {
                    "item": {"is_chunk": True, "url": "s3://b/k", "mediaType": "Audio"}
                }
            }
        }
        ok, item = _detect_chunk_mode(event)
        assert ok is False
        assert item is None

    def test_empty_event(self):
        ok, item = _detect_chunk_mode({})
        assert ok is False
        assert item is None


@pytest.mark.unit
class TestBuildChunkLabel:

    def test_first_chunk_label(self):
        result = _build_chunk_label("Summary 100", "2026-02-18 10:33Z", 1, 0, 3660)
        expected = "Summary 100 – Run 2026-02-18 10:33Z – Chunk 001 (0:00:00 – 1:01:00)"
        assert result == expected

    def test_middle_chunk_label(self):
        result = _build_chunk_label("Summary 100", "2026-02-18 10:33Z", 2, 3540, 7260)
        assert "Chunk 002" in result
        assert "0:59:00" in result
        assert "2:01:00" in result

    def test_zero_padded_index(self):
        result = _build_chunk_label("Summary 100", "2026-02-18 10:33Z", 10, 0, 3600)
        assert "Chunk 010" in result


# ─────────────────────────────────────────────────────────────────────
# Helper to build a minimal valid chunk-mode event
# ─────────────────────────────────────────────────────────────────────


def _make_chunk_event(*, prompt_source="saved", custom_label=None, custom_text=None):
    event = {
        "payload": {
            "assets": [
                {
                    "InventoryID": "inv-001",
                    "DerivedRepresentations": [
                        {
                            "Purpose": "proxy",
                            "StorageInfo": {
                                "PrimaryLocation": {
                                    "Bucket": "bucket",
                                    "ObjectKey": {"FullPath": "proxy.mp4"},
                                }
                            },
                        }
                    ],
                }
            ],
            "map": {
                "item": {
                    "is_chunk": True,
                    "url": "s3://bucket/chunk.mp4",
                    "mediaType": "Video",
                    "index": 1,
                    "start_time": 0,
                    "end_time": 3660,
                }
            },
        },
        "metadata": {
            "pipelineExecutionId": "exec-abc123",
            "pipelineExecutionStartTime": "2026-02-18 10:33Z",
        },
    }
    return event


_BASE_ENV = {
    "CONTENT_SOURCE": "proxy",
    "MODEL_ID_MEDIA": "twelvelabs.pegasus-1-2-v1:0",
    "PROMPT_SOURCE": "saved",
    "SAVED_PROMPT_NAME": "summary_100",
    "MEDIALAKE_ASSET_TABLE": "test-table",
}


@pytest.mark.unit
class TestHandlerChunkMode:

    @patch.dict("os.environ", _BASE_ENV, clear=True)
    @patch(
        "nodes.bedrock_content_processor.index.get_inference_profile_for_model",
        return_value="profile-id",
    )
    @patch("nodes.bedrock_content_processor.index.invoke_bedrock_with_retry")
    @patch("nodes.bedrock_content_processor.index.bedrock_rt")
    @patch("nodes.bedrock_content_processor.index.table")
    def test_proxy_uri_uses_chunk_url(
        self, mock_table, mock_bedrock_rt, mock_invoke, mock_profile
    ):
        mock_invoke.return_value = {
            "body": io.BytesIO(json.dumps({"message": "ok"}).encode())
        }
        mock_table.get_item.return_value = {"Item": {}}

        event = _make_chunk_event()
        lambda_handler(event, None)

        # The body passed to invoke_bedrock_with_retry should contain the chunk URL
        call_args = mock_invoke.call_args
        body_bytes = (
            call_args[0][2]
            if len(call_args[0]) > 2
            else call_args[1].get("body", call_args[0][2])
        )
        body_str = (
            body_bytes.decode() if isinstance(body_bytes, bytes) else str(body_bytes)
        )
        assert "s3://bucket/chunk.mp4" in body_str

    @patch.dict("os.environ", _BASE_ENV, clear=True)
    @patch(
        "nodes.bedrock_content_processor.index.get_inference_profile_for_model",
        return_value="profile-id",
    )
    @patch("nodes.bedrock_content_processor.index.invoke_bedrock_with_retry")
    @patch("nodes.bedrock_content_processor.index.bedrock_rt")
    @patch("nodes.bedrock_content_processor.index.table")
    def test_dynamo_key_contains_chunk_suffix(
        self, mock_table, mock_bedrock_rt, mock_invoke, mock_profile
    ):
        mock_invoke.return_value = {
            "body": io.BytesIO(json.dumps({"message": "ok"}).encode())
        }
        mock_table.get_item.return_value = {"Item": {}}

        event = _make_chunk_event()
        lambda_handler(event, None)

        # Check that update_item was called with a key ending in _chunk_001
        update_calls = mock_table.update_item.call_args_list
        assert len(update_calls) > 0
        for call in update_calls:
            expr_names = call[1].get("ExpressionAttributeNames", {})
            for v in expr_names.values():
                if "chunk_001" in v:
                    return
        pytest.fail("No update_item call had a key containing _chunk_001")

    @patch.dict(
        "os.environ",
        {
            "CONTENT_SOURCE": "proxy",
            "MODEL_ID_MEDIA": "twelvelabs.pegasus-1-2-v1:0",
            "PROMPT_SOURCE": "custom",
            "CUSTOM_PROMPT_TEXT": "Describe this video",
            "CUSTOM_PROMPT_LABEL": "MyLabel",
            "MEDIALAKE_ASSET_TABLE": "test-table",
        },
        clear=True,
    )
    @patch("nodes.bedrock_content_processor.index.check_key_exists")
    @patch(
        "nodes.bedrock_content_processor.index.get_inference_profile_for_model",
        return_value="profile-id",
    )
    @patch("nodes.bedrock_content_processor.index.invoke_bedrock_with_retry")
    @patch("nodes.bedrock_content_processor.index.bedrock_rt")
    @patch("nodes.bedrock_content_processor.index.table")
    def test_label_conflict_check_skipped(
        self, mock_table, mock_bedrock_rt, mock_invoke, mock_profile, mock_check
    ):
        mock_invoke.return_value = {
            "body": io.BytesIO(json.dumps({"message": "ok"}).encode())
        }
        mock_table.get_item.return_value = {"Item": {}}

        event = _make_chunk_event()
        lambda_handler(event, None)

        mock_check.assert_not_called()

    @patch.dict("os.environ", _BASE_ENV, clear=True)
    @patch(
        "nodes.bedrock_content_processor.index.get_inference_profile_for_model",
        return_value="profile-id",
    )
    @patch(
        "nodes.bedrock_content_processor.index.invoke_bedrock_with_retry",
        side_effect=RuntimeError("Bedrock failed"),
    )
    @patch("nodes.bedrock_content_processor.index.bedrock_rt")
    @patch("nodes.bedrock_content_processor.index.table")
    def test_failure_placeholder_written_and_reraises(
        self, mock_table, mock_bedrock_rt, mock_invoke, mock_profile
    ):
        event = _make_chunk_event()

        with pytest.raises(RuntimeError):
            lambda_handler(event, None)

        # Verify failure placeholder was written
        update_calls = mock_table.update_item.call_args_list
        assert len(update_calls) > 0
        last_call = update_calls[-1]
        expr_values = last_call[1].get("ExpressionAttributeValues", {})
        # The :v value should contain chunk_status="failed"
        v_val = expr_values.get(":v", {})
        assert v_val.get("chunk_status") == "failed"
