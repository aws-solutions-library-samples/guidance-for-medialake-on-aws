"""
Unit tests for configuration sanitization in external_metadata_fetch node.

Tests whitespace stripping of node configuration values and leading slash
normalization for normalizer_config_s3_path.

**Feature: external-metadata-enrichment**
"""

import json
import os
import sys
from unittest.mock import MagicMock, patch

# Mock aws_lambda_powertools before any imports that might trigger it
mock_powertools = MagicMock()
mock_powertools.Logger = MagicMock(return_value=MagicMock())
mock_powertools.Tracer = MagicMock(return_value=MagicMock())
mock_powertools.utilities = MagicMock()
mock_powertools.utilities.typing = MagicMock()
mock_powertools.utilities.typing.LambdaContext = MagicMock()
sys.modules["aws_lambda_powertools"] = mock_powertools
sys.modules["aws_lambda_powertools.utilities"] = mock_powertools.utilities
sys.modules["aws_lambda_powertools.utilities.typing"] = mock_powertools.utilities.typing

# Also mock lambda_middleware
sys.modules["lambda_middleware"] = MagicMock()

import pytest
from nodes.external_metadata_fetch.index import (
    _get_node_config,
    _sanitize_config_strings,
)
from nodes.external_metadata_fetch.normalizers import (
    clear_config_cache,
    resolve_normalizer_config,
)


# ---------------------------------------------------------------------------
# _sanitize_config_strings
# ---------------------------------------------------------------------------
@pytest.mark.unit
class TestSanitizeConfigStrings:
    """Tests for the _sanitize_config_strings helper."""

    def test_strips_leading_and_trailing_whitespace(self):
        """String values have leading/trailing whitespace removed."""
        config = {"key": "  value  "}
        assert _sanitize_config_strings(config) == {"key": "value"}

    def test_preserves_non_string_values(self):
        """Non-string values (int, float, None) are passed through unchanged."""
        config = {"retries": 3, "backoff": 1.5, "empty": None}
        assert _sanitize_config_strings(config) == config

    def test_recursively_sanitizes_nested_dicts(self):
        """Nested dicts have their string values stripped too."""
        config = {
            "outer": " hello ",
            "nested": {"inner": " world ", "num": 42},
        }
        result = _sanitize_config_strings(config)
        assert result["outer"] == "hello"
        assert result["nested"]["inner"] == "world"
        assert result["nested"]["num"] == 42

    def test_empty_dict_returns_empty(self):
        """An empty dict returns an empty dict."""
        assert _sanitize_config_strings({}) == {}

    def test_already_clean_strings_unchanged(self):
        """Strings without extra whitespace are returned as-is."""
        config = {"a": "clean", "b": "also_clean"}
        assert _sanitize_config_strings(config) == config


# ---------------------------------------------------------------------------
# _get_node_config whitespace sanitization
# ---------------------------------------------------------------------------
@pytest.mark.unit
class TestGetNodeConfigWhitespaceSanitization:
    """Verify _get_node_config strips whitespace from config values at every level."""

    def _make_event(self, node_config: dict) -> dict:
        return {"payload": {"data": {"node_config": node_config}}}

    def test_strips_whitespace_from_root_level_strings(self):
        """Root-level string config values have whitespace stripped."""
        event = self._make_event(
            {
                "adapter_type": "  generic_rest  ",
                "auth_type": " oauth2_client_credentials ",
                "secret_arn": "  arn:aws:secretsmanager:us-east-1:123:secret:medialake/creds  ",  # pragma: allowlist secret
                "metadata_endpoint": " https://api.example.com/v1/assets ",
            }
        )
        cfg = _get_node_config(event)
        assert cfg.adapter_type == "generic_rest"
        assert cfg.auth_type == "oauth2_client_credentials"
        assert (
            cfg.secret_arn
            == "arn:aws:secretsmanager:us-east-1:123:secret:medialake/creds"
        )
        assert cfg.metadata_endpoint == "https://api.example.com/v1/assets"

    def test_strips_whitespace_from_nested_config_values(self):
        """String values inside nested sub-configs are recursively stripped."""
        event = self._make_event(
            {
                "adapter_type": "generic_rest",
                "auth_type": "api_key",
                "secret_arn": "arn:aws:secretsmanager:us-east-1:123:secret:medialake/creds",  # pragma: allowlist secret
                "metadata_endpoint": "https://api.example.com",
                "normalizer_config": {
                    "source_type": "  generic_xml  ",
                    "config_s3_path": "  normalizer-configs/config.json  ",
                },
            }
        )
        cfg = _get_node_config(event)
        assert cfg.normalizer_config["source_type"] == "generic_xml"
        assert (
            cfg.normalizer_config["config_s3_path"] == "normalizer-configs/config.json"
        )

    def test_preserves_non_string_values(self):
        """Numeric, None, and other non-string values are left untouched."""
        event = self._make_event(
            {
                "adapter_type": "generic_rest",
                "auth_type": "api_key",
                "secret_arn": "arn:aws:secretsmanager:us-east-1:123:secret:medialake/creds",  # pragma: allowlist secret
                "metadata_endpoint": "https://api.example.com",
                "max_retries": 5,
                "initial_backoff_seconds": 2.0,
            }
        )
        cfg = _get_node_config(event)
        assert cfg.max_retries == 5
        assert cfg.initial_backoff_seconds == 2.0


