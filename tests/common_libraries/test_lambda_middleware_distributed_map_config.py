"""
Unit tests for LambdaMiddleware._make_output distributedMapConfig auto-set logic.
"""

import json
import sys
import time
from unittest.mock import MagicMock

import pytest

sys.modules.setdefault("aws_lambda_powertools.middleware_factory", MagicMock())

from common_libraries.lambda_middleware import LambdaMiddleware


@pytest.fixture
def middleware():
    return LambdaMiddleware(
        event_bus_name="test-bus",
        external_payload_bucket="test-bucket",
        assets_table_name="test-table",
        max_response_size=1,
    )


ORIG = {
    "metadata": {"pipelineExecutionId": "exec-123", "pipelineTraceId": "trace-abc"},
    "payload": {"data": {}, "assets": []},
}


def _mock_s3(mw, result_json):
    body = MagicMock()
    body.read.return_value = json.dumps(result_json).encode("utf-8")
    mw.s3.get_object.return_value = {"Body": body}


@pytest.mark.unit
class TestDistributedMapConfigAutoSet:

    def test_list_offload_sets_distributed_map_config(self, middleware):
        result = [{"a": 1}, {"b": 2}]
        _mock_s3(middleware, result)
        out = middleware._make_output(result, ORIG, time.time())
        dmc = out["metadata"]["distributedMapConfig"]
        assert dmc["s3_bucket"] == "test-bucket"
        assert isinstance(dmc["s3_key"], str)

    def test_dict_offload_does_not_set_distributed_map_config(self, middleware):
        result = {"key": "value"}
        _mock_s3(middleware, result)
        out = middleware._make_output(result, ORIG, time.time())
        assert "distributedMapConfig" not in out["metadata"]

    def test_existing_distributed_map_config_is_preserved(self, middleware):
        node_dmc = {"s3_bucket": "node-bucket", "s3_key": "node-key"}
        result = {
            "distributedMapConfig": node_dmc,
            "items": ["a", "b", "c"],
        }
        # Mock S3 get_object to return a list so the list-offload branch runs
        _mock_s3(middleware, ["a", "b", "c"])
        out = middleware._make_output(result, ORIG, time.time())
        assert out["metadata"]["distributedMapConfig"] == node_dmc
