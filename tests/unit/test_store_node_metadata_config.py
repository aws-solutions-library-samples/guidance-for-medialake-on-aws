"""
Tests for the s3_vector_store Lambda's index-creation metadata configuration.

The store node auto-creates the index on first write if CloudFormation hasn't yet.
That fallback path MUST declare the same non-filterable keys as the CDK construct,
or an index born from the Lambda would reintroduce the filterability race.

The Lambda is a separate deployment package and cannot import the CDK construct,
so it keeps its own copy of the key list. This test guards that the two copies
stay in sync AND that no search-filter key is ever marked non-filterable.
"""

import importlib.util
import os


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_BASE = os.path.join(os.path.dirname(__file__), "..", "..")
_CDK = os.path.join(_BASE, "medialake_constructs", "shared_constructs", "s3_vectors.py")
_LAMBDA = os.path.join(_BASE, "lambdas", "nodes", "s3_vector_store", "metadata_config.py")

FILTERABLE_REQUIRED = {"inventory_id", "embedding_option", "embedding_scope", "content_type"}


class TestStoreNodeMetadataConfig:
    def test_lambda_constant_exists(self):
        mod = _load(_LAMBDA, "metadata_config")
        assert hasattr(mod, "NON_FILTERABLE_METADATA_KEYS")

    def test_matches_cdk_construct(self):
        lam = _load(_LAMBDA, "metadata_config")
        cdk = _load(_CDK, "s3_vectors")
        assert set(lam.NON_FILTERABLE_METADATA_KEYS) == set(cdk.NON_FILTERABLE_METADATA_KEYS)

    def test_never_marks_a_search_filter_key_non_filterable(self):
        mod = _load(_LAMBDA, "metadata_config")
        assert not (FILTERABLE_REQUIRED & set(mod.NON_FILTERABLE_METADATA_KEYS))

    def test_within_10_key_limit(self):
        mod = _load(_LAMBDA, "metadata_config")
        assert len(mod.NON_FILTERABLE_METADATA_KEYS) <= 10
