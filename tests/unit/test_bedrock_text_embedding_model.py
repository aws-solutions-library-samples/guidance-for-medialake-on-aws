"""
Tests for selecting the Bedrock text-embedding model + payload by Marengo version.

Regression: the S3 Vector search path embedded query text with Marengo 2.7 while
clips were stored as Marengo 3.0 vectors, producing an incompatible embedding
space (every cosine distance ~1.0, random ranking). The query must be embedded
with the SAME model version as the stored vectors.
"""

import importlib.util
import os

# Load the pure helper module directly by path — avoids importing the full
# base_embedding_store (which builds boto3 clients and imports twelvelabs at
# module load, neither available in the unit-test environment).
_HELPER = os.path.join(
    os.path.dirname(__file__),
    "..",
    "..",
    "lambdas",
    "api",
    "search",
    "get_search",
    "bedrock_embedding_model.py",
)
_spec = importlib.util.spec_from_file_location("bedrock_embedding_model", _HELPER)
bem = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bem)


class TestResolveInferenceProfile:
    """resolve_inference_profile(version, region) -> regional inference profile id"""

    def test_version_3_0_uses_3_0_model(self):
        assert (
            bem.resolve_inference_profile("3.0", "us-east-1")
            == "us.twelvelabs.marengo-embed-3-0-v1:0"
        )

    def test_version_2_7_uses_2_7_model(self):
        assert (
            bem.resolve_inference_profile("2.7", "us-east-1")
            == "us.twelvelabs.marengo-embed-2-7-v1:0"
        )

    def test_region_prefix_eu(self):
        assert (
            bem.resolve_inference_profile("3.0", "eu-west-1")
            == "eu.twelvelabs.marengo-embed-3-0-v1:0"
        )

    def test_region_prefix_ap(self):
        assert (
            bem.resolve_inference_profile("3.0", "ap-southeast-2")
            == "apac.twelvelabs.marengo-embed-3-0-v1:0"
        )


class TestBuildTextPayload:
    """build_text_payload(version, query_text) -> dict matching the model's schema"""

    def test_3_0_payload_is_nested(self):
        assert bem.build_text_payload("3.0", "fire") == {
            "inputType": "text",
            "text": {"inputText": "fire"},
        }

    def test_2_7_payload_is_flat(self):
        assert bem.build_text_payload("2.7", "fire") == {
            "inputType": "text",
            "inputText": "fire",
        }
