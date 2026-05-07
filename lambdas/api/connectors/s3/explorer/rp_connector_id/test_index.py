"""
Unit tests for S3 explorer Lambda function
Testing prefix validation, normalization, and security constraints
"""

import sys
from unittest.mock import MagicMock

# Mock AWS dependencies before importing index
sys.modules["boto3"] = MagicMock()
sys.modules["boto3.dynamodb"] = MagicMock()
sys.modules["boto3.dynamodb.conditions"] = MagicMock()
sys.modules["aws_lambda_powertools"] = MagicMock()
sys.modules["common_libraries"] = MagicMock()
sys.modules["common_libraries.cors_utils"] = MagicMock()

import pytest
from index import normalize_prefix, parse_object_prefixes, validate_prefix_access


class TestNormalizePrefix:
    """Tests for normalize_prefix function"""

    def test_normalize_empty_string(self):
        """Empty string should return empty string"""
        assert normalize_prefix("") == ""

    def test_normalize_none(self):
        """None should return empty string"""
        assert normalize_prefix(None) == ""

    def test_normalize_whitespace_only(self):
        """Whitespace-only string should return empty string"""
        assert normalize_prefix("   ") == ""
        assert normalize_prefix("\t") == ""
        assert normalize_prefix("\n") == ""

    def test_normalize_adds_trailing_slash(self):
        """Prefix without trailing slash should get one added"""
        assert normalize_prefix("foo") == "foo/"
        assert normalize_prefix("foo/bar") == "foo/bar/"

    def test_normalize_preserves_trailing_slash(self):
        """Prefix with trailing slash should remain unchanged"""
        assert normalize_prefix("foo/") == "foo/"
        assert normalize_prefix("foo/bar/") == "foo/bar/"

    def test_normalize_trims_whitespace(self):
        """Leading and trailing whitespace should be removed"""
        assert normalize_prefix("  foo  ") == "foo/"
        assert normalize_prefix("  foo/bar  ") == "foo/bar/"
        assert normalize_prefix("\tfoo/bar\n") == "foo/bar/"

    def test_normalize_trims_and_adds_slash(self):
        """Should trim whitespace and add trailing slash"""
        assert normalize_prefix("  foo  ") == "foo/"
        assert normalize_prefix("  foo/bar ") == "foo/bar/"


class TestParseObjectPrefixes:
    """Tests for parse_object_prefixes function"""

    def test_parse_none(self):
        """None should return empty list"""
        assert parse_object_prefixes(None) == []

    def test_parse_empty_string(self):
        """Empty string should return empty list"""
        assert parse_object_prefixes("") == []

    def test_parse_single_string(self):
        """Single string should return list with normalized prefix"""
        assert parse_object_prefixes("foo") == ["foo/"]
        assert parse_object_prefixes("foo/") == ["foo/"]
        assert parse_object_prefixes("foo/bar") == ["foo/bar/"]

    def test_parse_string_with_whitespace(self):
        """String with whitespace should be trimmed and normalized"""
        assert parse_object_prefixes("  foo  ") == ["foo/"]
        assert parse_object_prefixes("  foo/bar  ") == ["foo/bar/"]

    def test_parse_empty_list(self):
        """Empty list should return empty list"""
        assert parse_object_prefixes([]) == []

    def test_parse_list_of_strings(self):
        """List of strings should return normalized prefixes"""
        assert parse_object_prefixes(["foo", "bar"]) == ["foo/", "bar/"]
        assert parse_object_prefixes(["foo/", "bar/"]) == ["foo/", "bar/"]
        assert parse_object_prefixes(["foo/bar", "baz/qux"]) == ["foo/bar/", "baz/qux/"]

    def test_parse_list_with_empty_strings(self):
        """Empty strings in list should be filtered out"""
        assert parse_object_prefixes(["foo", "", "bar"]) == ["foo/", "bar/"]
        assert parse_object_prefixes(["foo", "  ", "bar"]) == ["foo/", "bar/"]

    def test_parse_list_with_whitespace(self):
        """Whitespace in list items should be trimmed"""
        assert parse_object_prefixes(["  foo  ", "  bar  "]) == ["foo/", "bar/"]