# ---------------------------------------------------------------------------
# resolve_normalizer_config leading-slash handling
# ---------------------------------------------------------------------------
@pytest.mark.unit
class TestResolveNormalizerConfigLeadingSlash:
    """Verify resolve_normalizer_config strips leading slashes from S3 path."""

    def _setup_s3_mock(self, s3_config: dict):
        """Return a mock S3 client that returns the given config."""
        mock_s3 = MagicMock()
        mock_body = MagicMock()
        mock_body.read.return_value = json.dumps(s3_config).encode("utf-8")
        mock_s3.get_object.return_value = {"Body": mock_body}
        return mock_s3

    def test_strips_single_leading_slash(self):
        """A path like '/normalizer-configs/cfg.json' is corrected."""
        clear_config_cache()
        s3_config = {"source_namespace_prefix": "TEST"}
        mock_s3 = self._setup_s3_mock(s3_config)

        node_config = {
            "source_type": "generic_xml",
            "config_s3_path": "/normalizer-configs/cfg.json",
        }

        original = os.environ.get("IAC_ASSETS_BUCKET")
        os.environ["IAC_ASSETS_BUCKET"] = "test-bucket"
        try:
            with patch(
                "nodes.external_metadata_fetch.normalizers.config_loader.get_s3_client",
                return_value=mock_s3,
            ):
                result = resolve_normalizer_config(node_config)

            # Verify the S3 key used had no leading slash
            mock_s3.get_object.assert_called_once_with(
                Bucket="test-bucket", Key="normalizer-configs/cfg.json"
            )
            assert result == s3_config
        finally:
            if original is not None:
                os.environ["IAC_ASSETS_BUCKET"] = original
            else:
                os.environ.pop("IAC_ASSETS_BUCKET", None)
            clear_config_cache()

    def test_strips_multiple_leading_slashes(self):
        """A path like '///normalizer-configs/cfg.json' is corrected."""
        clear_config_cache()
        s3_config = {"key": "value"}
        mock_s3 = self._setup_s3_mock(s3_config)

        node_config = {
            "source_type": "generic_xml",
            "config_s3_path": "///normalizer-configs/cfg.json",
        }

        original = os.environ.get("IAC_ASSETS_BUCKET")
        os.environ["IAC_ASSETS_BUCKET"] = "test-bucket"
        try:
            with patch(
                "nodes.external_metadata_fetch.normalizers.config_loader.get_s3_client",
                return_value=mock_s3,
            ):
                resolve_normalizer_config(node_config)

            mock_s3.get_object.assert_called_once_with(
                Bucket="test-bucket", Key="normalizer-configs/cfg.json"
            )
        finally:
            if original is not None:
                os.environ["IAC_ASSETS_BUCKET"] = original
            else:
                os.environ.pop("IAC_ASSETS_BUCKET", None)
            clear_config_cache()

    def test_path_without_leading_slash_unchanged(self):
        """A clean path like 'normalizer-configs/cfg.json' works as before."""
        clear_config_cache()
        s3_config = {"key": "value"}
        mock_s3 = self._setup_s3_mock(s3_config)

        node_config = {
            "source_type": "generic_xml",
            "config_s3_path": "normalizer-configs/cfg.json",
        }

        original = os.environ.get("IAC_ASSETS_BUCKET")
        os.environ["IAC_ASSETS_BUCKET"] = "test-bucket"
        try:
            with patch(
                "nodes.external_metadata_fetch.normalizers.config_loader.get_s3_client",
                return_value=mock_s3,
            ):
                resolve_normalizer_config(node_config)

            mock_s3.get_object.assert_called_once_with(
                Bucket="test-bucket", Key="normalizer-configs/cfg.json"
            )
        finally:
            if original is not None:
                os.environ["IAC_ASSETS_BUCKET"] = original
            else:
                os.environ.pop("IAC_ASSETS_BUCKET", None)
            clear_config_cache()
