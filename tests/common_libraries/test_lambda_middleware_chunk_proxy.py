"""
Unit tests for LambdaMiddleware._inject_chunk_proxy and its integration
with _standardize_input for video chunk proxy patching.
"""

import copy
import sys
from unittest.mock import MagicMock, patch

import pytest

# Ensure the middleware_factory submodule mock exists before import
sys.modules.setdefault("aws_lambda_powertools.middleware_factory", MagicMock())

from common_libraries.lambda_middleware import LambdaMiddleware


@pytest.fixture
def asset_rec():
    return {
        "DerivedRepresentations": [
            {
                "Purpose": "proxy",
                "StorageInfo": {
                    "PrimaryLocation": {
                        "Bucket": "original-bucket",
                        "ObjectKey": {"FullPath": "original/key.mp4"},
                    }
                },
            }
        ]
    }


@pytest.mark.unit
class TestInjectChunkProxy:
    """Tests for the _inject_chunk_proxy static method."""

    def test_patch_via_url(self, asset_rec):
        item = {
            "is_chunk": True,
            "mediaType": "Video",
            "url": "s3://my-bucket/chunks/seg_001.mp4",
        }
        LambdaMiddleware._inject_chunk_proxy(asset_rec, item)
        loc = asset_rec["DerivedRepresentations"][0]["StorageInfo"]["PrimaryLocation"]
        assert loc["Bucket"] == "my-bucket"
        assert loc["ObjectKey"]["FullPath"] == "chunks/seg_001.mp4"
        assert loc["Key"] == "chunks/seg_001.mp4"

    def test_patch_via_bucket_key(self, asset_rec):
        item = {
            "is_chunk": True,
            "mediaType": "Video",
            "bucket": "b",
            "key": "k/seg.mp4",
        }
        LambdaMiddleware._inject_chunk_proxy(asset_rec, item)
        loc = asset_rec["DerivedRepresentations"][0]["StorageInfo"]["PrimaryLocation"]
        assert loc["Bucket"] == "b"
        assert loc["ObjectKey"]["FullPath"] == "k/seg.mp4"

    def test_non_chunk_does_nothing(self, asset_rec):
        original = copy.deepcopy(asset_rec)
        item = {"is_chunk": False, "mediaType": "Video", "url": "s3://b/k.mp4"}
        LambdaMiddleware._inject_chunk_proxy(asset_rec, item)
        assert asset_rec == original

    def test_wrong_media_type_does_nothing(self, asset_rec):
        original = copy.deepcopy(asset_rec)
        item = {"is_chunk": True, "mediaType": "Audio", "url": "s3://b/k.mp4"}
        LambdaMiddleware._inject_chunk_proxy(asset_rec, item)
        assert asset_rec == original

    def test_missing_proxy_rep_no_crash(self):
        rec = {"DerivedRepresentations": [{"Purpose": "thumbnail"}]}
        original = copy.deepcopy(rec)
        item = {"is_chunk": True, "mediaType": "Video", "url": "s3://b/k.mp4"}
        LambdaMiddleware._inject_chunk_proxy(rec, item)
        assert rec == original

    def test_none_asset_rec_no_crash(self):
        LambdaMiddleware._inject_chunk_proxy(
            None, {"is_chunk": True, "mediaType": "Video", "url": "s3://b/k.mp4"}
        )


@pytest.mark.unit
class TestStandardizeInputChunkProxy:
    """Integration test: _standardize_input patches proxy for chunk items."""

    def test_standardize_input_patches_proxy(self, asset_rec):
        mw = LambdaMiddleware(
            event_bus_name="test-bus",
            external_payload_bucket="test-bucket",
            assets_table_name="test-table",
        )

        event = {
            "item": {
                "inventory_id": "inv123",
                "is_chunk": True,
                "mediaType": "Video",
                "url": "s3://chunk-bucket/chunk.mp4",
                "index": 0,
            }
        }

        with patch.object(mw, "_fetch_asset_record", return_value=asset_rec):
            result = mw._standardize_input(event)

        loc = result["payload"]["assets"][0]["DerivedRepresentations"][0][
            "StorageInfo"
        ]["PrimaryLocation"]
        assert loc["Bucket"] == "chunk-bucket"
        assert loc["ObjectKey"]["FullPath"] == "chunk.mp4"
        assert loc["Key"] == "chunk.mp4"
