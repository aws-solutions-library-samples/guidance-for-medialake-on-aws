"""
Unit tests for the normalizer base interfaces and factory.

These tests verify that:
- The factory raises errors for unknown source types
- ValidationResult and NormalizationResult structures work correctly
- The SourceNormalizer interface can be properly implemented
- The register_normalizer function works correctly
"""

import pytest

# Import from nodes (pytest.ini adds lambdas/ to pythonpath)
from nodes.external_metadata_fetch.normalizers import (
    NORMALIZER_REGISTRY,
    NormalizationResult,
    SourceNormalizer,
    ValidationIssue,
    ValidationResult,
    ValidationSeverity,
    create_normalizer,
    register_normalizer,
)


@pytest.mark.unit
class TestValidationSeverity:
    """Tests for ValidationSeverity enum"""

    def test_warning_value(self):
        """WARNING severity has correct string value."""
        assert ValidationSeverity.WARNING.value == "warning"

    def test_error_value(self):
        """ERROR severity has correct string value."""
        assert ValidationSeverity.ERROR.value == "error"


@pytest.mark.unit
class TestValidationIssue:
    """Tests for ValidationIssue dataclass"""

    def test_create_warning_issue(self):
        """Creates a warning issue with all fields."""
        issue = ValidationIssue(
            severity=ValidationSeverity.WARNING,
            field_path="title",
            message="Title is missing",
            source_value=None,
        )

        assert issue.severity == ValidationSeverity.WARNING
        assert issue.field_path == "title"
        assert issue.message == "Title is missing"
        assert issue.source_value is None

    def test_create_error_issue_with_source_value(self):
        """Creates an error issue with source value."""
        issue = ValidationIssue(
            severity=ValidationSeverity.ERROR,
            field_path="ratings.0.value",
            message="Invalid rating value",
            source_value="INVALID",
        )

        assert issue.severity == ValidationSeverity.ERROR
        assert issue.field_path == "ratings.0.value"
        assert issue.source_value == "INVALID"

    def test_to_dict_includes_all_fields(self):
        """to_dict includes all fields when source_value is present."""
        issue = ValidationIssue(
            severity=ValidationSeverity.ERROR,
            field_path="field.path",
            message="Error message",
            source_value={"key": "value"},
        )

        result = issue.to_dict()

        assert result == {
            "severity": "error",
            "field_path": "field.path",
            "message": "Error message",
            "source_value": {"key": "value"},
        }

    def test_to_dict_excludes_none_source_value(self):
        """to_dict excludes source_value when None."""
        issue = ValidationIssue(
            severity=ValidationSeverity.WARNING,
            field_path="field",
            message="Warning",
            source_value=None,
        )

        result = issue.to_dict()

        assert "source_value" not in result
        assert result == {
            "severity": "warning",
            "field_path": "field",
            "message": "Warning",
        }


