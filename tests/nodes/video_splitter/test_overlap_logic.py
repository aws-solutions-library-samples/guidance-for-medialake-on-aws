"""
Unit tests for video_splitter overlap and stride logic.

Tests _compute_chunk_bounds (pure function) and the stride-loop logic
that drives chunk iteration in lambda_handler.
"""

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

sys.modules["requests"] = MagicMock()

# Load real nodes_utils so format_duration works
COMMON_LIBS_DIR = (
    Path(__file__).parent.parent.parent.parent / "lambdas" / "common_libraries"
)
if str(COMMON_LIBS_DIR) not in sys.path:
    sys.path.insert(0, str(COMMON_LIBS_DIR))
import nodes_utils as _nodes_utils_real

sys.modules["nodes_utils"] = _nodes_utils_real

import pytest
from nodes.video_splitter.index import _compute_chunk_bounds, lambda_handler

# ─────────────────────────────────────────────────────────────────────


@pytest.mark.unit
class TestComputeChunkBounds:

    def test_no_overlap_first_chunk(self):
        start, dur = _compute_chunk_bounds(0, 3600, 0, 10800, True)
        assert start == 0
        assert dur == 3600

    def test_no_overlap_middle_chunk(self):
        start, dur = _compute_chunk_bounds(3600, 3600, 0, 10800, False)
        assert start == 3600
        assert dur == 3600

    def test_first_chunk_with_overlap(self):
        start, dur = _compute_chunk_bounds(0, 3600, 60, 10800, True)
        assert start == 0
        assert dur == 3660

    def test_middle_chunk_with_overlap(self):
        start, dur = _compute_chunk_bounds(3600, 3600, 60, 10800, False)
        assert start == 3540
        assert dur == 3720

    def test_last_chunk_clamped(self):
        start, dur = _compute_chunk_bounds(7200, 3600, 60, 9000, False)
        assert start == 7140
        assert dur == 1860  # remaining = 9000 - 7140

    def test_single_chunk_video(self):
        start, dur = _compute_chunk_bounds(0, 3600, 60, 1800, True)
        assert start == 0
        assert dur == 1800  # is_last=True, remaining = 1800


@pytest.mark.unit
class TestStrideLogic:

    @patch("nodes.video_splitter.index.os.path.getsize", return_value=1024)
    @patch("nodes.video_splitter.index.s3_client")
    @patch("nodes.video_splitter.index.create_size_constrained_segment_copy")
    @patch("nodes.video_splitter.index.get_media_info")
    def test_coverage_safeguard(
        self, mock_media_info, mock_create, mock_s3, mock_getsize
    ):
        """When actual_dur < max_chunk_dur, current_start advances to this_chunk_end."""
        shorter_dur = 2000.0
        total_duration = 5000.0
        mock_media_info.return_value = (total_duration, 1024)
        mock_create.return_value = (True, shorter_dur)

        event = {
            "payload": {
                "data": {"chunkDuration": 3600, "overlapDuration": 60},
                "assets": [
                    {
                        "InventoryID": "inv-001",
                        "DigitalSourceAsset": {"ID": "asset-001"},
                        "DerivedRepresentations": [
                            {
                                "Purpose": "proxy",
                                "StorageInfo": {
                                    "PrimaryLocation": {
                                        "Bucket": "bucket",
                                        "ObjectKey": {"FullPath": "video.mp4"},
                                    }
                                },
                            }
                        ],
                    }
                ],
            }
        }
        result = lambda_handler(event, None)
        # Handler should succeed and produce segments
        assert isinstance(result, list)
        assert len(result) >= 2
        # When actual_dur < max_chunk_dur, current_start should advance to
        # this_chunk_end (2000), not current_start + max_chunk_dur (3600)
        second_logical_start = result[1]["logical_start_time"]
        assert second_logical_start == shorter_dur

    def test_2_5h_video_produces_3_chunks(self):
        """Full stride loop for 9000s video with 3600s chunks and 60s overlap."""
        max_chunk_dur = 3600
        overlap_dur = 60
        total_duration = 9000

        current_start = 0.0
        actual_starts = []
        seg_idx = 0

        while current_start < total_duration:
            seg_idx += 1
            is_first = seg_idx == 1
            actual_start, actual_max_dur = _compute_chunk_bounds(
                current_start, max_chunk_dur, overlap_dur, total_duration, is_first
            )
            actual_starts.append(actual_start)
            # Assume no size constraint: actual_dur == actual_max_dur
            actual_dur = actual_max_dur
            this_chunk_end = actual_start + actual_dur

            next_current_start = current_start + max_chunk_dur
            next_planned_actual_start = max(0.0, next_current_start - overlap_dur)
            if this_chunk_end < next_planned_actual_start:
                current_start = this_chunk_end
            else:
                current_start = next_current_start

        assert seg_idx == 3
        assert actual_starts == [0, 3540, 7140]


@pytest.mark.unit
class TestValidation:

    @patch("nodes.video_splitter.index.get_media_info")
    @patch("nodes.video_splitter.index.s3_client")
    def test_overlap_gte_chunk_duration_returns_400(self, mock_s3, mock_media_info):
        event = {
            "payload": {
                "data": {
                    "chunkDuration": 3600,
                    "overlapDuration": 3600,
                },
                "assets": [
                    {
                        "InventoryID": "inv-001",
                        "DigitalSourceAsset": {"ID": "asset-001"},
                        "DerivedRepresentations": [
                            {
                                "Purpose": "proxy",
                                "StorageInfo": {
                                    "PrimaryLocation": {
                                        "Bucket": "bucket",
                                        "ObjectKey": {"FullPath": "video.mp4"},
                                    }
                                },
                            }
                        ],
                    }
                ],
            }
        }
        result = lambda_handler(event, None)
        assert result["statusCode"] == 400
        assert (
            "error" in result.get("body", "").lower()
            or "overlap" in result.get("body", "").lower()
        )
