import json
import sys
from unittest.mock import MagicMock, patch

# Stub external modules that aren't available in the test environment
_file_ext_mod = MagicMock()
_file_ext_mod.SUPPORTED_EXTENSIONS = {
    "Image": ["jpg"],
    "Video": ["mp4"],
    "Audio": ["mp3"],
}
sys.modules.setdefault("file_extensions", _file_ext_mod)
sys.modules.setdefault("asset_deletion_service", MagicMock())
sys.modules.setdefault("collections_utils", MagicMock())
sys.modules.setdefault("collection_activity", MagicMock())

with patch.dict(
    "os.environ",
    {
        "ASSETS_TABLE": "test-table",
        "EVENT_BUS_NAME": "test-bus",
        "REGION": "us-east-1",
    },
):
    with patch("boto3.Session"), patch("boto3.client"), patch("boto3.resource"):
        from index import (
            normalize_event_context,
            normalize_event_contexts,
            process_records_in_parallel,
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _s3_record(bucket="b", key="k", event_name="ObjectCreated:Put", version_id=None):
    obj = {"key": key}
    if version_id:
        obj["versionId"] = version_id
    return {
        "eventSource": "aws:s3",
        "eventName": event_name,
        "s3": {"bucket": {"name": bucket}, "object": obj},
    }


def _sqs_record(body_dict):
    return {"eventSource": "aws:sqs", "body": json.dumps(body_dict)}


def _eventbridge_event(bucket="b", key="k", detail_type="Object Created"):
    return {
        "source": "aws.s3",
        "detail-type": detail_type,
        "detail": {"bucket": {"name": bucket}, "object": {"key": key}},
    }


# ---------------------------------------------------------------------------
# 1. Direct S3 record -> single context
# ---------------------------------------------------------------------------


class TestDirectS3Record:
    def test_single_context(self):
        ctxs = normalize_event_contexts(
            _s3_record(bucket="my-bucket", key="photos/img.jpg", version_id="v1")
        )
        assert len(ctxs) == 1
        assert ctxs[0]["bucket"] == "my-bucket"
        assert ctxs[0]["key"] == "photos/img.jpg"
        assert ctxs[0]["event_type"] == "ObjectCreated:Put"
        assert ctxs[0]["version_id"] == "v1"

    def test_singular_function(self):
        ctx = normalize_event_context(_s3_record(bucket="b", key="k"))
        assert ctx is not None
        assert ctx["bucket"] == "b"


# ---------------------------------------------------------------------------
# 2. SQS-wrapped S3 with multiple valid Records -> multiple contexts
# ---------------------------------------------------------------------------


class TestSQSMultipleRecords:
    def test_multiple_valid_records(self):
        body = {
            "Records": [
                _s3_record(bucket="b1", key="k1"),
                _s3_record(bucket="b2", key="k2", event_name="ObjectRemoved:Delete"),
                _s3_record(bucket="b3", key="k3"),
            ]
        }
        ctxs = normalize_event_contexts(_sqs_record(body))
        assert len(ctxs) == 3
        assert ctxs[0]["bucket"] == "b1"
        assert ctxs[1]["bucket"] == "b2"
        assert ctxs[1]["event_type"] == "ObjectRemoved:Delete"
        assert ctxs[2]["bucket"] == "b3"

    @patch("index.process_s3_event")
    @patch("index.AssetProcessor")
    def test_all_tasks_submitted(self, MockProcessor, mock_process):
        body = {
            "Records": [
                _s3_record(bucket="b1", key="k1"),
                _s3_record(bucket="b2", key="k2"),
            ]
        }
        processor = MockProcessor()
        process_records_in_parallel(processor, [_sqs_record(body)], max_workers=2)
        assert mock_process.call_count == 2
        buckets = {call.args[1]["bucket"] for call in mock_process.call_args_list}
        assert buckets == {"b1", "b2"}


# ---------------------------------------------------------------------------
# 3. Mixed valid/malformed nested records
# ---------------------------------------------------------------------------


class TestMixedValidMalformed:
    def test_missing_bucket_name_skipped(self):
        body = {
            "Records": [
                _s3_record(bucket="good", key="ok.jpg"),
                {"eventSource": "aws:s3", "s3": {"bucket": {}, "object": {"key": "x"}}},
                _s3_record(bucket="good2", key="ok2.jpg"),
            ]
        }
        ctxs = normalize_event_contexts(_sqs_record(body))
        assert len(ctxs) == 2
        assert ctxs[0]["bucket"] == "good"
        assert ctxs[1]["bucket"] == "good2"

    def test_non_dict_s3_skipped(self):
        body = {
            "Records": [
                {"eventSource": "aws:s3", "s3": "not-a-dict"},
                _s3_record(bucket="valid", key="v.jpg"),
            ]
        }
        ctxs = normalize_event_contexts(_sqs_record(body))
        assert len(ctxs) == 1
        assert ctxs[0]["bucket"] == "valid"

    def test_unrecognized_source_skipped(self):
        body = {
            "Records": [
                {
                    "eventSource": "aws:sns",
                    "s3": {"bucket": {"name": "b"}, "object": {"key": "k"}},
                },
                _s3_record(bucket="ok", key="ok.jpg"),
            ]
        }
        ctxs = normalize_event_contexts(_sqs_record(body))
        assert len(ctxs) == 1
        assert ctxs[0]["bucket"] == "ok"

    @patch("index.metrics")
    def test_malformed_records_emit_metrics(self, mock_metrics):
        body = {
            "Records": [
                {"eventSource": "aws:s3", "s3": {"bucket": {}, "object": {"key": "x"}}},
            ]
        }
        ctxs = normalize_event_contexts(_sqs_record(body))
        assert ctxs == []
        mock_metrics.add_metric.assert_called()


# ---------------------------------------------------------------------------
# 4. SQS-wrapped EventBridge -> single context
# ---------------------------------------------------------------------------


class TestSQSWrappedEventBridge:
    def test_single_context(self):
        ctxs = normalize_event_contexts(
            _sqs_record(_eventbridge_event(bucket="eb-bucket", key="eb-key"))
        )
        assert len(ctxs) == 1
        assert ctxs[0]["bucket"] == "eb-bucket"
        assert ctxs[0]["key"] == "eb-key"
        assert ctxs[0]["event_type"] == "ObjectCreated:"


# ---------------------------------------------------------------------------
# 5. Direct EventBridge -> single context (via singular func)
# ---------------------------------------------------------------------------


class TestDirectEventBridge:
    def test_singular_function(self):
        ctx = normalize_event_context(
            _eventbridge_event(
                bucket="d-bucket", key="d-key", detail_type="Object Deleted"
            )
        )
        assert ctx is not None
        assert ctx["bucket"] == "d-bucket"
        assert ctx["event_type"] == "ObjectRemoved:"

    def test_plural_function(self):
        ctxs = normalize_event_contexts(
            _eventbridge_event(bucket="d-bucket", key="d-key")
        )
        assert len(ctxs) == 1


# ---------------------------------------------------------------------------
# 6. Parse failure (invalid JSON body) -> empty list
# ---------------------------------------------------------------------------


class TestParseFailure:
    def test_invalid_json_returns_empty(self):
        sqs = {"eventSource": "aws:sqs", "body": "NOT VALID JSON{{{"}
        assert normalize_event_contexts(sqs) == []

    def test_singular_invalid_json_returns_none(self):
        sqs = {"eventSource": "aws:sqs", "body": "<<<bad>>>"}
        assert normalize_event_context(sqs) is None


# ---------------------------------------------------------------------------
# 7. Unrecognized event -> empty list
# ---------------------------------------------------------------------------


class TestUnrecognized:
    def test_empty_dict(self):
        assert normalize_event_contexts({}) == []

    def test_random_keys(self):
        assert normalize_event_contexts({"foo": "bar"}) == []

    def test_singular_returns_none(self):
        assert normalize_event_context({"foo": "bar"}) is None