@pytest.mark.unit
class TestValidationResult:
    """Tests for ValidationResult dataclass"""

    def test_create_valid_result(self):
        """Creates a valid result with no issues."""
        result = ValidationResult(is_valid=True)

        assert result.is_valid is True
        assert result.issues == []
        assert result.warnings == []
        assert result.errors == []

    def test_create_invalid_result_with_errors(self):
        """Creates an invalid result with error issues."""
        error = ValidationIssue(
            severity=ValidationSeverity.ERROR,
            field_path="root",
            message="Missing required field",
        )
        result = ValidationResult(is_valid=False, issues=[error])

        assert result.is_valid is False
        assert len(result.issues) == 1
        assert len(result.errors) == 1
        assert len(result.warnings) == 0

    def test_warnings_property_filters_correctly(self):
        """warnings property returns only WARNING severity issues."""
        warning = ValidationIssue(
            severity=ValidationSeverity.WARNING,
            field_path="optional_field",
            message="Optional field missing",
        )
        error = ValidationIssue(
            severity=ValidationSeverity.ERROR,
            field_path="required_field",
            message="Required field missing",
        )
        result = ValidationResult(is_valid=False, issues=[warning, error])

        assert len(result.warnings) == 1
        assert result.warnings[0].field_path == "optional_field"

    def test_errors_property_filters_correctly(self):
        """errors property returns only ERROR severity issues."""
        warning = ValidationIssue(
            severity=ValidationSeverity.WARNING,
            field_path="optional_field",
            message="Optional field missing",
        )
        error = ValidationIssue(
            severity=ValidationSeverity.ERROR,
            field_path="required_field",
            message="Required field missing",
        )
        result = ValidationResult(is_valid=False, issues=[warning, error])

        assert len(result.errors) == 1
        assert result.errors[0].field_path == "required_field"

    def test_add_warning_appends_issue(self):
        """add_warning appends a warning issue."""
        result = ValidationResult(is_valid=True)
        result.add_warning("field", "Warning message", "value")

        assert len(result.issues) == 1
        assert result.issues[0].severity == ValidationSeverity.WARNING
        assert result.issues[0].field_path == "field"
        assert result.issues[0].message == "Warning message"
        assert result.issues[0].source_value == "value"
        # Warnings don't change is_valid
        assert result.is_valid is True

    def test_add_error_appends_issue_and_invalidates(self):
        """add_error appends an error issue and sets is_valid to False."""
        result = ValidationResult(is_valid=True)
        result.add_error("field", "Error message", "bad_value")

        assert len(result.issues) == 1
        assert result.issues[0].severity == ValidationSeverity.ERROR
        assert result.is_valid is False

    def test_to_dict_structure(self):
        """to_dict returns correct structure with counts."""
        result = ValidationResult(is_valid=True)
        result.add_warning("field1", "Warning 1")
        result.add_warning("field2", "Warning 2")
        result.add_error("field3", "Error 1")

        dict_result = result.to_dict()

        assert dict_result["is_valid"] is False
        assert dict_result["warning_count"] == 2
        assert dict_result["error_count"] == 1
        assert len(dict_result["issues"]) == 3


@pytest.mark.unit
class TestNormalizationResult:
    """Tests for NormalizationResult dataclass"""

    def test_create_successful_result(self):
        """Creates a successful normalization result."""
        metadata = {"content_id": "123", "work_type": "Episode"}
        result = NormalizationResult(
            success=True,
            normalized_metadata=metadata,
        )

        assert result.success is True
        assert result.normalized_metadata == metadata
        assert result.validation.is_valid is True
        assert result.raw_source is None
        assert result.schema_version == "1.0.0"

    def test_create_failed_result(self):
        """Creates a failed normalization result with validation errors."""
        validation = ValidationResult(is_valid=False)
        validation.add_error("root", "Empty metadata")

        result = NormalizationResult(
            success=False,
            validation=validation,
            raw_source={"empty": True},
        )

        assert result.success is False
        assert result.normalized_metadata is None
        assert result.validation.is_valid is False
        assert result.raw_source == {"empty": True}

    def test_to_dict_successful(self):
        """to_dict includes normalized_metadata when successful."""
        metadata = {"content_id": "123"}
        result = NormalizationResult(
            success=True,
            normalized_metadata=metadata,
        )

        dict_result = result.to_dict()

        assert dict_result["success"] is True
        assert dict_result["normalized_metadata"] == metadata
        assert dict_result["schema_version"] == "1.0.0"
        assert "validation" in dict_result

    def test_to_dict_excludes_none_values(self):
        """to_dict excludes None values."""
        result = NormalizationResult(success=False)

        dict_result = result.to_dict()

        assert "normalized_metadata" not in dict_result
        assert "raw_source" not in dict_result

    def test_to_dict_includes_raw_source_when_present(self):
        """to_dict includes raw_source when present."""
        result = NormalizationResult(
            success=True,
            normalized_metadata={"id": "1"},
            raw_source={"original": "data"},
        )

        dict_result = result.to_dict()

        assert dict_result["raw_source"] == {"original": "data"}


