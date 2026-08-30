"""
Tests for the S3 Vectors index metadata-filterability configuration.

Root cause of the search bug: the index was created with NO metadataConfiguration,
so ALL 14 metadata keys were filterable-by-default. During the first concurrent
bulk load into a fresh index, S3 Vectors silently failed to register
`embedding_option` as filterable for some vectors (a schema-establishment race),
so the search filter `embedding_option = visual` matched nothing for those assets.

Fix: declare the return-only keys as NON-filterable at index creation. This shrinks
the filterable set to the few keys search actually filters on and makes filterability
deterministic instead of inferred from the write stream.

These tests guard the critical invariant: the keys search filters on
(embedding_option, inventory_id, embedding_scope, content_type) must NEVER be
listed as non-filterable, or the bug returns.
"""

import importlib.util
import os

_MOD = os.path.join(
    os.path.dirname(__file__), "..", "..",
    "medialake_constructs", "shared_constructs", "s3_vectors.py",
)


def _load_s3_vectors():
    spec = importlib.util.spec_from_file_location("s3_vectors", _MOD)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# Keys the search path filters on — MUST remain filterable.
FILTERABLE_REQUIRED = {"inventory_id", "embedding_option", "embedding_scope", "content_type"}

# Return-only keys — safe to declare non-filterable.
EXPECTED_NON_FILTERABLE = {
    "timestamp",
    "start_offset_sec",
    "end_offset_sec",
    "start_timecode",
    "end_timecode",
    "embedding_dimension",
    "space_type",
    "model_provider",
    "model_name",
    "model_version",
}


class TestNonFilterableMetadataKeys:
    def test_constant_exists(self):
        mod = _load_s3_vectors()
        assert hasattr(mod, "NON_FILTERABLE_METADATA_KEYS")

    def test_declares_the_return_only_keys(self):
        mod = _load_s3_vectors()
        assert set(mod.NON_FILTERABLE_METADATA_KEYS) == EXPECTED_NON_FILTERABLE

    def test_never_marks_a_filterable_search_key_as_non_filterable(self):
        mod = _load_s3_vectors()
        offenders = FILTERABLE_REQUIRED & set(mod.NON_FILTERABLE_METADATA_KEYS)
        assert not offenders, f"these must stay filterable: {offenders}"

    def test_within_s3_vectors_10_key_non_filterable_limit(self):
        # S3 Vectors allows at most 10 non-filterable metadata keys per index.
        mod = _load_s3_vectors()
        assert len(mod.NON_FILTERABLE_METADATA_KEYS) <= 10