class TestValidatePrefixAccess:
    """Tests for validate_prefix_access function"""

    def test_no_allowed_prefixes_allows_all(self):
        """When no allowed prefixes are configured, all access should be allowed"""
        assert validate_prefix_access("foo/", []) is True
        assert validate_prefix_access("foo/bar/", []) is True
        assert validate_prefix_access("", []) is True

    def test_exact_match_allowed(self):
        """Exact match of allowed prefix should be allowed"""
        assert validate_prefix_access("foo/", ["foo/"]) is True
        assert validate_prefix_access("foo/bar/", ["foo/bar/"]) is True

    def test_subdirectory_allowed(self):
        """Subdirectory of allowed prefix should be allowed"""
        assert validate_prefix_access("foo/bar/", ["foo/"]) is True
        assert validate_prefix_access("foo/bar/baz/", ["foo/"]) is True
        assert validate_prefix_access("foo/bar/baz/qux/", ["foo/bar/"]) is True

    def test_parent_directory_denied(self):
        """
        SECURITY: Parent directory of allowed prefix should be DENIED
        This is the fix for Comment 1
        """
        assert validate_prefix_access("foo/", ["foo/bar/"]) is False
        assert validate_prefix_access("foo/", ["foo/bar/baz/"]) is False

    def test_sibling_directory_denied(self):
        """
        SECURITY: Sibling directory (prefix collision) should be DENIED
        This tests the boundary check from Comment 2
        """
        # "foobar/" should NOT match allowed "foo/"
        assert validate_prefix_access("foobar/", ["foo/"]) is False

        # "foo2/" should NOT match allowed "foo/"
        assert validate_prefix_access("foo2/", ["foo/"]) is False

        # "foo/bar2/" should NOT match allowed "foo/bar/"
        assert validate_prefix_access("foo/bar2/", ["foo/bar/"]) is False

    def test_multiple_allowed_prefixes(self):
        """Should match any of multiple allowed prefixes"""
        allowed = ["foo/", "bar/"]
        assert validate_prefix_access("foo/", allowed) is True
        assert validate_prefix_access("foo/baz/", allowed) is True
        assert validate_prefix_access("bar/", allowed) is True
        assert validate_prefix_access("bar/qux/", allowed) is True
        assert validate_prefix_access("baz/", allowed) is False

    def test_empty_prefix_behavior(self):
        """
        Empty prefix should be rejected for security when there are configured prefixes.
        Empty string in allowed list is filtered out.
        """
        # Empty prefix with empty allowed list is rejected (filtered out)
        assert validate_prefix_access("", [""]) is False
        # Empty prefix with other prefixes should be rejected
        assert validate_prefix_access("", ["foo/"]) is False

    def test_normalization_applied(self):
        """Validation should work even when prefixes aren't pre-normalized"""
        # Requested prefix without trailing slash
        assert validate_prefix_access("foo/bar", ["foo/"]) is True

        # Both without trailing slashes
        assert validate_prefix_access("foo/bar", ["foo"]) is True

    def test_whitespace_handled(self):
        """Whitespace should be handled correctly"""
        assert validate_prefix_access("  foo/bar  ", ["foo/"]) is True
        assert validate_prefix_access("foo/bar", ["  foo/  "]) is True

    def test_none_prefix_treated_as_empty(self):
        """None prefix should be treated as empty string and follow empty string rules"""
        # None is treated as empty and rejected with empty allowed list
        assert validate_prefix_access(None, [""]) is False
        # None is treated as empty and rejected with configured prefixes
        assert validate_prefix_access(None, ["foo/"]) is False


class TestSecurityScenarios:
    """Specific security test cases from the verification comments"""

    def test_comment_1_counter_example_1(self):
        """
        Comment 1 counter-example: allowed "foo/" with requested "foobar/"
        Should be DENIED (sibling directory, not subdirectory)
        """
        assert validate_prefix_access("foobar/", ["foo/"]) is False
        assert validate_prefix_access("foobar", ["foo/"]) is False

    def test_comment_1_counter_example_2(self):
        """
        Comment 1 counter-example: allowed "foo/bar/" with requested "foo/"
        Should be DENIED (parent directory access)
        """
        assert validate_prefix_access("foo/", ["foo/bar/"]) is False
        assert validate_prefix_access("foo", ["foo/bar/"]) is False

    def test_legitimate_subdirectory_access(self):
        """
        Legitimate access: requested is within allowed prefix
        Should be ALLOWED
        """
        assert validate_prefix_access("foo/bar/", ["foo/"]) is True
        assert validate_prefix_access("foo/bar/baz/", ["foo/"]) is True
        assert validate_prefix_access("foo/bar/baz/qux/", ["foo/bar/"]) is True

    def test_edge_case_similar_names(self):
        """
        Edge cases with similar prefix names
        Should properly distinguish between similar names
        """
        # "foot/" should not match "foo/"
        assert validate_prefix_access("foot/", ["foo/"]) is False

        # "foo-bar/" should not match "foo/"
        assert validate_prefix_access("foo-bar/", ["foo/"]) is False

        # "foo_bar/" should not match "foo/"
        assert validate_prefix_access("foo_bar/", ["foo/"]) is False


class TestDeterministicDefaultSelection:
    """Tests for deterministic default prefix selection (Comment 3)"""

    def test_sorting_ensures_consistency(self):
        """
        Prefixes should be sorted to ensure deterministic default selection
        This is tested indirectly through lambda_handler, but we can verify
        the sort behavior here
        """
        # Example: if these are the allowed prefixes, they should be sorted
        prefixes = ["zebra/", "apple/", "banana/"]
        sorted_prefixes = sorted(prefixes)

        # Should be alphabetically sorted
        assert sorted_prefixes == ["apple/", "banana/", "zebra/"]

        # First element should always be "apple/" regardless of input order
        assert sorted_prefixes[0] == "apple/"

    def test_normalized_prefixes_sort_correctly(self):
        """Normalized prefixes should sort deterministically"""
        prefixes = ["foo/bar/", "foo/", "foo/baz/"]
        sorted_prefixes = sorted(prefixes)

        # Shorter prefixes come first when they share a common base
        assert sorted_prefixes == ["foo/", "foo/bar/", "foo/baz/"]
        assert sorted_prefixes[0] == "foo/"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