@pytest.mark.unit
class TestSourceNormalizerInterface:
    """Tests for SourceNormalizer abstract base class"""

    def test_cannot_instantiate_abstract_class(self):
        """Cannot instantiate SourceNormalizer directly."""
        with pytest.raises(TypeError):
            SourceNormalizer()

    def test_concrete_implementation_works(self):
        """A concrete implementation can be instantiated."""

        class TestNormalizer(SourceNormalizer):
            def get_source_type(self) -> str:
                return "test"

            def validate_input(self, raw_metadata: dict) -> ValidationResult:
                return ValidationResult(is_valid=True)

            def normalize(self, raw_metadata: dict) -> NormalizationResult:
                return NormalizationResult(
                    success=True,
                    normalized_metadata={"test": True},
                )

        normalizer = TestNormalizer()
        assert normalizer.get_source_type() == "test"

    def test_config_is_stored(self):
        """Config passed to constructor is stored."""

        class TestNormalizer(SourceNormalizer):
            def get_source_type(self) -> str:
                return "test"

            def validate_input(self, raw_metadata: dict) -> ValidationResult:
                return ValidationResult(is_valid=True)

            def normalize(self, raw_metadata: dict) -> NormalizationResult:
                return NormalizationResult(success=True)

        config = {"key": "value", "nested": {"a": 1}}
        normalizer = TestNormalizer(config)

        assert normalizer.config == config

    def test_config_defaults_to_empty_dict(self):
        """Config defaults to empty dict when not provided."""

        class TestNormalizer(SourceNormalizer):
            def get_source_type(self) -> str:
                return "test"

            def validate_input(self, raw_metadata: dict) -> ValidationResult:
                return ValidationResult(is_valid=True)

            def normalize(self, raw_metadata: dict) -> NormalizationResult:
                return NormalizationResult(success=True)

        normalizer = TestNormalizer()
        assert normalizer.config == {}

    def test_get_config_value_returns_value(self):
        """get_config_value returns config value when present."""

        class TestNormalizer(SourceNormalizer):
            def get_source_type(self) -> str:
                return "test"

            def validate_input(self, raw_metadata: dict) -> ValidationResult:
                return ValidationResult(is_valid=True)

            def normalize(self, raw_metadata: dict) -> NormalizationResult:
                return NormalizationResult(success=True)

        normalizer = TestNormalizer({"source_namespace_prefix": "CUSTOMER"})
        assert normalizer.get_config_value("source_namespace_prefix") == "CUSTOMER"

    def test_get_config_value_returns_default(self):
        """get_config_value returns default when key not present."""

        class TestNormalizer(SourceNormalizer):
            def get_source_type(self) -> str:
                return "test"

            def validate_input(self, raw_metadata: dict) -> ValidationResult:
                return ValidationResult(is_valid=True)

            def normalize(self, raw_metadata: dict) -> NormalizationResult:
                return NormalizationResult(success=True)

        normalizer = TestNormalizer({})
        assert normalizer.get_config_value("missing_key", "default") == "default"


@pytest.mark.unit
class TestNormalizerFactory:
    """Tests for create_normalizer factory function"""

    def test_raises_error_for_unknown_source_type(self):
        """Factory raises ValueError for unknown source type."""
        with pytest.raises(ValueError) as exc_info:
            create_normalizer("unknown_type")

        assert "Unknown source type: 'unknown_type'" in str(exc_info.value)
        assert "Available normalizers:" in str(exc_info.value)

    def test_error_message_lists_available_normalizers(self):
        """Error message includes list of available normalizers."""

        # First register a test normalizer
        class TestNormalizer(SourceNormalizer):
            def get_source_type(self) -> str:
                return "test_registered"

            def validate_input(self, raw_metadata: dict) -> ValidationResult:
                return ValidationResult(is_valid=True)

            def normalize(self, raw_metadata: dict) -> NormalizationResult:
                return NormalizationResult(success=True)

        # Save original registry state
        original_registry = NORMALIZER_REGISTRY.copy()

        try:
            register_normalizer("test_registered", TestNormalizer)

            with pytest.raises(ValueError) as exc_info:
                create_normalizer("nonexistent")

            assert "test_registered" in str(exc_info.value)
        finally:
            # Restore original registry
            NORMALIZER_REGISTRY.clear()
            NORMALIZER_REGISTRY.update(original_registry)

    def test_creates_registered_normalizer(self):
        """Factory creates normalizer when type is registered."""

        class TestNormalizer(SourceNormalizer):
            def get_source_type(self) -> str:
                return "factory_test"

            def validate_input(self, raw_metadata: dict) -> ValidationResult:
                return ValidationResult(is_valid=True)

            def normalize(self, raw_metadata: dict) -> NormalizationResult:
                return NormalizationResult(success=True)

        # Save original registry state
        original_registry = NORMALIZER_REGISTRY.copy()

        try:
            register_normalizer("factory_test", TestNormalizer)
            normalizer = create_normalizer("factory_test")

            assert isinstance(normalizer, TestNormalizer)
            assert normalizer.get_source_type() == "factory_test"
        finally:
            # Restore original registry
            NORMALIZER_REGISTRY.clear()
            NORMALIZER_REGISTRY.update(original_registry)

    def test_passes_config_to_normalizer(self):
        """Factory passes config to normalizer constructor."""

        class TestNormalizer(SourceNormalizer):
            def get_source_type(self) -> str:
                return "config_test"

            def validate_input(self, raw_metadata: dict) -> ValidationResult:
                return ValidationResult(is_valid=True)

            def normalize(self, raw_metadata: dict) -> NormalizationResult:
                return NormalizationResult(success=True)

        # Save original registry state
        original_registry = NORMALIZER_REGISTRY.copy()

        try:
            register_normalizer("config_test", TestNormalizer)
            config = {"source_namespace_prefix": "TEST", "custom_key": 123}
            normalizer = create_normalizer("config_test", config)

            assert normalizer.config == config
        finally:
            # Restore original registry
            NORMALIZER_REGISTRY.clear()
            NORMALIZER_REGISTRY.update(original_registry)


@pytest.mark.unit
class TestRegisterNormalizer:
    """Tests for register_normalizer function"""

    def test_registers_valid_normalizer(self):
        """Registers a valid normalizer class."""

        class ValidNormalizer(SourceNormalizer):
            def get_source_type(self) -> str:
                return "valid"

            def validate_input(self, raw_metadata: dict) -> ValidationResult:
                return ValidationResult(is_valid=True)

            def normalize(self, raw_metadata: dict) -> NormalizationResult:
                return NormalizationResult(success=True)

        # Save original registry state
        original_registry = NORMALIZER_REGISTRY.copy()

        try:
            register_normalizer("valid_test", ValidNormalizer)
            assert "valid_test" in NORMALIZER_REGISTRY
            assert NORMALIZER_REGISTRY["valid_test"] == ValidNormalizer
        finally:
            # Restore original registry
            NORMALIZER_REGISTRY.clear()
            NORMALIZER_REGISTRY.update(original_registry)

    def test_raises_error_for_non_normalizer_class(self):
        """Raises TypeError for class not inheriting from SourceNormalizer."""

        class NotANormalizer:
            pass

        with pytest.raises(TypeError) as exc_info:
            register_normalizer("invalid", NotANormalizer)

        assert "must inherit from SourceNormalizer" in str(exc_info.value)
        assert "NotANormalizer" in str(exc_info.value)

    def test_overwrites_existing_registration(self):
        """Overwrites existing registration with same source type."""

        class NormalizerV1(SourceNormalizer):
            def get_source_type(self) -> str:
                return "v1"

            def validate_input(self, raw_metadata: dict) -> ValidationResult:
                return ValidationResult(is_valid=True)

            def normalize(self, raw_metadata: dict) -> NormalizationResult:
                return NormalizationResult(success=True)

        class NormalizerV2(SourceNormalizer):
            def get_source_type(self) -> str:
                return "v2"

            def validate_input(self, raw_metadata: dict) -> ValidationResult:
                return ValidationResult(is_valid=True)

            def normalize(self, raw_metadata: dict) -> NormalizationResult:
                return NormalizationResult(success=True)

        # Save original registry state
        original_registry = NORMALIZER_REGISTRY.copy()

        try:
            register_normalizer("overwrite_test", NormalizerV1)
            register_normalizer("overwrite_test", NormalizerV2)

            assert NORMALIZER_REGISTRY["overwrite_test"] == NormalizerV2
        finally:
            # Restore original registry
            NORMALIZER_REGISTRY.clear()
            NORMALIZER_REGISTRY.update(original_registry)
